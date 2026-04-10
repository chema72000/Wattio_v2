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


def _knowledge_dirs(project_dir: Path) -> list[Path]:
    """Return all curated knowledge directories to search.

    Searches both the project working directory and the package's built-in
    knowledge directory so curated guides are always available regardless of
    where the user runs Wattio from.
    """
    dirs: list[Path] = []
    # Project-local knowledge (engineer's own notes)
    project_knowledge = project_dir / "wattio" / "knowledge" / "curated"
    if project_knowledge.is_dir():
        dirs.append(project_knowledge)
    # Built-in package knowledge (installed with Wattio)
    package_knowledge = Path(__file__).parent / "curated"
    if package_knowledge.is_dir() and package_knowledge != project_knowledge:
        dirs.append(package_knowledge)
    return dirs


def search_curated(project_dir: Path, query: str, max_results: int = 3) -> list[KnowledgeResult]:
    """Search curated markdown files for relevant content.

    Uses simple keyword matching. A future version may use embeddings/RAG.
    """
    knowledge_dirs = _knowledge_dirs(project_dir)
    if not knowledge_dirs:
        return []

    query_terms = set(query.lower().split())
    results: list[KnowledgeResult] = []
    seen_files: set[str] = set()

    for knowledge_dir in knowledge_dirs:
        for md_file in knowledge_dir.glob("*.md"):
            # Avoid duplicates if same file exists in both dirs
            if md_file.name in seen_files:
                continue
            seen_files.add(md_file.name)

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
