"""Load recent diary entries to give the agent memory of past sessions."""

from __future__ import annotations

from pathlib import Path

MAX_DIARY_FILES = 5  # Look at the last 5 days max


def load_recent_diary(project_dir: Path) -> str:
    """Read recent diary entries and return a structured summary.

    Extracts only actionable items: decisions, TODOs, recommendations, notes,
    and key work done. Skips conversational fluff and tool call details.
    """
    diary_dir = project_dir / "wattio" / "diary"
    if not diary_dir.is_dir():
        return ""

    md_files = sorted(diary_dir.glob("*.md"), reverse=True)[:MAX_DIARY_FILES]
    if not md_files:
        return ""

    all_decisions: list[str] = []
    all_todos: list[str] = []
    all_recommendations: list[str] = []
    all_notes: list[str] = []
    work_summaries: list[str] = []

    for md_file in md_files:
        date_str = md_file.stem
        content = md_file.read_text(encoding="utf-8", errors="replace")
        _extract_from_diary(
            content, date_str,
            all_decisions, all_todos, all_recommendations, all_notes,
            work_summaries,
        )

    if not any([all_decisions, all_todos, all_recommendations, all_notes, work_summaries]):
        return ""

    parts: list[str] = []

    if all_decisions:
        parts.append("### Decisions made\n" + "\n".join(f"- {d}" for d in all_decisions))

    if all_todos:
        parts.append("### Open TODOs\n" + "\n".join(f"- [ ] {t}" for t in all_todos))

    if all_recommendations:
        parts.append("### Recommendations\n" + "\n".join(f"- {r}" for r in all_recommendations))

    if all_notes:
        parts.append("### Notes\n" + "\n".join(f"- {n}" for n in all_notes))

    if work_summaries:
        parts.append("### Work done\n" + "\n".join(f"- {w}" for w in work_summaries))

    return "\n\n".join(parts)


def _extract_from_diary(
    content: str,
    date_str: str,
    decisions: list[str],
    todos: list[str],
    recommendations: list[str],
    notes: list[str],
    work_summaries: list[str],
) -> None:
    """Parse a single diary file and append findings to the lists."""
    lines = content.splitlines()
    current_category: str | None = None
    current_body: list[str] = []
    last_user_request: str | None = None
    found_wattio_response = False

    for line in lines:
        # Skip blockquotes and JSON fragments
        if line.startswith(">"):
            continue
        stripped = line.strip()
        if stripped in ("{", "}") or (
            stripped.startswith('"') and (stripped.endswith(',') or stripped.endswith('"'))
        ):
            continue

        # Detect category headers
        if "DECISION" in line and line.startswith("### "):
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = "decision"
            current_body = []
            continue

        if "TODO" in line and line.startswith("### "):
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = "todo"
            current_body = []
            continue

        if "RECOMMENDATION" in line and line.startswith("### "):
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = "recommendation"
            current_body = []
            continue

        if "NOTE" in line and line.startswith("### ") and "— Wattio" not in line:
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = "note"
            current_body = []
            continue

        # Detect user/wattio sections (end any current category)
        if line.startswith("### ") and "— User" in line:
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = None
            current_body = []
            last_user_request = None
            found_wattio_response = False
            continue

        if line.startswith("### ") and "— Wattio" in line:
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = None
            current_body = []
            found_wattio_response = True
            continue

        if line.startswith("## ") or line.startswith("# "):
            _flush_category(current_category, current_body, date_str,
                            decisions, todos, recommendations, notes)
            current_category = None
            current_body = []
            continue

        # Collect body text
        if current_category:
            if stripped:
                current_body.append(stripped)
        elif not found_wattio_response and last_user_request is None and stripped:
            # First non-empty line after a User header = the user's request
            last_user_request = stripped
        elif found_wattio_response and stripped:
            # Capture meaningful Wattio responses as work summaries,
            # but skip filler and lines that just repeat decisions/todos
            skip_phrases = [
                "you're welcome", "goodbye", "if you need",
                "check the diary", "diary entry", "feel free",
                "let me know", "i've recorded", "i have recorded",
                "a decision was made", "additionally, there",
            ]
            if (
                len(stripped) > 20
                and not any(p in stripped.lower() for p in skip_phrases)
            ):
                work_summaries.append(f"({date_str}) {stripped}")
                found_wattio_response = False  # Only capture first meaningful line

    # Flush remaining
    _flush_category(current_category, current_body, date_str,
                    decisions, todos, recommendations, notes)


def _flush_category(
    category: str | None,
    body: list[str],
    date_str: str,
    decisions: list[str],
    todos: list[str],
    recommendations: list[str],
    notes: list[str],
) -> None:
    """Append collected body to the right list."""
    if not category or not body:
        return
    text = f"({date_str}) " + " ".join(body)
    if category == "decision":
        decisions.append(text)
    elif category == "todo":
        todos.append(text)
    elif category == "recommendation":
        recommendations.append(text)
    elif category == "note":
        notes.append(text)
