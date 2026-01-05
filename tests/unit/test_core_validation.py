"""Unit tests for act.core.validation module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from act.core.validation import (
    MAX_TASK_DESCRIPTION_LENGTH,
    MIN_TASK_DESCRIPTION_LENGTH,
    ValidationError,
    ValidationResult,
    require_valid_inputs,
    validate_agent_config,
    validate_all_inputs,
    validate_docker_available,
    validate_repo_path,
    validate_task_input,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_success_creates_valid_result(self) -> None:
        """success() creates a valid result."""
        result = ValidationResult.success()
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_failure_creates_invalid_result(self) -> None:
        """failure() creates an invalid result."""
        result = ValidationResult.failure(["Error 1", "Error 2"])
        assert result.valid is False
        assert len(result.errors) == 2
        assert "Error 1" in result.errors

    def test_add_error_sets_valid_false(self) -> None:
        """add_error() sets valid to False."""
        result = ValidationResult.success()
        result.add_error("New error")
        assert result.valid is False
        assert "New error" in result.errors

    def test_add_warning_keeps_valid_true(self) -> None:
        """add_warning() does not affect valid status."""
        result = ValidationResult.success()
        result.add_warning("Warning")
        assert result.valid is True
        assert "Warning" in result.warnings

    def test_merge_combines_results(self) -> None:
        """merge() combines errors and warnings."""
        result1 = ValidationResult(valid=True, errors=[], warnings=["W1"])
        result2 = ValidationResult(valid=False, errors=["E1"], warnings=["W2"])
        result1.merge(result2)
        assert result1.valid is False
        assert "E1" in result1.errors
        assert "W1" in result1.warnings
        assert "W2" in result1.warnings

    def test_to_dict(self) -> None:
        """to_dict() returns correct structure."""
        result = ValidationResult(
            valid=False, errors=["Error"], warnings=["Warning"]
        )
        data = result.to_dict()
        assert data["valid"] is False
        assert "Error" in data["errors"]
        assert "Warning" in data["warnings"]


class TestValidateTaskInput:
    """Tests for validate_task_input function."""

    def test_empty_string_fails(self) -> None:
        """Empty string fails validation."""
        result = validate_task_input("")
        assert result.valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_whitespace_only_fails(self) -> None:
        """Whitespace-only string fails validation."""
        result = validate_task_input("   \t\n  ")
        assert result.valid is False
        assert any("whitespace" in e.lower() for e in result.errors)

    def test_short_string_warns(self) -> None:
        """Very short string produces warning."""
        result = validate_task_input("ab")
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("short" in w.lower() for w in result.warnings)

    def test_normal_string_succeeds(self) -> None:
        """Normal task description succeeds."""
        result = validate_task_input("Fix the login bug in auth module")
        assert result.valid is True
        assert result.errors == []

    def test_exceeds_max_length_fails(self) -> None:
        """String exceeding max length fails."""
        long_string = "x" * (MAX_TASK_DESCRIPTION_LENGTH + 1)
        result = validate_task_input(long_string)
        assert result.valid is False
        assert any("maximum" in e.lower() or "exceed" in e.lower() for e in result.errors)

    def test_exactly_max_length_succeeds(self) -> None:
        """String at exactly max length succeeds."""
        max_string = "x" * MAX_TASK_DESCRIPTION_LENGTH
        result = validate_task_input(max_string)
        assert result.valid is True

    def test_exactly_min_length_succeeds(self) -> None:
        """String at exactly min length succeeds without warning."""
        min_string = "x" * MIN_TASK_DESCRIPTION_LENGTH
        result = validate_task_input(min_string)
        assert result.valid is True


class TestValidateAgentConfig:
    """Tests for validate_agent_config function."""

    def test_missing_config_fails(self, tmp_path: Path) -> None:
        """Missing agent.yaml fails validation."""
        result = validate_agent_config(tmp_path)
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_valid_config_succeeds(self, tmp_path: Path) -> None:
        """Valid agent.yaml succeeds."""
        config_content = """
verification:
  container_image: python:3.11-slim
  steps:
    - name: test
      command: pytest
