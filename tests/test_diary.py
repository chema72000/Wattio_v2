"""Tests for the diary system."""

from pathlib import Path

import pytest

from wattio.diary.writer import DiaryWriter
from wattio.diary.export import export_diary


class TestDiaryWriter:
    def test_creates_diary_file(self, tmp_project: Path) -> None:
        writer = DiaryWriter(tmp_project)
        writer.log_user("Hello Wattio")
        writer.close_session()

        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        assert len(diary_files) == 1

        content = diary_files[0].read_text()
        assert "Wattio Session Diary" in content
        assert "Hello Wattio" in content
        assert "Session ended" in content

    def test_logs_tool_calls(self, tmp_project: Path) -> None:
        writer = DiaryWriter(tmp_project)
        writer.log_user("Find magnetics")
        writer.log_tool_call("magnetic_suggest", {"schematic_path": "test.asc"})
        writer.log_tool_result("Found 3 components")
        writer.log_assistant("Here are the results")
        writer.close_session()

        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        content = diary_files[0].read_text()
        assert "magnetic_suggest" in content
        assert "Found 3 components" in content
        assert "Here are the results" in content

    def test_truncates_long_results(self, tmp_project: Path) -> None:
        writer = DiaryWriter(tmp_project)
        writer.log_user("test")
        writer.log_tool_result("x" * 5000)
        writer.close_session()

        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        content = diary_files[0].read_text()
        assert "truncated" in content


class TestDiaryExport:
    def test_export_creates_docx(self, tmp_project: Path) -> None:
        # Create a diary markdown file
        diary_dir = tmp_project / "wattio" / "diary"
        md_file = diary_dir / "2026-01-01.md"
        md_file.write_text("# Wattio Session Diary — 2026-01-01\n\n## Session 14:00\n\nHello\n", encoding="utf-8")

        result = export_diary(tmp_project, "2026-01-01")
        assert "Exported" in result

        docx_file = diary_dir / "2026-01-01.docx"
        assert docx_file.exists()
        assert docx_file.stat().st_size > 0

    def test_export_missing_diary(self, tmp_project: Path) -> None:
        result = export_diary(tmp_project, "1999-01-01")
        assert "No diary found" in result
