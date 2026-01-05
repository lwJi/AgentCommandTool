"""Tests for startup validation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from act.config.validator import (
    StartupValidationError,
    require_valid_startup,
    validate_startup,
)


def _create_valid_config(repo_root: Path) -> None:
    """Create a valid agent.yaml in the repo root."""
    config_content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
"""
    (repo_root / "agent.yaml").write_text(config_content)


class TestValidateStartup:
    """Tests for validate_startup function."""

    def test_missing_agent_yaml(self, tmp_path: Path) -> None:
        """Missing agent.yaml returns error."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is False
            assert any("not found" in e.lower() for e in result.errors)
            assert result.config is None

    def test_no_api_key(self, tmp_path: Path) -> None:
        """No API key returns error."""
        _create_valid_config(tmp_path)

        with patch.dict(os.environ, {}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is False
            assert any("model access" in e.lower() for e in result.errors)

    def test_valid_config_with_anthropic_key(self, tmp_path: Path) -> None:
        """Valid config with Anthropic key passes."""
        _create_valid_config(tmp_path)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is True
            assert result.config is not None
            assert result.config.verification.container_image == "node:20-slim"
            assert len(result.errors) == 0

    def test_valid_config_with_openai_key(self, tmp_path: Path) -> None:
        """Valid config with OpenAI key passes."""
        _create_valid_config(tmp_path)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is True
            assert result.config is not None

    def test_valid_config_with_custom_endpoint(self, tmp_path: Path) -> None:
        """Valid config with custom LLM endpoint passes."""
        _create_valid_config(tmp_path)

        with patch.dict(
            os.environ,
            {"AGENT_LLM_BASE_URL": "http://localhost:8080/v1"},
            clear=True,
        ):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is True

    def test_invalid_yaml_returns_error(self, tmp_path: Path) -> None:
        """Invalid YAML returns parse error."""
        (tmp_path / "agent.yaml").write_text("invalid: yaml: content:")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is False
            assert any("parse" in e.lower() or "yaml" in e.lower() for e in result.errors)

    def test_missing_container_image(self, tmp_path: Path) -> None:
        """Missing container_image returns error."""
        config_content = """
verification:
  steps:
    - name: test
      command: npm test
"""
        (tmp_path / "agent.yaml").write_text(config_content)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is False
            assert any("container_image" in e for e in result.errors)

    def test_empty_steps(self, tmp_path: Path) -> None:
        """Empty steps array returns error."""
        config_content = """
verification:
  container_image: node:20-slim
  steps: []
"""
        (tmp_path / "agent.yaml").write_text(config_content)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is False
            assert any("step" in e.lower() for e in result.errors)

    def test_multiple_errors(self, tmp_path: Path) -> None:
        """Multiple validation errors are all reported."""
        # No config file and no API key
        with patch.dict(os.environ, {}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            assert result.valid is False
            assert len(result.errors) >= 2  # At least config + API key errors


class TestDockerCheck:
    """Tests for Docker availability check."""

    def test_docker_check_skipped_when_disabled(self, tmp_path: Path) -> None:
        """Docker check skipped when check_docker=False."""
        _create_valid_config(tmp_path)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = validate_startup(tmp_path, check_docker=False)

            # Should pass without Docker check
            assert result.valid is True


class TestRequireValidStartup:
    """Tests for require_valid_startup function."""

    def test_returns_config_on_success(self, tmp_path: Path) -> None:
        """Returns AgentConfig on successful validation."""
        _create_valid_config(tmp_path)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            config = require_valid_startup(tmp_path, check_docker=False)

            assert config is not None
            assert config.verification.container_image == "node:20-slim"

    def test_raises_on_missing_config(self, tmp_path: Path) -> None:
        """Raises StartupValidationError on missing config."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            with pytest.raises(StartupValidationError) as exc_info:
                require_valid_startup(tmp_path, check_docker=False)

            assert "not found" in str(exc_info.value).lower()

    def test_raises_on_missing_api_key(self, tmp_path: Path) -> None:
        """Raises StartupValidationError on missing API key."""
        _create_valid_config(tmp_path)

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(StartupValidationError) as exc_info:
                require_valid_startup(tmp_path, check_docker=False)

            assert "model access" in str(exc_info.value).lower()

    def test_error_message_lists_all_errors(self, tmp_path: Path) -> None:
        """Error message includes all validation failures."""
        # Missing both config and API key
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(StartupValidationError) as exc_info:
                require_valid_startup(tmp_path, check_docker=False)

            error_msg = str(exc_info.value)
            # Should mention both issues
            assert "not found" in error_msg.lower() or "configuration" in error_msg.lower()
            assert "model" in error_msg.lower()
