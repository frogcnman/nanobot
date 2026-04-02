"""Session Memory automatic compression for P0 level.

Implements:
- Token counting for session memory
- Compression threshold configuration (default: 5000 tokens / 3 tool calls)
- LLM-based conversation compression
- Replace original messages with compressed version
- Feature Gate toggle
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.config.feature_gate import get_feature_gate
from nanobot.utils.helpers import estimate_prompt_tokens

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider


# Default compression thresholds
DEFAULT_COMPRESSION_THRESHOLD_TOKENS = 5000
DEFAULT_COMPRESSION_THRESHOLD_TOOL_CALLS = 3
DEFAULT_COMPRESSION_MODEL_TOKENS = 1024

# Feature gate name
FEATURE_GATE_SESSION_COMPRESSION = "session_compression"

# Compression tool definition
COMPRESSION_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "deliver_compressed_summary",
            "description": "Deliver the compressed conversation summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "compressed_summary": {
                        "type": "string",
                        "description": "The compressed summary of the conversation so far. Keep all key decisions, user preferences, action items and important context.",
                    },
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of key points extracted from the conversation.",
                    },
                },
                "required": ["compressed_summary", "key_points"],
            },
        },
    }
]


def count_session_tokens(messages: list[dict[str, Any]]) -> int:
    """Count total tokens in session messages.

    Args:
        messages: List of session messages.

    Returns:
        Estimated token count.
    """
    return estimate_prompt_tokens(messages)


def should_compress(
    messages: list[dict[str, Any]],
    tool_calls_since_last: int,
    threshold_tokens: int = DEFAULT_COMPRESSION_THRESHOLD_TOKENS,
    threshold_tool_calls: int = DEFAULT_COMPRESSION_THRESHOLD_TOOL_CALLS,
) -> tuple[bool, int]:
    """Check if compression should be triggered.

    Triggers when either threshold is exceeded:
    - token count exceeds threshold_tokens
    - number of tool calls since last compression exceeds threshold_tool_calls

    Args:
        messages: Current session messages.
        tool_calls_since_last: Number of tool calls since last compression.
        threshold_tokens: Token threshold for compression.
        threshold_tool_calls: Tool call threshold for compression.

    Returns:
        Tuple of (should_compress, current_token_count).
    """
    current_tokens = count_session_tokens(messages)

    gate = get_feature_gate()
    if not gate.is_enabled(FEATURE_GATE_SESSION_COMPRESSION, True):
        return False, current_tokens

    if current_tokens >= threshold_tokens:
        logger.debug(
            "Compression triggered: token count {} exceeds threshold {}",
            current_tokens,
            threshold_tokens,
        )
        return True, current_tokens

    if tool_calls_since_last >= threshold_tool_calls:
        logger.debug(
            "Compression triggered: {} tool calls since last exceeds threshold {}",
            tool_calls_since_last,
            threshold_tool_calls,
        )
        return True, current_tokens

    return False, current_tokens


def _normalize_compression_args(args: Any) -> dict[str, Any] | None:
    """Normalize tool call arguments to expected dict shape."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return None

    if isinstance(args, list):
        return args[0] if args and isinstance(args[0], dict) else None

    return args if isinstance(args, dict) else None


