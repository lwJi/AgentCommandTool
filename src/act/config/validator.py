"""Startup validation for the AgentCommandTool system."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from act.config.env import has_llm_config
from act.config.schema import AgentConfig, ConfigError, load_config


class StartupValidationError(Exception):
    """Error during startup validation."""

    pass


@dataclass
class ValidationResult:
    """Result of startup validation."""

    valid: bool
    config: AgentConfig | None
    errors: list[str]


AGENT_YAML_FILENAME = "agent.yaml"


def _check_agent_yaml_exists(repo_root: Path) -> tuple[bool, str | None]:
    """Check if agent.yaml exists in the repository root.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Tuple of (exists, error_message).
    """
    config_path = repo_root / AGENT_YAML_FILENAME
    if not config_path.exists():
        return (
            False,
            f"Configuration required: {AGENT_YAML_FILENAME} not found in {repo_root}",
        )
    return True, None


def _check_llm_config() -> tuple[bool, str | None]:
    """Check if LLM configuration is available.

    Returns:
        Tuple of (configured, error_message).
    """
    if not has_llm_config():
        return False, (
            "Cannot proceed without model access: "
            "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or AGENT_LLM_BASE_URL"
        )
    return True, None


def _check_docker_available() -> tuple[bool, str | None]:
    """Check if Docker is available and running.

    Returns:
        Tuple of (available, error_message).
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, "Docker is not available or not running. Please start Docker."
        return True, None
    except FileNotFoundError:
        return (
            False,
            "Docker is not installed. Please install Docker to use verification.",
        )
    except subprocess.TimeoutExpired:
        return False, "Docker is not responding. Please check Docker status."
    except subprocess.SubprocessError as e:
        return False, f"Failed to check Docker status: {e}"


def _validate_config(repo_root: Path) -> tuple[AgentConfig | None, str | None]:
    """Load and validate the agent.yaml configuration.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Tuple of (config, error_message).
    """
    config_path = repo_root / AGENT_YAML_FILENAME
    try:
        config = load_config(config_path)
        return config, None
    except ConfigError as e:
        return None, str(e)


def validate_startup(
    repo_root: Path,
    check_docker: bool = True,
) -> ValidationResult:
    """Perform startup validation checks.

    Validates:
    1. agent.yaml exists
    2. agent.yaml is valid and has required fields
    3. At least one verification step is defined
    4. LLM API key is present
    5. Docker is available (optional)

    Args:
        repo_root: Path to the repository root.
        check_docker: Whether to check Docker availability.

    Returns:
        ValidationResult with validation status.
    """
    errors: list[str] = []
    config: AgentConfig | None = None

    # Check 1: agent.yaml exists
    exists, error = _check_agent_yaml_exists(repo_root)
    if not exists:
        errors.append(error or "Configuration file not found")
    else:
        # Check 2 & 3: Valid config with at least one step
        config, error = _validate_config(repo_root)
        if error:
            errors.append(error)

    # Check 4: LLM configuration
    has_llm, error = _check_llm_config()
    if not has_llm:
        errors.append(error or "LLM configuration missing")

    # Check 5: Docker availability (optional)
    if check_docker:
        docker_ok, error = _check_docker_available()
        if not docker_ok:
            errors.append(error or "Docker not available")

    return ValidationResult(
        valid=len(errors) == 0,
        config=config,
        errors=errors,
    )


def require_valid_startup(
    repo_root: Path,
    check_docker: bool = True,
) -> AgentConfig:
    """Validate startup and raise an exception if validation fails.

    Args:
        repo_root: Path to the repository root.
        check_docker: Whether to check Docker availability.

    Returns:
        Validated AgentConfig.

    Raises:
        StartupValidationError: If validation fails.
    """
    result = validate_startup(repo_root, check_docker)

    if not result.valid:
        error_msg = "Startup validation failed:\n" + "\n".join(
            f"  - {e}" for e in result.errors
        )
        raise StartupValidationError(error_msg)

    if result.config is None:
        raise StartupValidationError("Configuration is missing after validation")

    return result.config
