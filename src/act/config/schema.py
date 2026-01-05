"""YAML schema validation for agent.yaml configuration files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Base exception for configuration errors."""

    pass


class ConfigParseError(ConfigError):
    """Error parsing YAML configuration."""

    pass


class ConfigValidationError(ConfigError):
    """Error validating configuration schema."""

    pass


@dataclass
class VerificationStep:
    """A single verification step configuration."""

    name: str
    command: str


@dataclass
class VerificationConfig:
    """Verification pipeline configuration."""

    container_image: str
    steps: list[VerificationStep]


@dataclass
class TimeoutsConfig:
    """Timeout configuration."""

    verification_step: int = 300000  # 5 minutes in ms
    scout_query: int = 60000  # 1 minute in ms


@dataclass
class MonorepoConfig:
    """Monorepo configuration."""

    package: str | None = None


@dataclass
class AgentConfig:
    """Complete agent.yaml configuration."""

    verification: VerificationConfig
    timeouts: TimeoutsConfig = field(default_factory=TimeoutsConfig)
    monorepo: MonorepoConfig = field(default_factory=MonorepoConfig)


def _parse_yaml(content: str) -> dict[str, Any]:
    """Parse YAML content into a dictionary.

    Args:
        content: Raw YAML string.

    Returns:
        Parsed dictionary.

    Raises:
        ConfigParseError: If YAML parsing fails.
    """
    try:
        result = yaml.safe_load(content)
        if result is None:
            return {}
        if not isinstance(result, dict):
            raise ConfigParseError("Configuration must be a YAML mapping")
        return result
    except yaml.YAMLError as e:
        raise ConfigParseError(f"Failed to parse YAML: {e}") from e


def _validate_verification_steps(steps: Any) -> list[VerificationStep]:
    """Validate and parse verification steps.

    Args:
        steps: Raw steps data from YAML.

    Returns:
        List of validated VerificationStep objects.

    Raises:
        ConfigValidationError: If steps validation fails.
    """
    if not isinstance(steps, list):
        raise ConfigValidationError("verification.steps must be a list")

    if len(steps) == 0:
        raise ConfigValidationError("verification.steps must contain at least one step")

    validated_steps = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ConfigValidationError(f"verification.steps[{i}] must be a mapping")

        if "name" not in step:
            raise ConfigValidationError(
                f"verification.steps[{i}] requires 'name' field"
            )

        if "command" not in step:
            raise ConfigValidationError(
                f"verification.steps[{i}] requires 'command' field"
            )

        name = step["name"]
        command = step["command"]

        if not isinstance(name, str) or not name.strip():
            raise ConfigValidationError(
                f"verification.steps[{i}].name must be a non-empty string"
            )

        if not isinstance(command, str) or not command.strip():
            raise ConfigValidationError(
                f"verification.steps[{i}].command must be a non-empty string"
            )

        validated_steps.append(VerificationStep(name=name, command=command))

    return validated_steps


def _validate_verification(data: dict[str, Any]) -> VerificationConfig:
    """Validate the verification section of configuration.

    Args:
        data: Raw configuration dictionary.

    Returns:
        Validated VerificationConfig.

    Raises:
        ConfigValidationError: If verification validation fails.
    """
    if "verification" not in data:
        raise ConfigValidationError("Missing required section: verification")

    verification = data["verification"]
    if not isinstance(verification, dict):
        raise ConfigValidationError("verification must be a mapping")

    if "container_image" not in verification:
        raise ConfigValidationError(
            "Missing required field: verification.container_image"
        )

    container_image = verification["container_image"]
    if not isinstance(container_image, str) or not container_image.strip():
        raise ConfigValidationError(
            "verification.container_image must be a non-empty string"
        )

    if "steps" not in verification:
        raise ConfigValidationError("Missing required field: verification.steps")

    steps = _validate_verification_steps(verification["steps"])

    return VerificationConfig(container_image=container_image, steps=steps)


def _validate_timeouts(data: dict[str, Any]) -> TimeoutsConfig:
    """Validate the timeouts section of configuration.

    Args:
        data: Raw configuration dictionary.

    Returns:
        Validated TimeoutsConfig with defaults if not specified.
    """
    if "timeouts" not in data:
        return TimeoutsConfig()

    timeouts = data["timeouts"]
    if not isinstance(timeouts, dict):
        raise ConfigValidationError("timeouts must be a mapping")

    verification_step = timeouts.get("verification_step", 300000)
    scout_query = timeouts.get("scout_query", 60000)

    if not isinstance(verification_step, int) or verification_step <= 0:
        raise ConfigValidationError(
            "timeouts.verification_step must be a positive integer"
        )

    if not isinstance(scout_query, int) or scout_query <= 0:
        raise ConfigValidationError("timeouts.scout_query must be a positive integer")

    return TimeoutsConfig(
        verification_step=verification_step,
        scout_query=scout_query,
    )


def _validate_monorepo(data: dict[str, Any]) -> MonorepoConfig:
    """Validate the monorepo section of configuration.

    Args:
        data: Raw configuration dictionary.

    Returns:
        Validated MonorepoConfig with defaults if not specified.
    """
    if "monorepo" not in data:
        return MonorepoConfig()

    monorepo = data["monorepo"]
    if not isinstance(monorepo, dict):
        raise ConfigValidationError("monorepo must be a mapping")

    package = monorepo.get("package")
    if package is not None and (not isinstance(package, str) or not package.strip()):
        raise ConfigValidationError("monorepo.package must be a non-empty string")

    return MonorepoConfig(package=package)


def parse_config(content: str) -> AgentConfig:
    """Parse and validate agent.yaml configuration content.

    Args:
        content: Raw YAML string.

    Returns:
        Validated AgentConfig object.

    Raises:
        ConfigParseError: If YAML parsing fails.
        ConfigValidationError: If schema validation fails.
    """
    data = _parse_yaml(content)
    verification = _validate_verification(data)
    timeouts = _validate_timeouts(data)
    monorepo = _validate_monorepo(data)

    return AgentConfig(
        verification=verification,
        timeouts=timeouts,
        monorepo=monorepo,
    )


def load_config(path: Path) -> AgentConfig:
    """Load and validate agent.yaml configuration from a file.

    Args:
        path: Path to agent.yaml file.

    Returns:
        Validated AgentConfig object.

    Raises:
        ConfigParseError: If file reading or YAML parsing fails.
        ConfigValidationError: If schema validation fails.
    """
    try:
        content = path.read_text()
    except OSError as e:
        raise ConfigParseError(f"Failed to read configuration file: {e}") from e

    return parse_config(content)
