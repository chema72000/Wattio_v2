"""LTspice schematic editor tool — modify components, models, and directives."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool

_VALID_ACTIONS = {
    "list_components",
    "set_value",
    "remove_component",
    "set_model",
    "add_directive",
    "remove_directive",
}


class LTspiceEditTool(BaseTool):
    name = "ltspice_edit"
    description = (
        "Modify LTspice schematics — list components, change values, "
        "remove components, change models, add/remove SPICE directives. "
        "Edits are applied to a working copy; the original is never modified."
    )
    parameters = {
        "type": "object",
        "properties": {
            "schematic_path": {
                "type": "string",
                "description": "Path to the .asc schematic file (relative to project directory).",
            },
            "action": {
                "type": "string",
                "enum": sorted(_VALID_ACTIONS),
                "description": (
                    "Operation to perform: list_components, set_value, "
                    "remove_component, set_model, add_directive, remove_directive."
                ),
            },
            "component": {
                "type": "string",
                "description": (
                    'Component reference designator, e.g. "R1", "C3", "D1". '
                    "Required for set_value, remove_component, set_model."
                ),
            },
            "value": {
                "type": "string",
                "description": (
                    'New component value, e.g. "10k", "100n", "47u". '
                    "Required for set_value."
                ),
            },
            "model": {
                "type": "string",
                "description": (
                    'New SPICE model name, e.g. "1N4148", "IRF540N". '
                    "Required for set_model."
                ),
            },
            "directive": {
                "type": "string",
                "description": (
                    'SPICE directive text, e.g. ".tran 500m", ".ac dec 20 1 1meg". '
                    "Required for add_directive and remove_directive."
                ),
            },
            "component_filter": {
                "type": "string",
                "description": (
                    'Prefix filter for list_components, e.g. "R" for resistors only, '
                    '"C" for capacitors. Optional — omit to list all.'
                ),
            },
        },
        "required": ["schematic_path", "action"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        from wattio.tools.ltspice_helpers import (
            create_working_copy,
            ensure_sim_workdir,
            validate_schematic_path,
        )

        action = kwargs.get("action", "")
        if action not in _VALID_ACTIONS:
            return ToolResult(
                tool_call_id="",
                content=(
                    f"Error: Invalid action '{action}'. "
                    f"Valid actions: {', '.join(sorted(_VALID_ACTIONS))}"
                ),
                is_error=True,
            )

        # ── Validate schematic ──────────────────────────────────
        schematic_path = kwargs.get("schematic_path", "")
        result = validate_schematic_path(project_dir, schematic_path)
        if isinstance(result, str):
            return ToolResult(tool_call_id="", content=result, is_error=True)
        original_asc = result

        # ── Import PyLTSpice ────────────────────────────────────
        try:
            from PyLTSpice import AscEditor
        except ImportError:
            return ToolResult(
                tool_call_id="",
                content=(
                    "Error: PyLTSpice is not installed. "
                    "Install it with: pip install PyLTSpice"
                ),
                is_error=True,
            )

        # ── Dispatch to action handler ──────────────────────────
        if action == "list_components":
            return self._list_components(original_asc, AscEditor, kwargs)

        # All other actions need a working copy
        work_dir = ensure_sim_workdir(project_dir)
        work_asc = create_working_copy(original_asc, work_dir)

        try:
            editor = AscEditor(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error opening schematic: {e}",
                is_error=True,
            )

        handler = {
            "set_value": self._set_value,
            "remove_component": self._remove_component,
            "set_model": self._set_model,
            "add_directive": self._add_directive,
            "remove_directive": self._remove_directive,
        }[action]

        return handler(editor, work_asc, kwargs)

    # ── Action handlers ─────────────────────────────────────────

    @staticmethod
    def _list_components(
        asc_path: Path, asc_editor_cls: type, kwargs: dict[str, Any]
    ) -> ToolResult:
        """List all components with their values."""
        try:
            editor = asc_editor_cls(str(asc_path))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error opening schematic: {e}",
                is_error=True,
            )

        component_filter = kwargs.get("component_filter")

        try:
            if component_filter:
                components = editor.get_components(component_filter)
            else:
                components = editor.get_components()
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error listing components: {e}",
                is_error=True,
            )

        if not components:
            filter_msg = f" matching '{component_filter}'" if component_filter else ""
            return ToolResult(
                tool_call_id="",
                content=f"No components found{filter_msg} in `{asc_path.name}`.",
            )

        lines = [
            f"**Components in `{asc_path.name}`**"
            + (f" (filter: {component_filter})" if component_filter else ""),
            "",
            "| Component | Value |",
            "|-----------|-------|",
        ]

        for comp in components:
            try:
                value = editor.get_component_value(comp)
            except Exception:
                value = "—"
            lines.append(f"| {comp} | {value} |")

        lines.append(f"\n*{len(components)} component(s) listed.*")
        return ToolResult(tool_call_id="", content="\n".join(lines))

    @staticmethod
    def _set_value(
        editor: Any, work_asc: Path, kwargs: dict[str, Any]
    ) -> ToolResult:
        """Change a component's value."""
        component = kwargs.get("component")
        value = kwargs.get("value")

        if not component:
            return ToolResult(
                tool_call_id="",
                content="Error: 'component' parameter is required for set_value.",
                is_error=True,
            )
        if not value:
            return ToolResult(
                tool_call_id="",
                content="Error: 'value' parameter is required for set_value.",
                is_error=True,
            )

        try:
            editor.set_component_value(component, value)
            editor.write_netlist(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error setting value for {component}: {e}",
                is_error=True,
            )

        return ToolResult(
            tool_call_id="",
            content=(
                f"Set **{component}** = `{value}` in working copy.\n"
                f"Working copy: `{work_asc}`"
            ),
        )

    @staticmethod
    def _remove_component(
        editor: Any, work_asc: Path, kwargs: dict[str, Any]
    ) -> ToolResult:
        """Remove a component from the schematic."""
        component = kwargs.get("component")

        if not component:
            return ToolResult(
                tool_call_id="",
                content="Error: 'component' parameter is required for remove_component.",
                is_error=True,
            )

        try:
            editor.remove_component(component)
            editor.write_netlist(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error removing {component}: {e}",
                is_error=True,
            )

        return ToolResult(
            tool_call_id="",
            content=(
                f"Removed **{component}** from working copy.\n"
                f"Working copy: `{work_asc}`"
            ),
        )

    @staticmethod
    def _set_model(
        editor: Any, work_asc: Path, kwargs: dict[str, Any]
    ) -> ToolResult:
        """Change a component's SPICE model."""
        component = kwargs.get("component")
        model = kwargs.get("model")

        if not component:
            return ToolResult(
                tool_call_id="",
                content="Error: 'component' parameter is required for set_model.",
                is_error=True,
            )
        if not model:
            return ToolResult(
                tool_call_id="",
                content="Error: 'model' parameter is required for set_model.",
                is_error=True,
            )

        try:
            editor.set_element_model(component, model)
            editor.write_netlist(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error setting model for {component}: {e}",
                is_error=True,
            )

        return ToolResult(
            tool_call_id="",
            content=(
                f"Set **{component}** model = `{model}` in working copy.\n"
                f"Working copy: `{work_asc}`"
            ),
        )

    @staticmethod
    def _add_directive(
        editor: Any, work_asc: Path, kwargs: dict[str, Any]
    ) -> ToolResult:
        """Add a SPICE directive."""
        directive = kwargs.get("directive")

        if not directive:
            return ToolResult(
                tool_call_id="",
                content="Error: 'directive' parameter is required for add_directive.",
                is_error=True,
            )

        try:
            editor.add_instruction(directive)
            editor.write_netlist(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error adding directive: {e}",
                is_error=True,
            )

        return ToolResult(
            tool_call_id="",
            content=(
                f"Added directive `{directive}` to working copy.\n"
                f"Working copy: `{work_asc}`"
            ),
        )

    @staticmethod
    def _remove_directive(
        editor: Any, work_asc: Path, kwargs: dict[str, Any]
    ) -> ToolResult:
        """Remove a SPICE directive."""
        directive = kwargs.get("directive")

        if not directive:
            return ToolResult(
                tool_call_id="",
                content="Error: 'directive' parameter is required for remove_directive.",
                is_error=True,
            )

        try:
            editor.remove_instruction(directive)
            editor.write_netlist(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error removing directive: {e}",
                is_error=True,
            )

        return ToolResult(
            tool_call_id="",
            content=(
                f"Removed directive matching `{directive}` from working copy.\n"
                f"Working copy: `{work_asc}`"
            ),
        )
