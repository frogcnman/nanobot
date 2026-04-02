"""Background auto-consolidation via subagent (P2 level).

Implements:
- Run consolidation in background sub-agent
- Doesn't block user interaction
- Updates memory after completion
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.memory.auto_consolidation import AutoConsolidator, AutoMemoryStore
from nanobot.agent.memory.versioning import git_commit
from nanobot.agent.subagent import SubagentManager
from nanobot.config.feature_gate import get_feature_gate

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from pathlib import Path

# Consolidation prompt template
CONSOLIDATION_PROMPT = """You are the nanobot automatic memory consolidation agent.

Your task: Process the accumulated new session content and organize it into
long-term auto memory by topic. Follow the four-phase process exactly:

## Phase 1: Orient (Analyze)
- Read through all the new conversation content
- Identify:
  - Key user preferences
  - Important decisions made
  - Project information and context
  - Action items and outcomes
  - Facts worth remembering for future conversations

## Phase 2: Gather (Group)
- Group the extracted information into topics
- Example topics:
  - user-preferences (personal preferences, settings, habits)
  - project-{name} (information about specific projects)
  - decisions (important decisions made)
  - contacts (people and their roles/relationships)
  - knowledge (general facts worth remembering)
- Create new topic files as needed

## Phase 3: Consolidate (Write)
- For each topic:
  - Read existing memory content
  - Merge new information with existing content
  - Remove duplicates
  - Restructure for clarity
  - Write back the updated content

## Phase 4: Prune (Cleanup)
- Remove information that is outdated or no longer relevant
- Remove redundant or duplicated information
- Keep memory clean and focused

Use the available file tools to read and write the memory files.

Working directory: {memory_dir}
"""

# Tools will already include standard file system tools
# Just run the sub-agent with the consolidation task


async def run_background_consolidation(
    auto_store: AutoMemoryStore,
    provider: LLMProvider,
    model: str,
    workspace_dir: Path,
) -> bool:
    """Run auto memory consolidation in background.

    Args:
        auto_store: Auto memory store instance.
        provider: LLM provider to use.
        model: Model identifier.
        workspace_dir: Workspace root directory.

    Returns:
        True if consolidation completed successfully.
    """
    gate = get_feature_gate()
    if not gate.is_enabled("auto_memory_background", True):
        logger.debug("Background consolidation disabled via feature gate")
        return False

    if not auto_store.acquire_exclusive_lock():
        logger.debug("Could not acquire consolidation lock, another process is running")
        return False

    try:
        # Get all topics that need consolidation
        topics_to_consolidate = auto_store.check_triggers()
        if not topics_to_consolidate:
            logger.debug("No topics need consolidation at this time")
            auto_store.release_exclusive_lock()
            return False

        logger.info(
            "Starting background consolidation for {} topics: {}",
            len(topics_to_consolidate),
            topics_to_consolidate,
        )

        # Build the prompt with current state
        memory_dir = str(auto_store.auto_dir)
        index_metadata = auto_store.index.get_all_metadata()

        prompt = CONSOLIDATION_PROMPT.format(memory_dir=memory_dir) + f"""

## Current State
Topics needing consolidation: {', '.join(topics_to_consolidate)}

Topic metadata:
{index_metadata}

Complete the four-phase consolidation now. When you are done, your work is complete.
"""

        # Run as subagent in background
        # User can continue interacting with main agent during this time
        from nanobot.bus import MessageBus
        bus = MessageBus()
        manager = SubagentManager(
            provider=provider,
            workspace=workspace_dir,
            bus=bus,
            model=model,
        )
        result = await manager.run_task(prompt)

        # Update metadata after consolidation
        auto_store.mark_consolidation_done(topics_to_consolidate)

        # Commit if git versioning is enabled
        if auto_store.is_git_versioning_enabled():
            commit_msg = f"Auto memory consolidation: {len(topics_to_consolidate)} topics updated"
            git_commit(auto_store.auto_dir, commit_msg)

        logger.info("Background consolidation completed: {}", result)
        return True

    except Exception:
        logger.exception("Background consolidation failed")
        return False
    finally:
        auto_store.release_exclusive_lock()


def schedule_background_consolidation(
    auto_store: AutoMemoryStore,
    provider: LLMProvider,
    model: str,
    workspace_dir: Path,
) -> None:
    """Schedule background consolidation to run async.

    Creates an asyncio task that runs in the background without blocking.

    Args:
        auto_store: Auto memory store.
        provider: LLM provider.
        model: Model identifier.
        workspace_dir: Workspace root.
    """
    gate = get_feature_gate()
    if not gate.is_enabled("auto_memory_background", True):
        return

    asyncio.create_task(
        run_background_consolidation(
            auto_store=auto_store,
            provider=provider,
            model=model,
            workspace_dir=workspace_dir,
        )
    )

    logger.debug("Background consolidation scheduled")
