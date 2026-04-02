"""Auto Memory consolidation (P1-P3 level).

Implements:
- Storage structure: memory/auto/{topic}.md
- Trigger condition detection (24h + 5 sessions)
- Four-phase framework: Orient → Gather → Consolidate → Prune
- File-based exclusive locking
- Configuration via feature gates
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from nanobot.config.feature_gate import get_feature_gate
from nanobot.utils.helpers import ensure_dir, safe_filename

# Feature gate names
FEATURE_GATE_AUTO_MEMORY = "auto_memory"
FEATURE_GATE_AUTO_MEMORY_BACKGROUND = "auto_memory_background"
FEATURE_GATE_AUTO_MEMORY_GIT = "auto_memory_git_versioning"

# Default configuration
DEFAULT_MIN_HOURS_SINCE_LAST = 24
DEFAULT_MIN_NEW_SESSIONS = 5
LOCK_TIMEOUT_HOURS = 2  # Lock expires after 2 hours

# Storage paths
AUTO_MEMORY_DIR = "auto"
TOPIC_INDEX_NAME = "index.json"

# File lock paths
LOCK_FILE = "consolidation.lock"


class TopicIndex:
    """Topic index for auto memory.

    Maintains metadata about all memory topics:
    - last consolidation time
    - number of new sessions since last consolidation
    - file paths
    """

    def __init__(self, auto_dir: Path):
        self.auto_dir = auto_dir
        self.index_path = auto_dir / TOPIC_INDEX_NAME
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load index from disk."""
        if self.index_path.exists():
            try:
                self._data = json.loads(self.index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Failed to load topic index, starting fresh")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Save index to disk."""
        self.index_path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_topic_metadata(self, topic: str) -> dict[str, Any]:
        """Get metadata for a topic, creating default if not exists."""
        if topic not in self._data:
            self._data[topic] = {
                "created_at": datetime.now().isoformat(),
                "last_consolidation_at": None,
                "new_sessions_since_last": 0,
                "topic": topic,
                "file_path": f"{safe_filename(topic)}.md",
            }
        return self._data[topic]

    def increment_new_session(self, topic: str) -> None:
        """Increment new session counter for a topic."""
        meta = self.get_topic_metadata(topic)
        meta["new_sessions_since_last"] = meta.get("new_sessions_since_last", 0) + 1
        self._save()

    def update_last_consolidation(self, topic: str) -> None:
        """Update last consolidation timestamp and reset counter."""
        meta = self.get_topic_metadata(topic)
        meta["last_consolidation_at"] = datetime.now().isoformat()
        meta["new_sessions_since_last"] = 0
        self._save()

    def list_topics(self) -> list[str]:
        """List all topic names in index."""
        return list(self._data.keys())

    def get_all_metadata(self) -> dict[str, Any]:
        """Get all metadata."""
        return self._data


class FileLock:
    """Simple file-based exclusive lock for consolidation.

    Prevents multiple processes from running consolidation concurrently.
    Uses timestamp-based expiration to handle crashed processes.
    """

    def __init__(self, lock_path: Path, timeout_hours: float = LOCK_TIMEOUT_HOURS):
        self.lock_path = lock_path
        self.timeout_hours = timeout_hours
        self._locked = False

    def acquire(self) -> bool:
        """Try to acquire the lock. Returns True if acquired."""
        if self.lock_path.exists():
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                acquired_at = datetime.fromisoformat(data.get("acquired_at", ""))
                age = (datetime.now() - acquired_at).total_seconds() / 3600
                if age < self.timeout_hours:
                    # Lock is still valid
                    logger.debug("Consolidation lock already held, acquired {} hours ago", age)
                    return False
                # Lock expired, we can take it
                logger.warning("Consolidation lock expired, overwriting")
            except Exception:
                # Corrupt lock file, ignore
                pass

        # Create new lock
        try:
            self.lock_path.write_text(
                json.dumps({
                    "acquired_at": datetime.now().isoformat(),
                    "pid": str(time.time()),
                }, indent=2),
                encoding="utf-8",
            )
            self._locked = True
            return True
        except Exception:
            logger.exception("Failed to create lock")
            return False

    def release(self) -> None:
        """Release the lock."""
        if self._locked and self.lock_path.exists():
            try:
                self.lock_path.unlink()
            except Exception:
                logger.warning("Failed to release consolidation lock")
        self._locked = False

    def __enter__(self) -> bool:
        """Context manager entry."""
        acquired = self.acquire()
        if not acquired:
            return False
        return True

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()


class AutoMemoryStore:
    """Storage for auto memory system.

    Storage structure:
    memory/
      auto/
        {topic}.md  -> one file per topic
        index.json  -> topic index metadata
        consolidation.lock -> lock for concurrent consolidation
    """

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.auto_dir = ensure_dir(memory_dir / AUTO_MEMORY_DIR)
        self.index = TopicIndex(self.auto_dir)
        self.lock_path = self.auto_dir / LOCK_FILE
        self._lock = FileLock(self.lock_path)

    def get_topic_path(self, topic: str) -> Path:
        """Get the file path for a topic."""
        filename = safe_filename(topic) + ".md"
        return self.auto_dir / filename

    def read_topic(self, topic: str) -> str:
        """Read content of a topic memory file."""
        path = self.get_topic_path(topic)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_topic(self, topic: str, content: str) -> None:
        """Write content to a topic memory file."""
        path = self.get_topic_path(topic)
        path.write_text(content.strip() + "\n", encoding="utf-8")

    def append_entry(
        self,
        topic: str,
        entry: str,
        header: str | None = None,
    ) -> None:
        """Append a new entry to an existing topic.

        Preserves existing content, adds new entry with timestamp.
        """
        existing = self.read_topic(topic).rstrip()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        if existing:
            new_content = f"{existing}\n\n---\n[{ts}] {entry}"
        else:
            if header:
                new_content = f"# {header}\n\n[{ts}] {entry}"
            else:
                new_content = f"# {topic}\n\n[{ts}] {entry}"
        self.write_topic(topic, new_content)

    def acquire_lock(self) -> bool:
        """Acquire the consolidation lock."""
        return self._lock.acquire()

    def release_lock(self) -> None:
        """Release the consolidation lock."""
        self._lock.release()

    def should_consolidate(
        self,
        topic: str,
        min_hours: float = DEFAULT_MIN_HOURS_SINCE_LAST,
        min_sessions: int = DEFAULT_MIN_NEW_SESSIONS,
    ) -> bool:
        """Check if consolidation should run for this topic.

        Requires both conditions:
        1. More than min_hours since last consolidation
        2. More than min_sessions new sessions accumulated

        Args:
            topic: Topic name to check.
            min_hours: Minimum hours since last consolidation.
            min_sessions: Minimum number of new sessions.

        Returns:
            True if consolidation should run.
        """
        gate = get_feature_gate()
        if not gate.is_enabled(FEATURE_GATE_AUTO_MEMORY, False):
            return False

        meta = self.index.get_topic_metadata(topic)
        last_consolidation = meta.get("last_consolidation_at")
        new_sessions = meta.get("new_sessions_since_last", 0)

        # Never consolidated before -> should consolidate if we have enough sessions
        if last_consolidation is None:
            return new_sessions >= min_sessions

        # Check time elapsed
        try:
            last_dt = datetime.fromisoformat(last_consolidation)
            elapsed_hours = (datetime.now() - last_dt).total_seconds() / 3600
        except ValueError:
            elapsed_hours = 999

        # Both conditions must be satisfied
        if elapsed_hours < min_hours:
            return False
        if new_sessions < min_sessions:
            return False

        return True

    def list_all_should_consolidate(
        self,
        min_hours: float = DEFAULT_MIN_HOURS_SINCE_LAST,
        min_sessions: int = DEFAULT_MIN_NEW_SESSIONS,
    ) -> list[str]:
        """List all topics that need consolidation.

        Returns:
            List of topic names that need consolidation.
        """
        topics = []
        for topic in self.index.list_topics():
            if self.should_consolidate(topic, min_hours, min_sessions):
                topics.append(topic)
        return topics


class ConsolidationPhase:
    """Base class for consolidation phases."""

    phase_name: Literal["orient", "gather", "consolidate", "prune"]

    def __init__(self):
        pass


class AutoConsolidator:
    """Four-phase auto memory consolidation.

    Phase 1: Orient → Analyze new sessions, identify key information
    Phase 2: Gather → Extract content and group by topic
    Phase 3: Consolidate → Merge into memory files
    Phase 4: Prune → Remove outdated information
    """

    def __init__(
        self,
        memory_dir: Path,
        min_hours: float = DEFAULT_MIN_HOURS_SINCE_LAST,
        min_sessions: int = DEFAULT_MIN_NEW_SESSIONS,
    ):
        self.store = AutoMemoryStore(memory_dir)
        self.min_hours = min_hours
        self.min_sessions = min_sessions

    def check_triggers(self) -> list[str]:
        """Check all topics and return those that need consolidation."""
        return self.store.list_all_should_consolidate(self.min_hours, self.min_sessions)

    def acquire_exclusive_lock(self) -> bool:
        """Acquire exclusive lock for consolidation."""
        gate = get_feature_gate()
        if not gate.is_enabled(FEATURE_GATE_AUTO_MEMORY, False):
            return False
        return self.store.acquire_lock()

    def release_exclusive_lock(self) -> None:
        """Release the consolidation lock."""
        self.store.release_lock()

    def count_new_sessions(self, topics: list[str]) -> None:
        """Increment new session counter for each touched topic."""
        for topic in topics:
            self.store.index.increment_new_session(topic)

    def mark_consolidation_done(self, topics: list[str]) -> None:
        """Mark consolidation complete for these topics."""
        for topic in topics:
            self.store.index.update_last_consolidation(topic)

    # Git versioning enabled
    def is_git_versioning_enabled(self) -> bool:
        """Check if git versioning is enabled via feature gate."""
        gate = get_feature_gate()
        return gate.is_enabled(FEATURE_GATE_AUTO_MEMORY_GIT, False)
