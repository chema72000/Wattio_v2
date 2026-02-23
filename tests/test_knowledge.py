"""Tests for curated knowledge search and the KnowledgeSearchTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattio.knowledge.curated import KnowledgeResult, search_curated, _extract_title
from wattio.tools.knowledge_search import KnowledgeSearchTool


# ── curated.py tests ────────────────────────────────────────────────


class TestSearchCurated:
    def test_keyword_match(self, tmp_project: Path) -> None:
        """Single keyword match returns result."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        (kb_dir / "derating.md").write_text(
            "# Derating Rules\nCapacitor voltage derating is 50%.\n"
        )
        results = search_curated(tmp_project, "derating")
        assert len(results) == 1
        assert results[0].title == "Derating Rules"
        assert results[0].score > 0

    def test_no_matches(self, tmp_project: Path) -> None:
        """Query that matches nothing returns empty."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        (kb_dir / "derating.md").write_text("# Derating\nCapacitor derating is 50%.\n")
        results = search_curated(tmp_project, "nonexistent_xyz_keyword")
        assert results == []

    def test_no_knowledge_dir(self, tmp_path: Path) -> None:
        """Missing knowledge directory returns empty."""
        results = search_curated(tmp_path, "anything")
        assert results == []

    def test_sorted_by_score(self, tmp_project: Path) -> None:
        """Results sorted by score descending."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        (kb_dir / "derating.md").write_text(
            "# Derating\nCapacitor derating 50%.\n"
        )
        (kb_dir / "vendors.md").write_text(
            "# Vendors\nPreferred vendor is Wurth. Capacitor vendor is TDK.\n"
        )
        # Query "capacitor" — both match, but "vendors" has "capacitor" and extra context
        results = search_curated(tmp_project, "capacitor vendor")
        assert len(results) >= 1
        # Vendors file has both terms, derating has only one
        assert results[0].file == "vendors.md"

    def test_max_results(self, tmp_project: Path) -> None:
        """max_results limits output."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        for i in range(5):
            (kb_dir / f"note_{i}.md").write_text(f"# Note {i}\nCommon keyword here.\n")
        results = search_curated(tmp_project, "keyword", max_results=2)
        assert len(results) <= 2

    def test_multiple_query_terms(self, tmp_project: Path) -> None:
        """Partial matching: file matching 2/3 terms scores higher than 1/3."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        (kb_dir / "full.md").write_text("# Full match\nalpha beta gamma\n")
        (kb_dir / "partial.md").write_text("# Partial match\nalpha only\n")
        results = search_curated(tmp_project, "alpha beta gamma")
        assert len(results) >= 2
        assert results[0].file == "full.md"
        assert results[0].score > results[1].score

    def test_case_insensitive(self, tmp_project: Path) -> None:
        """Search is case-insensitive."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        (kb_dir / "caps.md").write_text("# CAPACITOR Guide\nVoltage DERATING rules.\n")
        results = search_curated(tmp_project, "capacitor derating")
        assert len(results) == 1


class TestExtractTitle:
    def test_heading(self) -> None:
        assert _extract_title("# My Title\nBody text", "fallback") == "My Title"

    def test_fallback(self) -> None:
        assert _extract_title("No heading here", "my_file") == "my_file"

    def test_heading_with_whitespace(self) -> None:
        assert _extract_title("#   Spaced Title  \nBody", "f") == "Spaced Title"


# ── KnowledgeSearchTool tests ──────────────────────────────────────


@pytest.fixture
def ks_tool() -> KnowledgeSearchTool:
    return KnowledgeSearchTool()


class TestKnowledgeSearchTool:
    @pytest.mark.asyncio
    async def test_successful_search(self, tmp_project: Path, ks_tool: KnowledgeSearchTool) -> None:
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        (kb_dir / "derating.md").write_text("# Derating\nCapacitor derating 50%.\n")
        result = await ks_tool.execute(tmp_project, query="derating")
        assert not result.is_error
        assert "Derating" in result.content
        assert "derating.md" in result.content

    @pytest.mark.asyncio
    async def test_no_results(self, tmp_project: Path, ks_tool: KnowledgeSearchTool) -> None:
        result = await ks_tool.execute(tmp_project, query="nonexistent_xyz")
        assert not result.is_error
        assert "No matching curated knowledge" in result.content

    @pytest.mark.asyncio
    async def test_empty_query_error(self, tmp_project: Path, ks_tool: KnowledgeSearchTool) -> None:
        result = await ks_tool.execute(tmp_project, query="")
        assert result.is_error
        assert "required" in result.content.lower()

    @pytest.mark.asyncio
    async def test_long_content_truncated(self, tmp_project: Path, ks_tool: KnowledgeSearchTool) -> None:
        """Content longer than 1500 chars is truncated in tool output."""
        kb_dir = tmp_project / "wattio" / "knowledge" / "curated"
        long_content = "# Long Doc\n" + "word " * 500  # ~2500 chars
        (kb_dir / "long.md").write_text(long_content)
        result = await ks_tool.execute(tmp_project, query="word")
        assert not result.is_error
        # The raw content is >1500 chars but the snippet should be truncated
        assert len(result.content) < len(long_content)
