"""Tests for the MagneticSuggestTool — all mock-based."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from wattio.tools.magnetic_suggest import MagneticSuggestTool


@pytest.fixture
def tool() -> MagneticSuggestTool:
    return MagneticSuggestTool()


def _make_proc_mock(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    """Create a mock subprocess with AsyncMock communicate."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


class TestMagneticSuggest:
    @pytest.mark.asyncio
    async def test_success_binary_found(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        """When the binary is found via shutil.which, it's used directly."""
        proc_mock = _make_proc_mock(stdout=b"Suggested: WE-FLEX 760308103207\n")

        with (
            patch("shutil.which", return_value="/usr/bin/magnetic-suggest"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc_mock),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
        assert not result.is_error
        assert "WE-FLEX" in result.content

    @pytest.mark.asyncio
    async def test_success_python_fallback(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        """When binary is not found, falls back to python -m."""
        proc_mock = _make_proc_mock(stdout=b"Suggested: EFD20\n")

        with (
            patch("shutil.which", return_value=None),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc_mock) as mock_exec,
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
        assert not result.is_error
        # Verify python -m fallback was used
        cmd = mock_exec.call_args[0]
        assert cmd[0] == "python3"
        assert cmd[1] == "-m"
        assert cmd[2] == "magnetic_suggest.cli"

    @pytest.mark.asyncio
    async def test_timeout_error(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        proc_mock = _make_proc_mock()
        proc_mock.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with (
            patch("shutil.which", return_value="/usr/bin/magnetic-suggest"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc_mock),
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
        assert result.is_error
        assert "timed out" in result.content.lower()

    @pytest.mark.asyncio
    async def test_not_installed_error(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        with (
            patch("shutil.which", return_value=None),
            patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
        assert result.is_error
        assert "not installed" in result.content.lower()

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        proc_mock = _make_proc_mock(
            returncode=1, stderr=b"Error: invalid schematic\n"
        )

        with (
            patch("shutil.which", return_value="/usr/bin/magnetic-suggest"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc_mock),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
        assert result.is_error
        assert "exit code 1" in result.content
        assert "invalid schematic" in result.content

    @pytest.mark.asyncio
    async def test_missing_schematic_path(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        result = await tool.execute(tmp_project, schematic_path="")
        assert result.is_error
        assert "required" in result.content.lower()

    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        result = await tool.execute(tmp_project, schematic_path="nonexistent.asc")
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_outside_project(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        result = await tool.execute(tmp_project, schematic_path="../../etc/passwd")
        assert result.is_error
        assert "outside" in result.content.lower()

    @pytest.mark.asyncio
    async def test_wrong_extension(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        # Create a non-.asc file
        txt_file = tmp_project / "readme.txt"
        txt_file.write_text("hello")
        result = await tool.execute(tmp_project, schematic_path="readme.txt")
        assert result.is_error
        assert ".asc" in result.content.lower()

    @pytest.mark.asyncio
    async def test_empty_output(self, tmp_project: Path, tool: MagneticSuggestTool) -> None:
        """Empty subprocess output → 'No matching components'."""
        proc_mock = _make_proc_mock(stdout=b"", stderr=b"")

        with (
            patch("shutil.which", return_value="/usr/bin/magnetic-suggest"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc_mock),
        ):
            result = await tool.execute(
                tmp_project, schematic_path="01 - LTspice/flyback/test.asc"
            )
        assert not result.is_error
        assert "No matching components" in result.content
