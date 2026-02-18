"""Search engineer's curated markdown files in wattio/knowledge/curated/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class KnowledgeResult:
    """A matching snippet from a curated knowledge file."""
    file: str
    title: str
    content: str
    score: float  # Simple relevance score (0-1)


def search_curated(project_dir: Path, query: str, max_results: int = 3) -> list[KnowledgeResult]:
    """Search curated markdown files for relevant content.

    Uses simple keyword matching. A future version may use embeddings/RAG.
    """
    knowledge_dir = project_dir / "wattio" / "knowledge" / "curated"
    if not knowledge_dir.is_dir():
        return []

    query_terms = set(query.lower().split())
    results: list[KnowledgeResult] = []

    for md_file in knowledge_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        title = _extract_title(content, md_file.stem)

        # Simple keyword scoring
        content_lower = content.lower()
        matches = sum(1 for term in query_terms if term in content_lower)
        if matches == 0:
            continue

        score = matches / len(query_terms)
        results.append(KnowledgeResult(
            file=md_file.name,
            title=title,
            content=content,
            score=score,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:max_results]


def _extract_title(content: str, fallback: str) -> str:
    """Extract the first markdown heading, or use the filename."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
