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
        "Search curated design guides and knowledge base. "
        "MANDATORY for custom magnetic design — always call this FIRST when the engineer "
        "asks about Frenetic, core selection, winding design, or any custom transformer/inductor design. "
        "Also use for derating rules, design guidelines, or project-specific conventions. "
        "Returns complete step-by-step workflows and reference data."
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

        # Return the top match in full, and list other matches as titles
        # so the LLM can query them later (keeps context manageable)
        top = results[0]
        output = f"## {top.title} (from {top.file}, relevance: {top.score:.0%})\n\n{top.content}"

        if len(results) > 1:
            other_titles = "\n".join(
                f"- **{r.title}** ({r.file}, relevance: {r.score:.0%})"
                for r in results[1:]
            )
            output += (
                f"\n\n---\n\n**Other matching topics** (use `knowledge_search` "
                f"with a more specific query to retrieve):\n{other_titles}"
            )

        return ToolResult(
            tool_call_id="",
            content=output,
            keep_full=True,  # Knowledge guides must stay in full context
        )
