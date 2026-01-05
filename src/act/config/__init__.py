"""Configuration parsing and validation."""

from act.config.env import (
    DEFAULT_ARTIFACT_DIR,
    ENV_ANTHROPIC_API_KEY,
    ENV_ARTIFACT_DIR,
    ENV_LLM_BASE_URL,
    ENV_LLM_MODEL,
    ENV_OPENAI_API_KEY,
    EnvConfig,
    LLMBackend,
    LLMConfig,
    get_artifact_dir,
    get_llm_backend,
    has_llm_config,
    load_env_config,
)
from act.config.schema import (
    AgentConfig,
    ConfigError,
    ConfigParseError,
    ConfigValidationError,
    MonorepoConfig,
    TimeoutsConfig,
    VerificationConfig,
    VerificationStep,
    load_config,
    parse_config,
)
from act.config.validator import (
    StartupValidationError,
    ValidationResult,
    require_valid_startup,
    validate_startup,
)

__all__ = [
    # Schema types
    "AgentConfig",
    "VerificationConfig",
    "VerificationStep",
    "TimeoutsConfig",
    "MonorepoConfig",
    # Schema functions
    "parse_config",
    "load_config",
    # Schema errors
    "ConfigError",
    "ConfigParseError",
    "ConfigValidationError",
    # Environment types
    "EnvConfig",
    "LLMConfig",
    "LLMBackend",
    # Environment functions
    "load_env_config",
    "get_artifact_dir",
    "get_llm_backend",
    "has_llm_config",
    # Environment constants
    "ENV_ANTHROPIC_API_KEY",
    "ENV_OPENAI_API_KEY",
    "ENV_LLM_BASE_URL",
    "ENV_LLM_MODEL",
    "ENV_ARTIFACT_DIR",
    "DEFAULT_ARTIFACT_DIR",
    # Validation types
    "ValidationResult",
    # Validation functions
    "validate_startup",
    "require_valid_startup",
    # Validation errors
    "StartupValidationError",
]
