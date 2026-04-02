"""Security module for nanobot.

Inspired by Claude Code's two-stage YOLO classifier:
- Stage 1: Fast 64-token check, block anything suspicious
- Stage 2: Full 4096-token analysis for suspicious inputs
- Balances security, speed, and cost
"""

from nanobot.security.prompt_injection import (
    PromptInjectionDetector,
    TwoStagePromptInjectionDetector,
    DetectionResult,
)

__all__ = [
    "PromptInjectionDetector",
    "TwoStagePromptInjectionDetector",
    "DetectionResult",
]
