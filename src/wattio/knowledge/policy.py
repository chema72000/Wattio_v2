"""Knowledge routing logic — decides where to look for answers.

The KnowledgeSearchTool lives in tools/knowledge_search.py for auto-discovery.
This module contains the policy enum for future routing logic.
"""

from __future__ import annotations

from enum import Enum


class QuestionType(str, Enum):
    """Classification of user questions for knowledge routing."""
    CALCULATION = "calculation"   # Must use tools/code, never guess
    TECHNICAL = "technical"       # Curated sources first, flag LLM fallback
    GENERAL = "general"           # LLM responds freely
