"""Terminal REPL with prompt-toolkit and Rich output."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.panel import Panel

from wattio import __version__
from wattio.config import ensure_wattio_dir, load_config

console = Console()

BANNER = Panel(
    f"[bold yellow]⚡ Wattio[/] v{__version__} — Power Electronics AI Assistant\n"
    "Type your question or [bold]/help[/]. Ctrl+D to exit.",
    border_style="yellow",
)

SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/export": "Export today's diary to .docx",
    "/clear": "Clear conversation history",
    "/config": "Show current configuration",
}

HELP_TEXT = "\n".join(f"  [bold]{cmd}[/]  {desc}" for cmd, desc in SLASH_COMMANDS.items())


async def _run_repl(project_dir: Path) -> None:
    """Main async REPL loop."""
    wattio_dir = ensure_wattio_dir(project_dir)
    config = load_config(project_dir)

    # Lazy imports to avoid circular deps
    from wattio.agent import Agent

    agent = Agent(config=config, project_dir=project_dir)

    history_file = wattio_dir / "history"
    session: PromptSession[str] = PromptSession(
        message="⚡ ",
        history=FileHistory(str(history_file)),
    )

    console.print(BANNER)
    console.print(
        f"  Project: [cyan]{project_dir.name}[/]  |  "
        f"LLM: [cyan]{config.llm.provider}/{config.llm.model}[/]\n"
    )

    while True:
        try:
            user_input = await session.prompt_async()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/]")
            await agent.shutdown()
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            await _handle_slash(user_input, agent, project_dir)
            continue

        # Send to agent
        await agent.handle_user_input(user_input)


async def _handle_slash(command: str, agent: Agent, project_dir: Path) -> None:
    """Process slash commands."""
    cmd = command.split()[0].lower()

    if cmd == "/help":
        console.print("\n[bold]Available commands:[/]")
        console.print(HELP_TEXT)
        console.print()

    elif cmd == "/export":
        from wattio.diary.export import export_today
        result = await export_today(project_dir)
        console.print(f"  [green]{result}[/]")

    elif cmd == "/clear":
        agent.clear_history()
        console.print("  [yellow]Conversation history cleared.[/]")

    elif cmd == "/config":
        console.print(f"  Provider: [cyan]{agent.config.llm.provider}[/]")
        console.print(f"  Model: [cyan]{agent.config.llm.model}[/]")
        console.print(f"  Diary: [cyan]{'on' if agent.config.diary.enabled else 'off'}[/]")

    else:
        console.print(f"  [red]Unknown command:[/] {cmd}. Type /help for available commands.")


def main() -> None:
    """Entry point for `wattio` command."""
    project_dir = Path.cwd()
    try:
        asyncio.run(_run_repl(project_dir))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