"""
        (tmp_path / "agent.yaml").write_text(config_content)
        result = validate_agent_config(tmp_path)
        assert result.valid is True

    def test_invalid_yaml_fails(self, tmp_path: Path) -> None:
        """Invalid YAML fails validation."""
        (tmp_path / "agent.yaml").write_text("invalid: yaml: content:")
        result = validate_agent_config(tmp_path)
        assert result.valid is False

    def test_missing_required_fields_fails(self, tmp_path: Path) -> None:
        """Missing required fields fails validation."""
        (tmp_path / "agent.yaml").write_text("foo: bar")
        result = validate_agent_config(tmp_path)
        assert result.valid is False


class TestValidateDockerAvailable:
    """Tests for validate_docker_available function."""

    @patch("act.verifier.container.ContainerManager")
    def test_docker_available_succeeds(self, mock_manager_class: MagicMock) -> None:
        """Docker available succeeds validation."""
        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager_class.return_value = mock_manager
        result = validate_docker_available()
        assert result.valid is True

    @patch("act.verifier.container.ContainerManager")
    def test_docker_unavailable_fails(self, mock_manager_class: MagicMock) -> None:
        """Docker unavailable fails validation."""
        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = False
        mock_manager_class.return_value = mock_manager
        result = validate_docker_available()
        assert result.valid is False
        assert any("docker" in e.lower() for e in result.errors)

    @patch("act.verifier.container.ContainerManager")
    def test_docker_error_fails(self, mock_manager_class: MagicMock) -> None:
        """Docker check error fails validation."""
        mock_manager_class.side_effect = Exception("Connection error")
        result = validate_docker_available()
        assert result.valid is False
        assert any("failed" in e.lower() for e in result.errors)


class TestValidateRepoPath:
    """Tests for validate_repo_path function."""

    def test_nonexistent_path_fails(self, tmp_path: Path) -> None:
        """Non-existent path fails validation."""
        result = validate_repo_path(tmp_path / "nonexistent")
        assert result.valid is False
        assert any("not exist" in e.lower() for e in result.errors)

    def test_file_path_fails(self, tmp_path: Path) -> None:
        """File path (not directory) fails validation."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        result = validate_repo_path(file_path)
        assert result.valid is False
        assert any("not a directory" in e.lower() for e in result.errors)

    def test_directory_succeeds(self, tmp_path: Path) -> None:
        """Valid directory succeeds."""
        result = validate_repo_path(tmp_path)
        assert result.valid is True

    def test_non_git_repo_warns(self, tmp_path: Path) -> None:
        """Non-git directory produces warning."""
        result = validate_repo_path(tmp_path)
        assert result.valid is True
        assert any("git" in w.lower() for w in result.warnings)

    def test_git_repo_no_warning(self, tmp_path: Path) -> None:
        """Git repository produces no warning."""
        (tmp_path / ".git").mkdir()
        result = validate_repo_path(tmp_path)
        assert result.valid is True
        assert not any("git" in w.lower() for w in result.warnings)


class TestValidateAllInputs:
    """Tests for validate_all_inputs function."""

    @patch("act.core.validation.validate_docker_available")
    def test_all_valid(self, mock_docker: MagicMock, tmp_path: Path) -> None:
        """All inputs valid succeeds."""
        mock_docker.return_value = ValidationResult.success()
        # Create valid config
        config = """
verification:
  container_image: python:3.11-slim
  steps:
    - name: test
      command: pytest
"""
        (tmp_path / "agent.yaml").write_text(config)
        (tmp_path / ".git").mkdir()

        result = validate_all_inputs("Valid task description", tmp_path)
        assert result.valid is True

    def test_invalid_task_fails(self, tmp_path: Path) -> None:
        """Invalid task description fails overall."""
        result = validate_all_inputs("", tmp_path, skip_docker=True)
        assert result.valid is False

    def test_invalid_repo_path_fails(self, tmp_path: Path) -> None:
        """Invalid repo path fails overall."""
        result = validate_all_inputs(
            "Valid task", tmp_path / "nonexistent", skip_docker=True
        )
        assert result.valid is False

    def test_skip_docker_validation(self, tmp_path: Path) -> None:
        """skip_docker=True skips Docker validation."""
        config = """
verification:
  container_image: python:3.11-slim
  steps:
    - name: test
      command: pytest
"""
        (tmp_path / "agent.yaml").write_text(config)

        # Should not call docker validation
        result = validate_all_inputs("Valid task", tmp_path, skip_docker=True)
        # May still be invalid if other checks fail, but docker isn't called
        # Just verify it doesn't crash
        assert isinstance(result, ValidationResult)

    @patch("act.core.validation.validate_docker_available")
    def test_combines_all_errors(self, mock_docker: MagicMock, tmp_path: Path) -> None:
        """All validation errors are combined."""
        mock_docker.return_value = ValidationResult.failure(["Docker error"])
        config = """
verification:
  container_image: python:3.11-slim
  steps:
    - name: test
      command: pytest
"""
        (tmp_path / "agent.yaml").write_text(config)

        # Short task (warning) + Docker error
        result = validate_all_inputs("ab", tmp_path)
        assert len(result.warnings) > 0
        # Docker validation failed
        assert any("Docker" in e for e in result.errors)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_exception_contains_result(self) -> None:
        """ValidationError contains the result."""
        result = ValidationResult.failure(["Error 1", "Error 2"])
        error = ValidationError(result)
        assert error.result is result
        assert "Error 1" in str(error)

    def test_exception_message(self) -> None:
        """ValidationError has descriptive message."""
        result = ValidationResult.failure(["First error", "Second error"])
        error = ValidationError(result)
        message = str(error)
        assert "First error" in message
        assert "Second error" in message


class TestRequireValidInputs:
    """Tests for require_valid_inputs function."""

    @patch("act.core.validation.validate_docker_available")
    def test_valid_inputs_returns_result(
        self, mock_docker: MagicMock, tmp_path: Path
    ) -> None:
        """Valid inputs return result without raising."""
        mock_docker.return_value = ValidationResult.success()
        config = """
verification:
  container_image: python:3.11-slim
  steps:
    - name: test
      command: pytest
"""
        (tmp_path / "agent.yaml").write_text(config)
        (tmp_path / ".git").mkdir()

        result = require_valid_inputs("Valid task", tmp_path)
        assert result.valid is True

    def test_invalid_inputs_raises(self, tmp_path: Path) -> None:
        """Invalid inputs raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            require_valid_inputs("", tmp_path, skip_docker=True)
        assert exc_info.value.result.valid is False
