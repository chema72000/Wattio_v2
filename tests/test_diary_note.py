"""Tests for the DiaryNoteTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattio.tools.diary_note import DiaryNoteTool


@pytest.fixture
def tool() -> DiaryNoteTool:
    return DiaryNoteTool()


class TestDiaryNote:
    @pytest.mark.asyncio
    async def test_default_category(self, tmp_project: Path, tool: DiaryNoteTool) -> None:
        result = await tool.execute(tmp_project, note="Test note")
        assert not result.is_error
        assert "note" in result.content.lower()
        # Verify written to diary file
        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        assert len(diary_files) == 1
        content = diary_files[0].read_text()
        assert "\U0001F4CC NOTE" in content
        assert "Test note" in content

    @pytest.mark.asyncio
    async def test_decision_icon(self, tmp_project: Path, tool: DiaryNoteTool) -> None:
        result = await tool.execute(tmp_project, note="Use flyback topology", category="decision")
        assert not result.is_error
        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        content = diary_files[0].read_text()
        assert "\u2705 DECISION" in content
        assert "Use flyback topology" in content

    @pytest.mark.asyncio
    async def test_todo_icon(self, tmp_project: Path, tool: DiaryNoteTool) -> None:
        result = await tool.execute(tmp_project, note="Add snubber", category="todo")
        assert not result.is_error
        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        content = diary_files[0].read_text()
        assert "\u2610 TODO" in content

    @pytest.mark.asyncio
    async def test_recommendation_icon(self, tmp_project: Path, tool: DiaryNoteTool) -> None:
        result = await tool.execute(tmp_project, note="Use Wurth inductors", category="recommendation")
        assert not result.is_error
        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        content = diary_files[0].read_text()
        assert "\u2b50 RECOMMENDATION" in content

    @pytest.mark.asyncio
    async def test_empty_note_error(self, tmp_project: Path, tool: DiaryNoteTool) -> None:
        result = await tool.execute(tmp_project, note="")
        assert result.is_error
        assert "required" in result.content.lower()

    @pytest.mark.asyncio
    async def test_timestamp_present(self, tmp_project: Path, tool: DiaryNoteTool) -> None:
        await tool.execute(tmp_project, note="Timestamped note")
        diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
        content = diary_files[0].read_text()
        # Timestamp format: ### HH:MM — 📌 NOTE
        import re
        assert re.search(r"### \d{2}:\d{2} —", content)
