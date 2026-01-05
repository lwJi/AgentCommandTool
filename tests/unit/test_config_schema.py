"""Tests for agent.yaml schema validation."""

import tempfile
from pathlib import Path

import pytest

from act.config.schema import (
    AgentConfig,
    ConfigParseError,
    ConfigValidationError,
    VerificationConfig,
    VerificationStep,
    load_config,
    parse_config,
)


class TestParseConfig:
    """Tests for parse_config function."""

    def test_valid_minimal_config(self) -> None:
        """Valid minimal configuration passes validation."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
"""
        config = parse_config(content)

        assert isinstance(config, AgentConfig)
        assert config.verification.container_image == "node:20-slim"
        assert len(config.verification.steps) == 1
        assert config.verification.steps[0].name == "test"
        assert config.verification.steps[0].command == "npm test"

    def test_valid_full_config(self) -> None:
        """Valid full configuration with all optional fields passes."""
        content = """
verification:
  container_image: python:3.12-slim
  steps:
    - name: install
      command: pip install -e ".[dev]"
    - name: lint
      command: ruff check src/
    - name: test
      command: pytest

timeouts:
  verification_step: 600000
  scout_query: 120000

monorepo:
  package: packages/core
"""
        config = parse_config(content)

        assert config.verification.container_image == "python:3.12-slim"
        assert len(config.verification.steps) == 3
        assert config.timeouts.verification_step == 600000
        assert config.timeouts.scout_query == 120000
        assert config.monorepo.package == "packages/core"

    def test_default_timeouts(self) -> None:
        """Default timeouts are used when not specified."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
"""
        config = parse_config(content)

        assert config.timeouts.verification_step == 300000  # 5 min default
        assert config.timeouts.scout_query == 60000  # 1 min default

    def test_default_monorepo(self) -> None:
        """Default monorepo config is used when not specified."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
"""
        config = parse_config(content)

        assert config.monorepo.package is None


class TestValidationErrors:
    """Tests for configuration validation errors."""

    def test_missing_verification_section(self) -> None:
        """Missing verification section raises error."""
        content = """
timeouts:
  verification_step: 300000
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "Missing required section: verification" in str(exc_info.value)

    def test_missing_container_image(self) -> None:
        """Missing container_image raises specific error."""
        content = """
verification:
  steps:
    - name: test
      command: npm test
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "verification.container_image" in str(exc_info.value)

    def test_missing_steps(self) -> None:
        """Missing steps array raises specific error."""
        content = """
verification:
  container_image: node:20-slim
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "verification.steps" in str(exc_info.value)

    def test_empty_steps(self) -> None:
        """Empty steps array raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps: []
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "at least one step" in str(exc_info.value)

    def test_step_missing_name(self) -> None:
        """Step missing name field raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - command: npm test
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "requires 'name' field" in str(exc_info.value)

    def test_step_missing_command(self) -> None:
        """Step missing command field raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "requires 'command' field" in str(exc_info.value)

    def test_empty_container_image(self) -> None:
        """Empty container_image raises error."""
        content = """
verification:
  container_image: ""
  steps:
    - name: test
      command: npm test
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "container_image must be a non-empty string" in str(exc_info.value)

    def test_empty_step_name(self) -> None:
        """Empty step name raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: ""
      command: npm test
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "name must be a non-empty string" in str(exc_info.value)

    def test_empty_step_command(self) -> None:
        """Empty step command raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: ""
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "command must be a non-empty string" in str(exc_info.value)

    def test_invalid_timeout_type(self) -> None:
        """Non-integer timeout raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
timeouts:
  verification_step: "slow"
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "verification_step must be a positive integer" in str(exc_info.value)

    def test_negative_timeout(self) -> None:
        """Negative timeout raises error."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
timeouts:
  scout_query: -100
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "scout_query must be a positive integer" in str(exc_info.value)


class TestParseErrors:
    """Tests for YAML parsing errors."""

    def test_malformed_yaml(self) -> None:
        """Malformed YAML raises parse error with details."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
    command: npm test  # Wrong indentation
"""
        with pytest.raises(ConfigParseError) as exc_info:
            parse_config(content)

        assert "Failed to parse YAML" in str(exc_info.value)

    def test_invalid_yaml_structure(self) -> None:
        """Non-mapping YAML raises error."""
        content = """
- item1
- item2
"""
        with pytest.raises(ConfigParseError) as exc_info:
            parse_config(content)

        assert "must be a YAML mapping" in str(exc_info.value)

    def test_empty_yaml(self) -> None:
        """Empty YAML raises validation error for missing verification."""
        content = ""

        with pytest.raises(ConfigValidationError) as exc_info:
            parse_config(content)

        assert "Missing required section: verification" in str(exc_info.value)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_file(self) -> None:
        """Loading valid config file works."""
        content = """
verification:
  container_image: node:20-slim
  steps:
    - name: test
      command: npm test
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            config = load_config(path)
            assert config.verification.container_image == "node:20-slim"
        finally:
            path.unlink()

    def test_load_nonexistent_file(self) -> None:
        """Loading nonexistent file raises error."""
        path = Path("/nonexistent/agent.yaml")

        with pytest.raises(ConfigParseError) as exc_info:
            load_config(path)

        assert "Failed to read configuration file" in str(exc_info.value)


class TestDataclasses:
    """Tests for configuration dataclasses."""

    def test_verification_step_creation(self) -> None:
        """VerificationStep can be created directly."""
        step = VerificationStep(name="test", command="npm test")
        assert step.name == "test"
        assert step.command == "npm test"

    def test_verification_config_creation(self) -> None:
        """VerificationConfig can be created directly."""
        steps = [VerificationStep(name="test", command="npm test")]
        config = VerificationConfig(container_image="node:20", steps=steps)
        assert config.container_image == "node:20"
        assert len(config.steps) == 1
