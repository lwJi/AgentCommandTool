"""Environment variable loading for deployment configuration."""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class LLMBackend(Enum):
    """Supported LLM backend types."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM backend configuration."""

    backend: LLMBackend
    api_key: str
    base_url: str | None = None
    model: str | None = None


@dataclass
class EnvConfig:
    """Environment-based configuration."""

    llm: LLMConfig | None
    artifact_dir: Path


# Environment variable names
ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_LLM_BASE_URL = "AGENT_LLM_BASE_URL"
ENV_LLM_MODEL = "AGENT_LLM_MODEL"
ENV_ARTIFACT_DIR = "AGENT_ARTIFACT_DIR"

# Default values
DEFAULT_ARTIFACT_DIR = Path.home() / ".agent-artifacts"


def _load_llm_config() -> LLMConfig | None:
    """Load LLM configuration from environment variables.

    Priority order:
    1. Custom endpoint (AGENT_LLM_BASE_URL + AGENT_LLM_MODEL)
    2. Anthropic (ANTHROPIC_API_KEY)
    3. OpenAI (OPENAI_API_KEY)

    Returns:
        LLMConfig if any LLM configuration is found, None otherwise.
    """
    base_url = os.environ.get(ENV_LLM_BASE_URL)
    model = os.environ.get(ENV_LLM_MODEL)
    anthropic_key = os.environ.get(ENV_ANTHROPIC_API_KEY)
    openai_key = os.environ.get(ENV_OPENAI_API_KEY)

    # Priority 1: Custom endpoint
    if base_url:
        # For custom endpoints, we need an API key from somewhere
        # Check for a generic key or fall back to existing keys
        api_key = anthropic_key or openai_key or ""
        return LLMConfig(
            backend=LLMBackend.CUSTOM,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    # Priority 2: Anthropic
    if anthropic_key:
        return LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key=anthropic_key,
            model=model,
        )

    # Priority 3: OpenAI
    if openai_key:
        return LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key=openai_key,
            model=model,
        )

    return None


def _load_artifact_dir() -> Path:
    """Load artifact directory from environment or use default.

    Returns:
        Path to artifact directory.
    """
    artifact_dir_str = os.environ.get(ENV_ARTIFACT_DIR)
    if artifact_dir_str:
        return Path(artifact_dir_str).expanduser()
    return DEFAULT_ARTIFACT_DIR


def load_env_config() -> EnvConfig:
    """Load all environment-based configuration.

    Returns:
        EnvConfig with LLM and artifact directory settings.
    """
    return EnvConfig(
        llm=_load_llm_config(),
        artifact_dir=_load_artifact_dir(),
    )


def get_llm_backend() -> LLMBackend | None:
    """Get the selected LLM backend type.

    Returns:
        The LLMBackend type if configured, None otherwise.
    """
    config = _load_llm_config()
    return config.backend if config else None


def get_artifact_dir() -> Path:
    """Get the configured artifact directory.

    Returns:
        Path to artifact directory.
    """
    return _load_artifact_dir()


def has_llm_config() -> bool:
    """Check if any LLM configuration is available.

    Returns:
        True if an LLM backend is configured.
    """
    return _load_llm_config() is not None
