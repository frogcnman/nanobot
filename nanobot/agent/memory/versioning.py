"""Git versioning and pruning for auto memory (P3 level).

Implements:
- git versioning for memory files
- automatic pruning of stale/expired memory
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.memory.auto_consolidation import AutoMemoryStore
from nanobot.config.feature_gate import get_feature_gate

# Default pruning settings
DEFAULT_PRUNE_AFTER_DAYS = 180  # Remove stale entries after 6 months
DEFAULT_MIN_ENTRIES_TO_KEEP = 5  # Keep at least this many entries


def is_git_repo(path: Path) -> bool:
    """Check if the directory is in a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def git_commit(
    auto_memory_dir: Path,
    message: str,
) -> bool:
    """Commit all auto memory changes to git.

    Args:
        auto_memory_dir: Path to auto memory directory.
        message: Commit message.

    Returns:
        True if commit succeeded or not needed.
    """
    gate = get_feature_gate()
    if not gate.is_enabled("auto_memory_git_versioning", False):
        return True  # Not enabled, treated as success

    # Check if git is available and repo exists
    root_dir = auto_memory_dir.parent.parent  # Go up to workspace root
    if not is_git_repo(root_dir):
        logger.debug("Git versioning enabled but workspace is not a git repo")
        return False

    try:
        # Add changed files
        add_result = subprocess.run(
            ["git", "add", str(auto_memory_dir)],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info("Auto memory committed to git: {}", result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in e.stdout:
            logger.debug("Git: nothing to commit")
            return True
        logger.warning("Git commit failed: {}", e.stderr)
        return False


def parse_entry_timestamp(line: str) -> datetime | None:
    """Extract timestamp from an entry line like "[YYYY-MM-DD HH:MM] ..."."""
    if not line.startswith("["):
        return None

    # Find the closing bracket
    close_idx = line.find("]")
    if close_idx < 12:  # Need at least "[YYYY-MM-DD HH:MM"
        return None

    ts_str = line[1:close_idx]
    try:
        # Try full datetime format
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d")
        except ValueError:
            return None


class MemoryPruner:
    """Automatic pruning of outdated memory entries.

    Removes entries older than a certain age while keeping a minimum
    number of recent entries.
    """

    def __init__(
        self,
        auto_memory: AutoMemoryStore,
        prune_after_days: int = DEFAULT_PRUNE_AFTER_DAYS,
        min_entries_to_keep: int = DEFAULT_MIN_ENTRIES_TO_KEEP,
    ):
        self.auto = auto_memory
        self.prune_after_days = prune_after_days
        self.min_entries_to_keep = min_entries_to_keep

    def filter_outdated_entries(self, content: str) -> str:
        """Filter out outdated entries from topic content.

        Keeps all entries newer than prune_after_days, and ensures
        at least min_entries_to_keep are retained even if older.

        Args:
            content: Original topic content.

        Returns:
            Filtered content with outdated entries removed.
        """
        lines = content.splitlines()
        entries: list[tuple[datetime | None, list[str]]] = []

        current_entry_lines: list[str] = []
        current_entry_date: datetime | None = None

        for line in lines:
            line = line.rstrip()

            # New entry starts with a timestamp bracket
            if line.startswith("[") and "---" not in line:
                # Save previous entry if we have one
                if current_entry_lines:
                    entries.append((current_entry_date, current_entry_lines))
                    current_entry_lines = []

                current_entry_date = parse_entry_timestamp(line)

            current_entry_lines.append(line)

        # Add last entry
        if current_entry_lines:
            entries.append((current_entry_date, current_entry_lines))

        # If we don't have many entries, keep everything
        if len(entries) <= self.min_entries_to_keep:
            return content

        # Sort entries by date (oldest first)
        entries_with_dates = [
            (date, lines) for date, lines in entries if date is not None
        ]
        entries_with_dates.sort(key=lambda x: x[0] if x[0] else datetime.min)

        # Calculate cutoff date
        cutoff = datetime.now() - timedelta(days=self.prune_after_days)

        # Keep entries that are:
        # 1. Newer than cutoff, OR
        # 2. Within the min_entries_to_keep most recent regardless of age
        kept: list[list[str]] = []
        recent_cutoff = len(entries_with_dates) - self.min_entries_to_keep

        for idx, (date, lines) in enumerate(entries_with_dates):
            keep = False

            if date is None:
                # Can't date, keep it to be safe
                keep = True
            elif idx >= recent_cutoff:
                # In most recent block, always keep
                keep = True
            elif date >= cutoff:
                # New enough, keep
                keep = True

            if keep:
                kept.append(lines)

        # Check if anything was pruned
        pruned_count = len(entries_with_dates) - len(kept)
        if pruned_count > 0:
            logger.info("Pruned {} outdated entries", pruned_count)

        # Reconstruct content
        result_lines: list[str] = []

        # Keep header at top if it's not an entry
        header_lines: list[str] = []
        found_first_entry = False
        for line in lines:
            if not found_first_entry and line.startswith("# "):
                header_lines.append(line)
            elif not found_first_entry and not line.strip():
                header_lines.append(line)
            else:
                found_first_entry = True
                break

        result_lines.extend(header_lines)

        # Add kept entries with separator
        first_entry = True
        for entry_lines in kept:
            if not first_entry:
                result_lines.append("---")
            result_lines.extend(entry_lines)
            first_entry = False

        return "\n".join(result_lines)

    def prune_topic(self, topic: str) -> bool:
        """Prune outdated entries from a single topic.

        Args:
            topic: Topic name to prune.

        Returns:
            True if changes were made, False otherwise.
        """
        gate = get_feature_gate()
        if not gate.is_enabled("auto_memory_pruning", True):
            return False

        content = self.auto.read_topic(topic)
        if not content:
            return False

        filtered = self.filter_outdated_entries(content)
        if filtered.strip() == content.strip():
            return False

        self.auto.write_topic(topic, filtered)
        logger.info("Pruned outdated entries from topic '{}'", topic)
        return True

    def prune_all_topics(self) -> int:
        """Prune outdated entries from all topics.

        Returns:
            Number of topics that were pruned.
        """
        pruned = 0
        for topic in self.auto.index.list_topics():
            if self.prune_topic(topic):
                pruned += 1
        return pruned
