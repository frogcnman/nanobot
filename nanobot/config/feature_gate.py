"""Feature gate (toggles) for gradual rollout and A/B testing.

Inspired by Claude Code's engineering practice:
- 200+ feature gates in production
- Enable/disable features without full rollback
- Support gradual rollout and A/B testing
- Keep it lightweight, no complex infrastructure needed
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class FeatureGateConfig(BaseModel):
    """Feature gate configuration stored in config.yaml."""
    enabled: dict[str, bool] = Field(default_factory=dict)
    """Mapping of feature name -> enabled/disabled."""

    def is_enabled(self, name: str, default: bool = False) -> bool:
        """Check if a feature is enabled."""
        return self.enabled.get(name, default)

    def get(self, name: str, default: Any = None) -> Any:
        """Get a feature gate value (supports bool or any other type)."""
        return self.enabled.get(name, default)


class FeatureGate:
    """Runtime feature gate manager.

    Lightweight implementation (~50 lines) that keeps nanobot lightweight.
    """

    def __init__(self, config: Optional[FeatureGateConfig] = None):
        self._config = config or FeatureGateConfig()

    def is_enabled(self, name: str, default: bool = False) -> bool:
        """Check if a feature is enabled."""
        return self._config.is_enabled(name, default)

    def get(self, name: str, default: Any = None) -> Any:
        """Get a feature gate value."""
        return self._config.get(name, default)

    def set_enabled(self, name: str, enabled: bool) -> None:
        """Set a feature gate at runtime."""
        self._config.enabled[name] = enabled

    def list_features(self) -> list[str]:
        """List all configured feature names."""
        return list(self._config.enabled.keys())


# Default instance for use throughout the codebase
_default_gate = FeatureGate()


def get_feature_gate() -> FeatureGate:
    """Get the global feature gate instance."""
    return _default_gate


def init_feature_gate(config: FeatureGateConfig) -> None:
    """Initialize the global feature gate from config."""
    global _default_gate
    _default_gate = FeatureGate(config)
