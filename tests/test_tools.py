"""Tests for the tool system."""

from pathlib import Path

import pytest

from wattio.tools.file_reader import FileReaderTool
from wattio.tools.registry import ToolRegistry


@pytest.fixture
def file_reader() -> FileReaderTool:
    return FileReaderTool()


class TestFileReader:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_project: Path, file_reader: FileReaderTool) -> None:
        result = await file_reader.execute(
            tmp_project, file_path="01 - LTspice/flyback/test.asc"
        )
        assert not result.is_error
        assert "Version 4" in result.content

    @pytest.mark.asyncio
    async def test_read_missing_file(self, tmp_project: Path, file_reader: FileReaderTool) -> None:
        result = await file_reader.execute(tmp_project, file_path="nonexistent.asc")
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_read_unsupported_extension(self, tmp_project: Path, file_reader: FileReaderTool) -> None:
        # Create a .exe file
        exe_file = tmp_project / "bad.exe"
        exe_file.write_text("binary")
        result = await file_reader.execute(tmp_project, file_path="bad.exe")
        assert result.is_error
        assert "unsupported" in result.content.lower()

    @pytest.mark.asyncio
    async def test_read_outside_project(self, tmp_project: Path, file_reader: FileReaderTool) -> None:
        result = await file_reader.execute(tmp_project, file_path="../../etc/passwd")
        assert result.is_error
        assert "outside" in result.content.lower()


class TestToolRegistry:
    def test_auto_discover(self) -> None:
        registry = ToolRegistry.auto_discover()
        assert len(registry.all_tools) >= 3
        names = [t.name for t in registry.all_tools]
        assert "file_reader" in names
        assert "magnetic_suggest" in names
        assert "knowledge_search" in names

    def test_to_openai_schemas(self) -> None:
        registry = ToolRegistry.auto_discover()
        schemas = registry.to_openai_schemas()
        assert len(schemas) >= 3
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "description" in schema["function"]
