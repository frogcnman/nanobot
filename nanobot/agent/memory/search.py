"""Memory search functionality (P2 level).

Implements:
- Semantic-free search using keyword grep on topic files
- Inject relevant memory into conversation context
- Lightweight, no additional dependencies required
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.memory.auto_consolidation import AutoMemoryStore
from nanobot.config.feature_gate import get_feature_gate
from nanobot.utils.helpers import safe_filename

# Feature gate
FEATURE_GATE_MEMORY_SEARCH = "memory_search"

# Default maximum results to inject
DEFAULT_MAX_SEARCH_RESULTS = 5
DEFAULT_MAX_CONTEXT_LINES = 20


def keyword_search(
    text: str,
    keywords: list[str],
    case_sensitive: bool = False,
) -> list[tuple[int, str]]:
    """Search for keywords in text, return matching lines with line numbers.

    Args:
        text: Text to search in.
        keywords: List of keywords to search for.
        case_sensitive: Whether matching should be case-sensitive.

    Returns:
        List of (line_number, line_content) for matching lines.
    """
    matches = []
    flags = 0 if case_sensitive else re.IGNORECASE

    for line_num, line in enumerate(text.splitlines(), 1):
        for keyword in keywords:
            pattern = re.compile(re.escape(keyword), flags)
            if pattern.search(line):
                matches.append((line_num, line))
                break

    return matches


def get_context_around_match(
    text: str,
    match_line: int,
    context_lines: int = 2,
) -> str:
    """Get context lines around a matching line.

    Args:
        text: Full text content.
        match_line: Line number of the match (1-indexed).
        context_lines: Number of lines to include before and after.

    Returns:
        The context snippet including the match and surrounding lines.
    """
    lines = text.splitlines()
    start = max(0, match_line - 1 - context_lines)
    end = min(len(lines), match_line + context_lines)
    return "\n".join(lines[start:end])


class MemorySearcher:
    """Search auto memory topics for relevant information.

    Lightweight search using simple keyword matching that works
    without any additional dependencies like vector databases.
    """

    def __init__(self, auto_memory: AutoMemoryStore):
        self.auto = auto_memory
        self._topic_cache: dict[str, str] = {}

    def _read_topic_cached(self, topic: str) -> str:
        """Read topic content with caching."""
        if topic in self._topic_cache:
            return self._topic_cache[topic]
        content = self.auto.read_topic(topic)
        self._topic_cache[topic] = content
        return content

    def invalidate_cache(self, topic: str | None = None) -> None:
        """Invalidate topic cache after updates."""
        if topic is None:
            self._topic_cache.clear()
        elif topic in self._topic_cache:
            del self._topic_cache[topic]

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_SEARCH_RESULTS,
        context_lines: int = 2,
    ) -> list[dict[str, Any]]:
        """Search auto memory for keywords in query.

        Args:
            query: Search query (extracts keywords from query text).
            max_results: Maximum number of results to return.
            context_lines: Number of context lines around each match.

        Returns:
            List of search results, each with topic, snippet, and score.
        """
        gate = get_feature_gate()
        if not gate.is_enabled(FEATURE_GATE_MEMORY_SEARCH, True):
            return []

        # Extract keywords from query (simple: split on whitespace, filter short)
        keywords = [kw.strip() for kw in query.split() if len(kw.strip()) >= 3]
        if not keywords:
            return []

        results: list[dict[str, Any]] = []

        # Search all topics
        topics = self.auto.index.list_topics()
        for topic in topics:
            content = self._read_topic_cached(topic)
            if not content:
                continue

            matches = keyword_search(content, keywords)
            if not matches:
                continue

            # Score by number of matches
            score = len(matches)

            # Get best match with context
            best_match = matches[0]
            snippet = get_context_around_match(content, best_match[0], context_lines)

            results.append({
                "topic": topic,
                "score": score,
                "snippet": snippet,
                "match_line": best_match[0],
                "matches": len(matches),
            })

        # Sort by score descending, take top N
        results.sort(key=lambda r: -r["score"])
        return results[:max_results]

    def search_and_format_context(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_SEARCH_RESULTS,
    ) -> str:
        """Search and format results for injection into context.

        Args:
            query: Search query from current user message.
            max_results: Maximum number of results.

        Returns:
            Formatted markdown context with relevant memory, empty if none.
        """
        results = self.search(query, max_results)
        if not results:
            return ""

        lines = ["## Relevant Memory from Past Conversations", ""]

        for idx, result in enumerate(results, 1):
            topic = result["topic"]
            snippet = result["snippet"]
            lines.append(f"### {idx}. {topic}")
            lines.append("```")
            lines.append(snippet.strip())
            lines.append("```")
            lines.append("")

        return "\n".join(lines)


def inject_relevant_memory(
    current_query: str,
    memory_dir: Path,
    max_results: int = DEFAULT_MAX_SEARCH_RESULTS,
) -> str:
    """Convenience function to search and get formatted relevant memory.

    Args:
        current_query: Current user query to find relevant memory for.
        memory_dir: Root memory directory (where auto/ is located).
        max_results: Maximum number of search results to include.

    Returns:
        Formatted context string to inject, empty if no results or disabled.
    """
    gate = get_feature_gate()
    if not gate.is_enabled(FEATURE_GATE_MEMORY_SEARCH, True):
        return ""

    auto_store = AutoMemoryStore(memory_dir)
    searcher = MemorySearcher(auto_store)
    return searcher.search_and_format_context(current_query, max_results)
