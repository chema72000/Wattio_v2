"""Tool for searching the engineer's curated knowledge base."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattio.knowledge.curated import search_curated
from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class KnowledgeSearchTool(BaseTool):
    """Tool that the LLM can call to search curated knowledge files."""

    name = "knowledge_search"
    description = (
        "Search the engineer's curated design notes and knowledge base. "
        "Use this when answering technical questions about derating rules, "
        "preferred vendors, design guidelines, or project-specific conventions. "
        "Returns relevant excerpts from the engineer's markdown notes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query (keywords describing what you're looking for).",
            },
        },
        "required": ["query"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        if not query:
            return ToolResult(
                tool_call_id="",
                content="Error: query is required.",
                is_error=True,
            )

        results = search_curated(project_dir, query)

        if not results:
            return ToolResult(
                tool_call_id="",
                content="No matching curated knowledge found. You may answer from general knowledge, "
                        "but clearly state: 'From general knowledge (not from your curated notes).'",
            )

        output_parts = []
        for r in results:
            snippet = r.content[:1500] if len(r.content) > 1500 else r.content
            output_parts.append(
                f"## {r.title} (from {r.file}, relevance: {r.score:.0%})\n\n{snippet}"
            )

        return ToolResult(
            tool_call_id="",
            content="\n\n---\n\n".join(output_parts),
        )
