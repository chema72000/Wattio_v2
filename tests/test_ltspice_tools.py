"""Tests for LTspice tools — all mock-based, no LTspice needed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from wattio.tools.ltspice_helpers import (
    check_platform,
    compute_measurements,
    create_working_copy,
    eng,
    ensure_results_dir,
    ensure_sim_workdir,
    extract_parameters_from_asc,
    find_ltspice_exe,
    validate_schematic_path,
)


# ── Platform detection ──────────────────────────────────────────────


class TestCheckPlatform:
    def test_macos_returns_error(self) -> None:
        with patch("wattio.tools.ltspice_helpers.platform.system", return_value="Darwin"):
            err = check_platform()
            assert err is not None
            assert "Windows" in err

    def test_linux_returns_error(self) -> None:
        with patch("wattio.tools.ltspice_helpers.platform.system", return_value="Linux"):
            err = check_platform()
            assert err is not None
            assert "Windows" in err

    def test_windows_returns_none(self) -> None:
        with patch("wattio.tools.ltspice_helpers.platform.system", return_value="Windows"):
            err = check_platform()
            assert err is None


# ── LTspice exe discovery ──────────────────────────────────────────


class TestFindLTspiceExe:
    def test_found_in_path(self) -> None:
        with patch("wattio.tools.ltspice_helpers.shutil.which", return_value="/usr/bin/ltspice.exe"):
            result = find_ltspice_exe()
            assert result == Path("/usr/bin/ltspice.exe")

    def test_not_found(self) -> None:
        with (
            patch("wattio.tools.ltspice_helpers.shutil.which", return_value=None),
            patch.object(Path, "is_file", return_value=False),
        ):
            result = find_ltspice_exe()
            assert result is None


# ── Path validation ─────────────────────────────────────────────────


class TestValidateSchematicPath:
    def test_valid_path(self, tmp_project: Path) -> None:
        result = validate_schematic_path(
            tmp_project, "01 - LTspice/flyback/test.asc"
        )
        assert isinstance(result, Path)
        assert result.suffix == ".asc"

    def test_missing_file(self, tmp_project: Path) -> None:
        result = validate_schematic_path(tmp_project, "nonexistent.asc")
        assert isinstance(result, str)
        assert "not found" in result.lower()

    def test_outside_project(self, tmp_project: Path) -> None:
        result = validate_schematic_path(tmp_project, "../../etc/passwd")
        assert isinstance(result, str)
        assert "outside" in result.lower()

    def test_wrong_extension(self, tmp_project: Path) -> None:
        # Create a non-.asc file
        txt_file = tmp_project / "readme.txt"
        txt_file.write_text("hello")
        result = validate_schematic_path(tmp_project, "readme.txt")
        assert isinstance(result, str)
        assert ".asc" in result.lower()


# ── Directory helpers ───────────────────────────────────────────────


class TestDirectoryHelpers:
    def test_ensure_results_dir(self, tmp_project: Path) -> None:
        results = ensure_results_dir(tmp_project)
        assert results.is_dir()
        assert results == tmp_project / "wattio" / "results"

    def test_ensure_sim_workdir(self, tmp_project: Path) -> None:
        sim = ensure_sim_workdir(tmp_project)
        assert sim.is_dir()
        assert sim == tmp_project / "wattio" / "sim_work"


# ── Working copy ────────────────────────────────────────────────────


class TestCreateWorkingCopy:
    def test_basic_copy(self, tmp_project: Path) -> None:
        original = tmp_project / "01 - LTspice" / "flyback" / "test.asc"
        work_dir = ensure_sim_workdir(tmp_project)
        copy = create_working_copy(original, work_dir)
        assert copy.is_file()
        assert copy.name == "test.asc"
        assert copy.parent == work_dir
        assert copy.read_text() == original.read_text()

    def test_copy_with_suffix(self, tmp_project: Path) -> None:
        original = tmp_project / "01 - LTspice" / "flyback" / "test.asc"
        work_dir = ensure_sim_workdir(tmp_project)
        copy = create_working_copy(original, work_dir, suffix="_sweep_003")
        assert copy.name == "test_sweep_003.asc"
        assert copy.is_file()

    def test_copies_supporting_files(self, tmp_project: Path) -> None:
        # Create a .lib file next to the schematic
        lib_dir = tmp_project / "01 - LTspice" / "flyback"
        lib_file = lib_dir / "models.lib"
        lib_file.write_text(".model NPN NPN(BF=100)")

        original = lib_dir / "test.asc"
        work_dir = ensure_sim_workdir(tmp_project)
        create_working_copy(original, work_dir)

        assert (work_dir / "models.lib").is_file()


# ── .asc parameter parsing ─────────────────────────────────────────


class TestExtractParametersFromAsc:
    def test_simple_param(self) -> None:
        content = "TEXT 100 200 Left 2 !.param load_resistance 10"
        params = extract_parameters_from_asc(content)
        assert params["load_resistance"] == "10"

    def test_param_with_equals(self) -> None:
        content = "TEXT 100 200 Left 2 !.param fsw=100k"
        params = extract_parameters_from_asc(content)
        assert params["fsw"] == "100k"

    def test_multiple_params_one_line(self) -> None:
        content = "TEXT 100 200 Left 2 !.param Vin 48 Vout=12"
        params = extract_parameters_from_asc(content)
        assert params["Vin"] == "48"
        assert params["Vout"] == "12"

    def test_scientific_notation(self) -> None:
        content = ".param Cin 100n\n.param Cout 47u"
        params = extract_parameters_from_asc(content)
        assert params["Cin"] == "100n"
        assert params["Cout"] == "47u"

    def test_braces(self) -> None:
        content = ".param inductance {560u}"
        params = extract_parameters_from_asc(content)
        assert params["inductance"] == "560u"

    def test_no_params(self) -> None:
        content = "Version 4\nSHEET 1 880 680\n"
        params = extract_parameters_from_asc(content)
        assert params == {}

    def test_multiline(self) -> None:
        content = (
            "TEXT 100 100 Left 2 !.param R1 10\n"
            "TEXT 100 200 Left 2 !.param R2 20\n"
            "TEXT 100 300 Left 2 !.param C1=100n\n"
        )
        params = extract_parameters_from_asc(content)
        assert len(params) == 3
        assert params["R1"] == "10"
        assert params["R2"] == "20"
        assert params["C1"] == "100n"


# ── Engineering notation ────────────────────────────────────────────


class TestEngineeringNotation:
    def test_zero(self) -> None:
        assert eng(0, "V") == "0V"

    def test_microhenry(self) -> None:
        result = eng(560e-6, "H")
        assert "560" in result
        assert "H" in result

    def test_milliamp(self) -> None:
        result = eng(0.0023, "A")
        assert "2.3" in result
        assert "A" in result

    def test_kilohertz(self) -> None:
        result = eng(100_000, "Hz")
        assert "100" in result
        assert "kHz" in result

    def test_volts(self) -> None:
        result = eng(12, "V")
        assert "12" in result
        assert "V" in result

    def test_nanofarad(self) -> None:
        result = eng(100e-9, "F")
        assert "100" in result
        assert "F" in result

    def test_negative(self) -> None:
        result = eng(-3.3, "V")
        assert "-3.3" in result
        assert "V" in result

    def test_no_unit(self) -> None:
        result = eng(1000)
        assert "1k" in result


# ── Measurement computation ─────────────────────────────────────────


class TestComputeMeasurements:
    def test_basic_dc(self) -> None:
        """DC signal: all measurements should be the same value."""
        import numpy as np

        t = np.linspace(0, 1, 100)
        d = np.full_like(t, 5.0)
        m = compute_measurements(t, d)
        assert m["min"] == pytest.approx(5.0)
        assert m["max"] == pytest.approx(5.0)
        assert m["avg"] == pytest.approx(5.0)
        assert m["rms"] == pytest.approx(5.0)
        assert m["peak_to_peak"] == pytest.approx(0.0)
        assert m["final"] == pytest.approx(5.0)

    def test_custom_window(self) -> None:
        """Measurement window should filter data."""
        import numpy as np

        t = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
        d = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        m = compute_measurements(t, d, measure_start=0.3)
        assert m["min"] == pytest.approx(3.0)
        assert m["max"] == pytest.approx(5.0)
        assert m["final"] == pytest.approx(5.0)

    def test_sine_wave(self) -> None:
        """Sine wave should have ~2.0 peak-to-peak and ~0.707 RMS."""
        import numpy as np

        t = np.linspace(0, 1, 10000)
        d = np.sin(2 * np.pi * 10 * t)  # 10Hz sine
        m = compute_measurements(t, d, measure_start=0.0)
        assert m["peak_to_peak"] == pytest.approx(2.0, abs=0.01)
        assert m["rms"] == pytest.approx(1 / 2**0.5, abs=0.01)


# ── Tool auto-discovery ─────────────────────────────────────────────


class TestToolDiscovery:
    def test_ltspice_tools_registered(self) -> None:
        """All four LTspice tools should be auto-discovered."""
        from wattio.tools.registry import ToolRegistry

        registry = ToolRegistry.auto_discover()
        names = [t.name for t in registry.all_tools]
        assert "ltspice_run" in names
        assert "ltspice_sweep" in names
        assert "ltspice_plot" in names
        assert "ltspice_edit" in names

    def test_helpers_not_registered(self) -> None:
        """The helpers module should NOT be registered as a tool."""
        from wattio.tools.registry import ToolRegistry

        registry = ToolRegistry.auto_discover()
        names = [t.name for t in registry.all_tools]
        assert "ltspice_helpers" not in names


# ── Tool error handling (mock-based) ────────────────────────────────


class TestLTspiceRunErrors:
    @pytest.mark.asyncio
    async def test_platform_error_on_macos(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_run import LTspiceRunTool

        tool = LTspiceRunTool()
        with patch("wattio.tools.ltspice_helpers.platform.system", return_value="Darwin"):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
            assert result.is_error
            assert "Windows" in result.content

    @pytest.mark.asyncio
    async def test_missing_ltspice(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_run import LTspiceRunTool

        tool = LTspiceRunTool()
        with (
            patch("wattio.tools.ltspice_helpers.platform.system", return_value="Windows"),
            patch("wattio.tools.ltspice_helpers.find_ltspice_exe", return_value=None),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
            assert result.is_error
            assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_missing_schematic(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_run import LTspiceRunTool

        tool = LTspiceRunTool()
        with (
            patch("wattio.tools.ltspice_helpers.platform.system", return_value="Windows"),
            patch("wattio.tools.ltspice_helpers.shutil.which", return_value="/usr/bin/ltspice.exe"),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="nonexistent.asc"
            )
            assert result.is_error
            assert "not found" in result.content.lower()


class TestLTspiceSweepErrors:
    @pytest.mark.asyncio
    async def test_too_many_sweep_points(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_sweep import LTspiceSweepTool

        tool = LTspiceSweepTool()
        with (
            patch("wattio.tools.ltspice_helpers.platform.system", return_value="Windows"),
            patch("wattio.tools.ltspice_helpers.shutil.which", return_value="/usr/bin/ltspice.exe"),
        ):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                sweep_param="fsw",
                start=1000,
                stop=1_000_000,
                step=1000,
                measure_trace="I(L1)",
            )
            assert result.is_error
            assert "max" in result.content.lower() or "50" in result.content

    @pytest.mark.asyncio
    async def test_platform_error(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_sweep import LTspiceSweepTool

        tool = LTspiceSweepTool()
        with patch("wattio.tools.ltspice_helpers.platform.system", return_value="Darwin"):
            result = await tool.execute(
                tmp_project,
                schematic_path="test.asc",
                sweep_param="fsw",
                start=100000,
                stop=500000,
                step=100000,
                measure_trace="I(L1)",
            )
            assert result.is_error
            assert "Windows" in result.content


class TestLTspicePlotErrors:
    @pytest.mark.asyncio
    async def test_missing_raw_file(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_plot import LTspicePlotTool

        tool = LTspicePlotTool()
        result = await tool.execute(
            tmp_project, raw_path="nonexistent.raw", traces=["V(OUT)"]
        )
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_empty_traces(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_plot import LTspicePlotTool

        tool = LTspicePlotTool()
        result = await tool.execute(
            tmp_project, raw_path="test.raw", traces=[]
        )
        assert result.is_error
        assert "empty" in result.content.lower()

    @pytest.mark.asyncio
    async def test_outside_project(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_plot import LTspicePlotTool

        tool = LTspicePlotTool()
        result = await tool.execute(
            tmp_project, raw_path="../../etc/passwd", traces=["V(OUT)"]
        )
        assert result.is_error
        assert "outside" in result.content.lower()


# ── LTspice Edit tool ─────────────────────────────────────────────


class TestLTspiceEditListComponents:
    @pytest.mark.asyncio
    async def test_list_all_components(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor(
            components=["R1", "R2", "C1"],
            values={"R1": "10k", "R2": "20k", "C1": "100n"},
        )

        with patch("wattio.tools.ltspice_edit.AscEditor", mock_editor, create=True):
            # Patch at the import target inside execute
            with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
                result = await tool.execute(
                    tmp_project,
                    schematic_path="01 - LTspice/flyback/test.asc",
                    action="list_components",
                )

        assert not result.is_error
        assert "R1" in result.content
        assert "10k" in result.content
        assert "C1" in result.content
        assert "3 component(s)" in result.content

    @pytest.mark.asyncio
    async def test_list_filtered(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor(
            components=["R1", "R2"],
            values={"R1": "10k", "R2": "20k"},
            filtered_components={"R": ["R1", "R2"]},
        )

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="list_components",
                component_filter="R",
            )

        assert not result.is_error
        assert "R1" in result.content
        assert "R2" in result.content
        assert "filter: R" in result.content

    @pytest.mark.asyncio
    async def test_list_empty(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor(components=[], values={})

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="list_components",
            )

        assert not result.is_error
        assert "No components found" in result.content


class TestLTspiceEditSetValue:
    @pytest.mark.asyncio
    async def test_set_value_success(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="set_value",
                component="R1",
                value="20k",
            )

        assert not result.is_error
        assert "R1" in result.content
        assert "20k" in result.content
        # Verify the mock was called correctly
        instance = mock_editor.return_value
        instance.set_component_value.assert_called_once_with("R1", "20k")
        instance.write_netlist.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_value_missing_component(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="set_value",
                value="20k",
            )

        assert result.is_error
        assert "component" in result.content.lower()

    @pytest.mark.asyncio
    async def test_set_value_missing_value(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="set_value",
                component="R1",
            )

        assert result.is_error
        assert "value" in result.content.lower()


class TestLTspiceEditRemoveComponent:
    @pytest.mark.asyncio
    async def test_remove_success(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="remove_component",
                component="C2",
            )

        assert not result.is_error
        assert "C2" in result.content
        instance = mock_editor.return_value
        instance.remove_component.assert_called_once_with("C2")

    @pytest.mark.asyncio
    async def test_remove_missing_component(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="remove_component",
            )

        assert result.is_error
        assert "component" in result.content.lower()


class TestLTspiceEditSetModel:
    @pytest.mark.asyncio
    async def test_set_model_success(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="set_model",
                component="D1",
                model="1N4148",
            )

        assert not result.is_error
        assert "D1" in result.content
        assert "1N4148" in result.content
        instance = mock_editor.return_value
        instance.set_element_model.assert_called_once_with("D1", "1N4148")

    @pytest.mark.asyncio
    async def test_set_model_missing_params(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="set_model",
                component="D1",
            )

        assert result.is_error
        assert "model" in result.content.lower()


class TestLTspiceEditDirectives:
    @pytest.mark.asyncio
    async def test_add_directive(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="add_directive",
                directive=".tran 500m",
            )

        assert not result.is_error
        assert ".tran 500m" in result.content
        instance = mock_editor.return_value
        instance.add_instruction.assert_called_once_with(".tran 500m")

    @pytest.mark.asyncio
    async def test_remove_directive(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="remove_directive",
                directive=".tran",
            )

        assert not result.is_error
        assert ".tran" in result.content
        instance = mock_editor.return_value
        instance.remove_instruction.assert_called_once_with(".tran")

    @pytest.mark.asyncio
    async def test_add_directive_missing_param(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="add_directive",
            )

        assert result.is_error
        assert "directive" in result.content.lower()


class TestLTspiceEditErrors:
    @pytest.mark.asyncio
    async def test_invalid_action(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="01 - LTspice/flyback/test.asc",
                action="add_component",
            )

        assert result.is_error
        assert "Invalid action" in result.content

    @pytest.mark.asyncio
    async def test_missing_schematic(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_edit import LTspiceEditTool

        tool = LTspiceEditTool()
        mock_editor = _make_mock_asc_editor()

        with patch.dict("sys.modules", {"PyLTSpice": _fake_pyltspice(mock_editor)}):
            result = await tool.execute(
                tmp_project,
                schematic_path="nonexistent.asc",
                action="list_components",
            )

        assert result.is_error
        assert "not found" in result.content.lower()


class TestLTspiceEditDiscovery:
    def test_ltspice_edit_registered(self) -> None:
        """ltspice_edit should be auto-discovered by the registry."""
        from wattio.tools.registry import ToolRegistry

        registry = ToolRegistry.auto_discover()
        names = [t.name for t in registry.all_tools]
        assert "ltspice_edit" in names


# ── Mock helpers for ltspice_edit tests ────────────────────────────


def _make_mock_asc_editor(
    components: list[str] | None = None,
    values: dict[str, str] | None = None,
    filtered_components: dict[str, list[str]] | None = None,
) -> Any:
    """Create a mock AscEditor class that returns predictable data.

    Args:
        components: List of component names for get_components().
        values: Dict of component name to value for get_component_value().
        filtered_components: Dict of prefix to component list for filtered get_components(prefix).
    """
    from unittest.mock import MagicMock

    components = components or []
    values = values or {}
    filtered_components = filtered_components or {}

    mock_cls = MagicMock()
    instance = MagicMock()
    mock_cls.return_value = instance

    def get_components(prefix: str | None = None) -> list[str]:
        if prefix and prefix in filtered_components:
            return filtered_components[prefix]
        if prefix is None:
            return components
        return components

    def get_component_value(comp: str) -> str:
        return values.get(comp, "—")

    instance.get_components = MagicMock(side_effect=get_components)
    instance.get_component_value = MagicMock(side_effect=get_component_value)

    return mock_cls


def _fake_pyltspice(mock_editor: Any) -> Any:
    """Create a fake PyLTSpice module with AscEditor set to the mock."""
    from types import ModuleType

    mod = ModuleType("PyLTSpice")
    mod.AscEditor = mock_editor  # type: ignore[attr-defined]
    return mod


# ── Additional edge-case tests ─────────────────────────────────────


class TestEngEdgeCases:
    def test_femto_scale(self) -> None:
        result = eng(5e-15, "F")
        assert "5" in result
        assert "f" in result
        assert "F" in result

    def test_giga_scale(self) -> None:
        result = eng(2.5e9, "Hz")
        assert "2.5" in result
        assert "GHz" in result


class TestComputeMeasurementsEdgeCases:
    def test_measure_start_beyond_data(self) -> None:
        """When measure_start is beyond all data, fallback to all data."""
        import numpy as np

        t = np.array([0.0, 0.1, 0.2, 0.3])
        d = np.array([1.0, 2.0, 3.0, 4.0])
        m = compute_measurements(t, d, measure_start=999.0)
        # Should fall back to using all data
        assert m["min"] == pytest.approx(1.0)
        assert m["max"] == pytest.approx(4.0)
        assert m["final"] == pytest.approx(4.0)


class TestIsInSimWorkdir:
    def test_inside(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_helpers import is_in_sim_workdir

        sim_dir = ensure_sim_workdir(tmp_project)
        asc = sim_dir / "test.asc"
        asc.write_text("Version 4")
        assert is_in_sim_workdir(asc, tmp_project) is True

    def test_outside(self, tmp_project: Path) -> None:
        from wattio.tools.ltspice_helpers import is_in_sim_workdir

        asc = tmp_project / "01 - LTspice" / "flyback" / "test.asc"
        assert is_in_sim_workdir(asc, tmp_project) is False


class TestExtractParametersEdgeCases:
    def test_comments_mixed_in(self) -> None:
        """Lines that are not .param directives are ignored."""
        content = (
            "* This is a comment\n"
            ".param R_load 10\n"
            "; Another comment line\n"
            "TEXT 100 200 Left 2 !.param fsw=100k\n"
        )
        params = extract_parameters_from_asc(content)
        assert params["R_load"] == "10"
        assert params["fsw"] == "100k"
        assert len(params) == 2
