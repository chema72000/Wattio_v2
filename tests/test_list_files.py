"""Tests for the ListFilesTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattio.tools.list_files import ListFilesTool


@pytest.fixture
def tool() -> ListFilesTool:
    return ListFilesTool()


class TestListFiles:
    @pytest.mark.asyncio
    async def test_list_project_root(self, tmp_project: Path, tool: ListFilesTool) -> None:
        result = await tool.execute(tmp_project)
        assert not result.is_error
        assert "Contents of ./" in result.content
        # Should see the "01 - LTspice" dir and "wattio" dir
        assert "wattio/" in result.content

    @pytest.mark.asyncio
    async def test_list_subdirectory(self, tmp_project: Path, tool: ListFilesTool) -> None:
        result = await tool.execute(tmp_project, directory="01 - LTspice/flyback")
        assert not result.is_error
        assert "test.asc" in result.content

    @pytest.mark.asyncio
    async def test_hidden_files_skipped(self, tmp_project: Path, tool: ListFilesTool) -> None:
        # Create a hidden file
        (tmp_project / ".hidden").write_text("secret")
        result = await tool.execute(tmp_project)
        assert not result.is_error
        assert ".hidden" not in result.content

    @pytest.mark.asyncio
    async def test_glob_pattern(self, tmp_project: Path, tool: ListFilesTool) -> None:
        result = await tool.execute(tmp_project, pattern="**/*.asc")
        assert not result.is_error
        assert "test.asc" in result.content

    @pytest.mark.asyncio
    async def test_glob_no_matches(self, tmp_project: Path, tool: ListFilesTool) -> None:
        result = await tool.execute(tmp_project, pattern="**/*.xyz")
        assert not result.is_error
        assert "No files matching" in result.content

    @pytest.mark.asyncio
    async def test_result_limit(self, tmp_project: Path, tool: ListFilesTool) -> None:
        """More than 50 glob matches are limited."""
        many_dir = tmp_project / "many"
        many_dir.mkdir()
        for i in range(60):
            (many_dir / f"file_{i:03d}.txt").write_text("data")
        result = await tool.execute(tmp_project, directory="many", pattern="*.txt")
        assert not result.is_error
        assert "and 10 more" in result.content

    @pytest.mark.asyncio
    async def test_outside_project_error(self, tmp_project: Path, tool: ListFilesTool) -> None:
        result = await tool.execute(tmp_project, directory="../../etc")
        assert result.is_error
        assert "outside" in result.content.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, tmp_project: Path, tool: ListFilesTool) -> None:
        result = await tool.execute(tmp_project, directory="nope")
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_empty_directory(self, tmp_project: Path, tool: ListFilesTool) -> None:
        empty = tmp_project / "empty"
        empty.mkdir()
        result = await tool.execute(tmp_project, directory="empty")
        assert not result.is_error
        assert "empty" in result.content.lower()

    @pytest.mark.asyncio
    async def test_default_directory(self, tmp_project: Path, tool: ListFilesTool) -> None:
        """None or '.' should list project root."""
        result = await tool.execute(tmp_project, directory=None)
        assert not result.is_error
        assert "Contents of ./" in result.content
