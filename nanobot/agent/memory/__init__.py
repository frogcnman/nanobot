"""Two-layer memory system with automatic compression and consolidation.

P0: Session Memory automatic compression
P1: Auto Memory base consolidation
P2: Background consolidation + memory search
P3: Versioning + pruning

This is the complete upgrade following Claude Code architecture.
"""

# Re-export original MemoryStore from legacy location (../memory_legacy.py)
import sys
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "memory_legacy",
    Path(__file__).parent.parent / "memory_legacy.py"
)
memory_module = importlib.util.module_from_spec(spec)
sys.modules["memory_legacy"] = memory_module
spec.loader.exec_module(memory_module)

MemoryStore = memory_module.MemoryStore
MemoryConsolidator = memory_module.MemoryConsolidator

from nanobot.agent.memory.compression import (
    FEATURE_GATE_SESSION_COMPRESSION,
    count_session_tokens,
    should_compress,
    compress_conversation,
    replace_with_compressed,
    DEFAULT_COMPRESSION_THRESHOLD_TOKENS,
    DEFAULT_COMPRESSION_THRESHOLD_TOOL_CALLS,
)
from nanobot.agent.memory.auto_consolidation import (
    FEATURE_GATE_AUTO_MEMORY,
    FEATURE_GATE_AUTO_MEMORY_BACKGROUND,
    FEATURE_GATE_AUTO_MEMORY_GIT,
    AutoMemoryStore,
    AutoConsolidator,
    TopicIndex,
    FileLock,
    DEFAULT_MIN_HOURS_SINCE_LAST,
    DEFAULT_MIN_NEW_SESSIONS,
)
from nanobot.agent.memory.search import (
    FEATURE_GATE_MEMORY_SEARCH,
    MemorySearcher,
    inject_relevant_memory,
    keyword_search,
)
from nanobot.agent.memory.versioning import (
    git_commit,
    MemoryPruner,
    DEFAULT_PRUNE_AFTER_DAYS,
    DEFAULT_MIN_ENTRIES_TO_KEEP,
)
from nanobot.agent.memory.background import (
    run_background_consolidation,
    schedule_background_consolidation,
)

__all__ = [
    # Legacy: original memory store
    "MemoryStore",
    "MemoryConsolidator",
    # P0: Compression
    "FEATURE_GATE_SESSION_COMPRESSION",
    "count_session_tokens",
    "should_compress",
    "compress_conversation",
    "replace_with_compressed",
    "DEFAULT_COMPRESSION_THRESHOLD_TOKENS",
    "DEFAULT_COMPRESSION_THRESHOLD_TOOL_CALLS",
    # P1: Auto consolidation
    "FEATURE_GATE_AUTO_MEMORY",
    "FEATURE_GATE_AUTO_MEMORY_BACKGROUND",
    "FEATURE_GATE_AUTO_MEMORY_GIT",
    "AutoMemoryStore",
    "AutoConsolidator",
    "TopicIndex",
    "FileLock",
    "DEFAULT_MIN_HOURS_SINCE_LAST",
    "DEFAULT_MIN_NEW_SESSIONS",
    # P2: Search
    "FEATURE_GATE_MEMORY_SEARCH",
    "MemorySearcher",
    "inject_relevant_memory",
    "keyword_search",
    # Background consolidation
    "run_background_consolidation",
    "schedule_background_consolidation",
    # P3: Versioning + pruning
    "git_commit",
    "MemoryPruner",
    "DEFAULT_PRUNE_AFTER_DAYS",
    "DEFAULT_MIN_ENTRIES_TO_KEEP",
]
