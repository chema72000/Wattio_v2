"""Tests for the diary loader (session memory)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattio.diary.loader import (
    MAX_DIARY_FILES,
    _extract_from_diary,
    _flush_category,
    load_recent_diary,
)


class TestLoadRecentDiary:
    def test_no_diary_dir(self, tmp_path: Path) -> None:
        result = load_recent_diary(tmp_path)
        assert result == ""

    def test_empty_diary_dir(self, tmp_project: Path) -> None:
        result = load_recent_diary(tmp_project)
        assert result == ""

    def test_decisions_parsed(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — \u2705 DECISION\n"
            "Use flyback topology for the converter.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "Decisions made" in result
        assert "flyback topology" in result

    def test_todos_parsed(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — \u2610 TODO\n"
            "Add snubber circuit to reduce ringing.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "Open TODOs" in result
        assert "snubber" in result

    def test_recommendations_parsed(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — \u2b50 RECOMMENDATION\n"
            "Use Wurth WE-FLEX for the transformer.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "Recommendations" in result
        assert "Wurth" in result

    def test_notes_parsed_not_wattio_header(self, tmp_project: Path) -> None:
        """Notes headers are parsed, but '— Wattio' headers are not."""
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — \U0001F4CC NOTE\n"
            "Important design consideration here.\n\n"
            "### 14:05 — Wattio\n"
            "This is just assistant text, should not be a note.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "Notes" in result
        assert "Important design consideration" in result

    def test_blockquotes_skipped(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — \u2705 DECISION\n"
            "> Tool call: `file_reader`\n"
            "Use forward topology.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "Tool call" not in result
        assert "forward topology" in result

    def test_json_fragments_skipped(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — \u2705 DECISION\n"
            '{\n'
            '"schematic_path": "test.asc"\n'
            '}\n'
            "Use buck topology.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "schematic_path" not in result
        assert "buck topology" in result

    def test_work_summaries(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — User\n"
            "Run simulation\n\n"
            "### 14:01 — Wattio\n"
            "The simulation shows the output voltage is stable at 12V with 50mV ripple.\n\n"
        )
        result = load_recent_diary(tmp_project)
        assert "Work done" in result
        assert "output voltage" in result

    def test_skip_filler_phrases(self, tmp_project: Path) -> None:
        diary_dir = tmp_project / "wattio" / "diary"
        (diary_dir / "2026-02-20.md").write_text(
            "# Diary\n\n"
            "### 14:00 — User\n"
            "Thanks\n\n"
            "### 14:01 — Wattio\n"
            "You're welcome! Let me know if you need anything else.\n\n"
        )
        result = load_recent_diary(tmp_project)
        # Filler phrases should be skipped, so no work summaries
        assert result == ""

    def test_max_diary_files(self, tmp_project: Path) -> None:
        """Only last MAX_DIARY_FILES files are processed, sorted by date."""
        diary_dir = tmp_project / "wattio" / "diary"
        for i in range(8):
            day = f"2026-02-{10 + i:02d}"
            (diary_dir / f"{day}.md").write_text(
                f"# Diary\n\n### 14:00 — \u2705 DECISION\nDecision from {day}.\n\n"
            )
        result = load_recent_diary(tmp_project)
        # Should only contain the last 5 days (2026-02-13 through 2026-02-17)
        assert "2026-02-17" in result
        assert "2026-02-13" in result
        # Earlier days should not be included
        assert "2026-02-10" not in result


class TestFlushCategory:
    def test_empty_body_no_append(self) -> None:
        decisions: list[str] = []
        todos: list[str] = []
        recs: list[str] = []
        notes: list[str] = []
        _flush_category("decision", [], "2026-01-01", decisions, todos, recs, notes)
        assert decisions == []

    def test_none_category_no_append(self) -> None:
        decisions: list[str] = []
        _flush_category(None, ["text"], "2026-01-01", decisions, [], [], [])
        assert decisions == []

    def test_decision_flush(self) -> None:
        decisions: list[str] = []
        _flush_category("decision", ["Use flyback"], "2026-01-01", decisions, [], [], [])
        assert len(decisions) == 1
        assert "(2026-01-01)" in decisions[0]
        assert "Use flyback" in decisions[0]

    def test_todo_flush(self) -> None:
        todos: list[str] = []
        _flush_category("todo", ["Add snubber"], "2026-01-01", [], todos, [], [])
        assert len(todos) == 1

    def test_recommendation_flush(self) -> None:
        recs: list[str] = []
        _flush_category("recommendation", ["Use Wurth"], "2026-01-01", [], [], recs, [])
        assert len(recs) == 1

    def test_note_flush(self) -> None:
        notes: list[str] = []
        _flush_category("note", ["Design note"], "2026-01-01", [], [], [], notes)
        assert len(notes) == 1
