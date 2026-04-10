"""Core agent loop — receives user input, calls LLM, executes tools."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from wattio.models import LLMResponse, Message, Role, ToolCall, ToolResult, WattioConfig
from wattio.llm.router import LLMRouter
from wattio.tools.registry import ToolRegistry

console = Console()

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"

MAX_TOOL_ROUNDS = 20  # Safety limit on consecutive tool calls
_TOOL_RESULT_TRUNCATE_LEN = 300  # Max chars for old tool results sent to LLM

_LTSPICE_TOOLS = {"ltspice_run", "ltspice_sweep", "ltspice_plot", "ltspice_edit", "ltspice_export_csv"}

_PLOT_SAVED_RE = re.compile(r"\*\*Plot saved:\*\*\s*`([^`]+)`")


def _extract_simulation_info(
    tool_name: str, arguments: dict, content: str
) -> dict:
    """Extract simulation metadata from tool arguments and result content."""
    info: dict = {}

    # Schematic path
    info["schematic"] = arguments.get("schematic_path") or arguments.get("raw_path", "")

    # Summary — first line of the result content
    info["summary"] = content.splitlines()[0] if content else ""

    # Parameters
    params: dict[str, str] | None = None
    if tool_name == "ltspice_run":
        pc = arguments.get("param_changes")
        if pc:
            params = {k: str(v) for k, v in pc.items()}
    elif tool_name == "ltspice_sweep":
        sp = arguments.get("sweep_param", "")
        if sp:
            params = {
                sp: f"{arguments.get('start')} → {arguments.get('stop')} step {arguments.get('step')}"
            }
    elif tool_name == "ltspice_edit":
        action = arguments.get("action", "")
        parts: dict[str, str] = {}
        if arguments.get("component"):
            parts["component"] = arguments["component"]
        if arguments.get("value"):
            parts["value"] = arguments["value"]
        if arguments.get("model"):
            parts["model"] = arguments["model"]
        if arguments.get("directive"):
            parts["directive"] = arguments["directive"]
        if parts:
            params = parts
        # Summarise with the action name
        info["summary"] = f"**Action:** `{action}` — {info['summary']}"
    info["params"] = params

    # Traces
    traces = arguments.get("traces")
    if not traces and tool_name == "ltspice_sweep":
        mt = arguments.get("measure_trace")
        if mt:
            traces = [mt]
    info["traces"] = traces

    # Plot path
    m = _PLOT_SAVED_RE.search(content)
    info["plot_path"] = m.group(1) if m else None

    return info


class Agent:
    """Wattio agent: LLM + tools + diary."""

    def __init__(self, config: WattioConfig, project_dir: Path) -> None:
        self.config = config
        self.project_dir = project_dir
        self._router = LLMRouter(config)
        self._registry = ToolRegistry.auto_discover()
        self._history: list[Message] = []
        self._diary_writer = None

        # Load recent diary for session continuity
        from wattio.diary.loader import load_recent_diary
        diary_history = load_recent_diary(project_dir)
        if diary_history:
            diary_context = (
                "## Previous sessions\n\n"
                "Below are highlights from recent sessions. Use this to recall "
                "past decisions, TODOs, and context. Do NOT tell the engineer "
                "to check the diary — you already have it.\n\n"
                f"{diary_history}"
            )
            console.print("  [dim]Diary loaded from previous sessions.[/]")
        else:
            diary_context = ""

        # Build system prompt
        template = SYSTEM_PROMPT_PATH.read_text()
        system_text = template.format(
            project_dir=project_dir.name,
            date=date.today().isoformat(),
            diary_context=diary_context,
        )
        self._system_message = Message.system(system_text)

        # Init diary if enabled
        if config.diary.enabled:
            from wattio.diary.writer import DiaryWriter
            self._diary_writer = DiaryWriter(project_dir)

        tools = self._registry.all_tools
        if tools:
            tool_names = ", ".join(t.name for t in tools)
            console.print(f"  Tools loaded: [dim]{tool_names}[/]\n")

    def clear_history(self) -> None:
        self._history.clear()

    def _prepare_messages(self, current_round_start: int) -> list[Message]:
        """Build message list for LLM, compressing old tool results.

        Tool results from previous rounds are compressed to save tokens:
        - Image data (base64) is stripped from old results (already analyzed)
        - Large text results are truncated (unless marked keep_full)
        Only tool results in the current round are sent in full.
        """
        messages = [self._system_message]
        for i, msg in enumerate(self._history):
            if not (msg.role == Role.TOOL and msg.tool_result and i < current_round_start):
                messages.append(msg)
                continue

            tr = msg.tool_result
            if tr.is_error:
                messages.append(msg)
                continue

            # Strip image data from old results (LLM already saw them)
            if tr.image_base64:
                compressed = ToolResult(
                    tool_call_id=tr.tool_call_id,
                    content=tr.content,  # keeps "Image loaded: path (N bytes)"
                    is_error=False,
                )
                messages.append(Message.tool(compressed))
                continue

            # Truncate large text results (unless marked keep_full)
            if not tr.keep_full and len(tr.content) > _TOOL_RESULT_TRUNCATE_LEN:
                truncated_content = (
                    tr.content[:_TOOL_RESULT_TRUNCATE_LEN]
                    + f"\n\n[... truncated, originally {len(tr.content)} chars]"
                )
                compressed = ToolResult(
                    tool_call_id=tr.tool_call_id,
                    content=truncated_content,
                    is_error=False,
                )
                messages.append(Message.tool(compressed))
                continue

            messages.append(msg)
        return messages

    async def shutdown(self) -> None:
        if self._diary_writer:
            self._diary_writer.close_session()
        await self._router.close()

    async def handle_user_input(self, text: str) -> None:
        """Process one user message through the full agent loop."""
        user_msg = Message.user(text)
        self._history.append(user_msg)

        if self._diary_writer:
            self._diary_writer.log_user(text)

        # Agent loop: LLM may request tool calls, then we feed results back
        current_round_start = len(self._history)
        for _ in range(MAX_TOOL_ROUNDS):
            messages = self._prepare_messages(current_round_start)
            tool_schemas = self._registry.to_openai_schemas() or None

            try:
                response = await self._router.chat_stream(
                    messages,
                    tools=tool_schemas,
                    on_text=lambda chunk: console.print(chunk, end=""),
                )
            except Exception as e:
                console.print(f"\n  [red]LLM error:[/] {e}\n")
                return

            # If no tool calls, we have a final text response
            if not response.tool_calls:
                self._handle_streamed_response(response)
                return

            # Process tool calls (text was already streamed if any)
            assistant_msg = Message.assistant(
                text=response.content, tool_calls=response.tool_calls
            )
            self._history.append(assistant_msg)

            if response.content:
                # Text was already streamed, just add a newline
                console.print()

            await self._execute_tool_calls(response.tool_calls)
            # Tool results just added are "current round" for the next LLM call
            current_round_start = len(self._history) - len(response.tool_calls)
        else:
            console.print("\n  [yellow]Reached maximum tool call rounds.[/]\n")

    def _handle_text_response(self, response: LLMResponse) -> None:
        """Display and log a final text response (non-streaming fallback)."""
        text = response.content or ""
        self._history.append(Message.assistant(text))

        if text:
            console.print()
            console.print(Markdown(text))
            console.print()

        if self._diary_writer:
            self._diary_writer.log_assistant(text)

    def _handle_streamed_response(self, response: LLMResponse) -> None:
        """Log a response that was already streamed to the console."""
        text = response.content or ""
        self._history.append(Message.assistant(text))

        # Text was already printed via on_text callback; just add trailing newline
        console.print("\n")

        if self._diary_writer:
            self._diary_writer.log_assistant(text)

    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        """Execute each tool call and append results to history."""
        for tc in tool_calls:
            tool = self._registry.get(tc.name)
            if not tool:
                result = ToolResult(
                    tool_call_id=tc.id,
                    content=f"Error: Unknown tool '{tc.name}'",
                    is_error=True,
                )
            else:
                console.print(f"\n  [dim]⚙ {tc.name}[/]")

                if self._diary_writer:
                    self._diary_writer.log_tool_call(tc.name, tc.arguments)

                result = await tool.execute(self.project_dir, **tc.arguments)
                result.tool_call_id = tc.id

                if self._diary_writer:
                    self._diary_writer.log_tool_result(result.content, result.is_error)

                if (
                    self._diary_writer
                    and not result.is_error
                    and tc.name in _LTSPICE_TOOLS
                ):
                    info = _extract_simulation_info(
                        tc.name, tc.arguments, result.content
                    )
                    self._diary_writer.log_simulation(
                        tool_name=tc.name,
                        schematic=info["schematic"],
                        summary=info["summary"],
                        params=info["params"],
                        traces=info["traces"],
                        plot_path=info["plot_path"],
                    )

                if result.is_error:
                    console.print(f"  [red]Error:[/] {result.content}")

            self._history.append(Message.tool(result))