async def compress_conversation(
    messages: list[dict[str, Any]],
    provider: LLMProvider,
    model: str,
    max_completion_tokens: int = DEFAULT_COMPRESSION_MODEL_TOKENS,
) -> dict[str, Any] | None:
    """Compress conversation using LLM.

    Calls LLM to generate a compressed summary that preserves all important
    information while reducing token count significantly.

    Args:
        messages: Original conversation messages to compress.
        provider: LLM provider to use.
        model: Model identifier.
        max_completion_tokens: Maximum tokens for compression output.

    Returns:
        Compressed message dict, or None if compression failed.
    """
    # Format conversation for the compressor
    formatted_lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if not content:
            continue

        tools_used = msg.get("tools_used", [])
        tool_suffix = f" [tools: {', '.join(tools_used)}]" if tools_used else ""

        timestamp = msg.get("timestamp", "")
        ts_prefix = f"[{timestamp[:16]}] " if timestamp else ""

        formatted_lines.append(f"{ts_prefix}{role.upper()}{tool_suffix}: {content}")

    conversation_text = "\n".join(formatted_lines)

    system_prompt = (
        "You are a conversation compression specialist. Your task is to compress "
        "the conversation history into a concise summary that preserves ALL key information:\n"
        "- User preferences and personal settings\n"
        "- Important decisions made\n"
        "- Action items and pending work\n"
        "- Key technical context and project information\n"
        "- Results of important tool calls\n\n"
        "Remove redundant interactions, duplicate explanations, and tangential "
        "conversations that don't affect the current context.\n"
        "Call the deliver_compressed_summary tool with your result."
    )

    user_prompt = f"""Compress this conversation:

{conversation_text}"""

    chat_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        forced = {"type": "function", "function": {"name": "deliver_compressed_summary"}}
        response = await provider.chat_with_retry(
            messages=chat_messages,
            tools=COMPRESSION_TOOL,
            model=model,
            tool_choice=forced,
            max_tokens=max_completion_tokens,
        )

        if response.finish_reason == "error" and "tool_choice" in (response.content or "").lower():
            logger.warning("Forced tool_choice unsupported, retrying with auto")
            response = await provider.chat_with_retry(
                messages=chat_messages,
                tools=COMPRESSION_TOOL,
                model=model,
                tool_choice="auto",
                max_tokens=max_completion_tokens,
            )

        if not response.has_tool_calls:
            logger.warning(
                "Compression: LLM did not call deliver_compressed_summary "
                "(finish_reason={}, content_len={})",
                response.finish_reason,
                len(response.content or ""),
            )
            return None

        args = _normalize_compression_args(response.tool_calls[0].arguments)
        if args is None:
            logger.warning("Compression: invalid arguments from LLM")
            return None

        if "compressed_summary" not in args:
            logger.warning("Compression: missing compressed_summary in result")
            return None

        compressed_summary = args.get("compressed_summary", "")
        key_points = args.get("key_points", [])

        if not compressed_summary:
            logger.warning("Compression: empty summary received")
            return None

        # Create compressed message entry
        compressed_msg = {
            "role": "system",
            "content": f"""## Compressed Conversation History

### Summary
{compressed_summary}

### Key Points
{chr(10).join(f'- {point}' for point in key_points) if key_points else '(none)'}

---
*This section is a compressed summary of earlier conversation to save tokens.*
""",
            "timestamp": datetime.now().isoformat(),
            "is_compressed": True,
            "original_message_count": len(messages),
            "original_tokens": count_session_tokens(messages),
        }

        compressed_tokens = count_session_tokens([compressed_msg])
        logger.info(
            "Conversation compression complete: {} messages / {} tokens → {} tokens "
            "(reduction: {:.1f}%)",
            len(messages),
            compressed_msg["original_tokens"],
            compressed_tokens,
            (1 - compressed_tokens / compressed_msg["original_tokens"]) * 100,
        )

        return compressed_msg

    except Exception:
        logger.exception("Conversation compression failed")
        return None


def replace_with_compressed(
    messages: list[dict[str, Any]],
    compressed_message: dict[str, Any],
) -> list[dict[str, Any]]:
    """Replace original messages with compressed version.

    Preserves the latest user message at the end for proper conversation flow.

    Args:
        messages: Original message list.
        compressed_message: Compressed summary message.

    Returns:
        New message list with compressed version at the beginning, followed by
        any uncompressed recent messages that should stay in context.
    """
    # Keep the compressed summary as system message
    new_messages = [compressed_message]

    # Find the last user message - we want to keep all messages from the
    # most recent user turn intact for the current conversation flow
    last_user_idx = -1
    for i in reversed(range(len(messages))):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    if last_user_idx >= 0:
        # Add everything from last user message onwards as-is
        new_messages.extend(messages[last_user_idx:])
    else:
        # If no user message found (unlikely), just keep the compressed summary
        pass

    return new_messages
