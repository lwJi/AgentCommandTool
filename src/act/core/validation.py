"""Input validation for task execution.

Validates:
- Task description is non-empty
- agent.yaml is valid
- Docker is available
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Validation constants
MAX_TASK_DESCRIPTION_LENGTH = 10000
MIN_TASK_DESCRIPTION_LENGTH = 3


@dataclass
class ValidationResult:
    """Result of input validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @staticmethod
    def success() -> ValidationResult:
        """Create a successful validation result."""
        return ValidationResult(valid=True, errors=[], warnings=[])

    @staticmethod
    def failure(errors: list[str]) -> ValidationResult:
        """Create a failed validation result."""
        return ValidationResult(valid=False, errors=errors, warnings=[])

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge another validation result into this one.

        Args:
            other: Another validation result

        Returns:
            Self for chaining
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False
        return self

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_task_input(task_description: str) -> ValidationResult:
    """Validate task description input.

    Args:
        task_description: The task description to validate

    Returns:
        ValidationResult
    """
    result = ValidationResult(valid=True)

    # Check for empty
    if not task_description:
        result.add_error("Task description cannot be empty")
        return result

    # Check for whitespace only
    stripped = task_description.strip()
    if not stripped:
        result.add_error("Task description cannot be whitespace only")
        return result

    # Check minimum length
    if len(stripped) < MIN_TASK_DESCRIPTION_LENGTH:
        result.add_warning(
            f"Task description is very short ({len(stripped)} chars), "
            "consider being more specific"
        )

    # Check maximum length
    if len(task_description) > MAX_TASK_DESCRIPTION_LENGTH:
        result.add_error(
            f"Task description exceeds maximum length "
            f"({len(task_description)} > {MAX_TASK_DESCRIPTION_LENGTH} characters)"
        )

    return result


def validate_agent_config(repo_path: Path) -> ValidationResult:
    """Validate agent.yaml configuration.

    Args:
        repo_path: Path to repository root

    Returns:
        ValidationResult
    """
    from act.config.schema import ConfigError, load_config

    config_path = repo_path / "agent.yaml"

    if not config_path.exists():
        return ValidationResult.failure(
            [f"Configuration file not found: {config_path}"]
        )

    try:
        _config = load_config(config_path)
        return ValidationResult.success()
    except ConfigError as e:
        return ValidationResult.failure([f"Configuration error: {e}"])
    except Exception as e:
        return ValidationResult.failure([f"Unexpected error loading config: {e}"])


def validate_docker_available() -> ValidationResult:
    """Validate Docker is available.

    Returns:
        ValidationResult
    """
    from act.verifier.container import ContainerManager

    try:
        manager = ContainerManager()
        if manager.is_docker_available():
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                ["Docker daemon is not running or not accessible"]
            )
    except Exception as e:
        return ValidationResult.failure([f"Failed to check Docker availability: {e}"])


def validate_repo_path(repo_path: Path) -> ValidationResult:
    """Validate repository path.

    Args:
        repo_path: Path to validate

    Returns:
        ValidationResult
    """
    result = ValidationResult(valid=True)

    if not repo_path.exists():
        result.add_error(f"Repository path does not exist: {repo_path}")
        return result

    if not repo_path.is_dir():
        result.add_error(f"Repository path is not a directory: {repo_path}")
        return result

    # Check for .git directory (optional warning)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        result.add_warning("Repository path does not appear to be a git repository")

    return result


def validate_all_inputs(
    task_description: str,
    repo_path: Path,
    skip_docker: bool = False,
) -> ValidationResult:
    """Validate all inputs before task execution.

    Args:
        task_description: Task description
        repo_path: Repository path
        skip_docker: Whether to skip Docker validation

    Returns:
        Combined ValidationResult
    """
    result = ValidationResult(valid=True)

    # Validate task input
    task_result = validate_task_input(task_description)
    result.merge(task_result)

    # Validate repo path
    repo_result = validate_repo_path(repo_path)
    result.merge(repo_result)

    # Only continue with config/docker validation if repo path is valid
    if repo_result.valid:
        # Validate config
        config_result = validate_agent_config(repo_path)
        result.merge(config_result)

        # Validate Docker (optional)
        if not skip_docker:
            docker_result = validate_docker_available()
            result.merge(docker_result)

    return result


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, result: ValidationResult) -> None:
        """Initialize with validation result.

        Args:
            result: The failed validation result
        """
        self.result = result
        message = "; ".join(result.errors)
        super().__init__(message)


def require_valid_inputs(
    task_description: str,
    repo_path: Path,
    skip_docker: bool = False,
) -> ValidationResult:
    """Validate inputs and raise exception on failure.

    Args:
        task_description: Task description
        repo_path: Repository path
        skip_docker: Whether to skip Docker validation

    Returns:
        ValidationResult if valid

    Raises:
        ValidationError: If validation fails
    """
    result = validate_all_inputs(task_description, repo_path, skip_docker)
    if not result.valid:
        raise ValidationError(result)
    return result
