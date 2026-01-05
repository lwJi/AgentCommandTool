"""Tests for environment variable loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from act.config.env import (
    DEFAULT_ARTIFACT_DIR,
    ENV_ANTHROPIC_API_KEY,
    ENV_ARTIFACT_DIR,
    ENV_LLM_BASE_URL,
    ENV_LLM_MODEL,
    ENV_OPENAI_API_KEY,
    LLMBackend,
    get_artifact_dir,
    get_llm_backend,
    has_llm_config,
    load_env_config,
)


@pytest.fixture
def clean_env() -> None:
    """Fixture to clean LLM-related environment variables."""
    env_vars = [
        ENV_ANTHROPIC_API_KEY,
        ENV_OPENAI_API_KEY,
        ENV_LLM_BASE_URL,
        ENV_LLM_MODEL,
        ENV_ARTIFACT_DIR,
    ]
    with patch.dict(os.environ, {}, clear=True):
        for var in env_vars:
            os.environ.pop(var, None)
        yield


class TestLLMBackendPriority:
    """Tests for LLM backend selection priority."""

    def test_custom_endpoint_takes_priority(self) -> None:
        """Custom endpoint takes priority over API keys."""
        with patch.dict(
            os.environ,
            {
                ENV_LLM_BASE_URL: "http://localhost:8080/v1",
                ENV_LLM_MODEL: "llama-3.1-70b",
                ENV_ANTHROPIC_API_KEY: "sk-ant-test",
                ENV_OPENAI_API_KEY: "sk-test",
            },
            clear=True,
        ):
            backend = get_llm_backend()
            assert backend == LLMBackend.CUSTOM

            config = load_env_config()
            assert config.llm is not None
            assert config.llm.backend == LLMBackend.CUSTOM
            assert config.llm.base_url == "http://localhost:8080/v1"
            assert config.llm.model == "llama-3.1-70b"

    def test_anthropic_priority_over_openai(self) -> None:
        """Anthropic key takes priority over OpenAI when both present."""
        with patch.dict(
            os.environ,
            {
                ENV_ANTHROPIC_API_KEY: "sk-ant-test",
                ENV_OPENAI_API_KEY: "sk-test",
            },
            clear=True,
        ):
            backend = get_llm_backend()
            assert backend == LLMBackend.ANTHROPIC

            config = load_env_config()
            assert config.llm is not None
            assert config.llm.backend == LLMBackend.ANTHROPIC
            assert config.llm.api_key == "sk-ant-test"

    def test_openai_used_when_anthropic_absent(self) -> None:
        """OpenAI key used when Anthropic key is absent."""
        with patch.dict(
            os.environ,
            {
                ENV_OPENAI_API_KEY: "sk-test",
            },
            clear=True,
        ):
            backend = get_llm_backend()
            assert backend == LLMBackend.OPENAI

            config = load_env_config()
            assert config.llm is not None
            assert config.llm.backend == LLMBackend.OPENAI
            assert config.llm.api_key == "sk-test"

    def test_no_llm_when_no_config(self) -> None:
        """No LLM config when no environment variables set."""
        with patch.dict(os.environ, {}, clear=True):
            backend = get_llm_backend()
            assert backend is None

            config = load_env_config()
            assert config.llm is None

    def test_has_llm_config_true(self) -> None:
        """has_llm_config returns True when configured."""
        with patch.dict(
            os.environ,
            {ENV_ANTHROPIC_API_KEY: "sk-ant-test"},
            clear=True,
        ):
            assert has_llm_config() is True

    def test_has_llm_config_false(self) -> None:
        """has_llm_config returns False when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            assert has_llm_config() is False


class TestArtifactDir:
    """Tests for artifact directory configuration."""

    def test_default_artifact_dir(self) -> None:
        """Default artifact dir used when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            artifact_dir = get_artifact_dir()
            assert artifact_dir == DEFAULT_ARTIFACT_DIR
            assert artifact_dir == Path.home() / ".agent-artifacts"

    def test_custom_artifact_dir(self) -> None:
        """Custom artifact dir used when env var set."""
        with patch.dict(
            os.environ,
            {ENV_ARTIFACT_DIR: "/var/agent-data/artifacts"},
            clear=True,
        ):
            artifact_dir = get_artifact_dir()
            assert artifact_dir == Path("/var/agent-data/artifacts")

    def test_artifact_dir_tilde_expansion(self) -> None:
        """Tilde in artifact dir path is expanded."""
        with patch.dict(
            os.environ,
            {ENV_ARTIFACT_DIR: "~/my-artifacts"},
            clear=True,
        ):
            artifact_dir = get_artifact_dir()
            assert artifact_dir == Path.home() / "my-artifacts"

    def test_artifact_dir_in_env_config(self) -> None:
        """Artifact dir is included in EnvConfig."""
        with patch.dict(
            os.environ,
            {ENV_ARTIFACT_DIR: "/custom/path"},
            clear=True,
        ):
            config = load_env_config()
            assert config.artifact_dir == Path("/custom/path")


class TestModelConfiguration:
    """Tests for model configuration."""

    def test_model_with_anthropic(self) -> None:
        """Model can be specified with Anthropic backend."""
        with patch.dict(
            os.environ,
            {
                ENV_ANTHROPIC_API_KEY: "sk-ant-test",
                ENV_LLM_MODEL: "claude-3-opus-20240229",
            },
            clear=True,
        ):
            config = load_env_config()
            assert config.llm is not None
            assert config.llm.model == "claude-3-opus-20240229"

    def test_model_optional(self) -> None:
        """Model is optional and can be None."""
        with patch.dict(
            os.environ,
            {ENV_ANTHROPIC_API_KEY: "sk-ant-test"},
            clear=True,
        ):
            config = load_env_config()
            assert config.llm is not None
            assert config.llm.model is None


class TestCustomEndpoint:
    """Tests for custom endpoint configuration."""

    def test_custom_endpoint_uses_available_key(self) -> None:
        """Custom endpoint uses available API key."""
        with patch.dict(
            os.environ,
            {
                ENV_LLM_BASE_URL: "http://localhost:8080/v1",
                ENV_ANTHROPIC_API_KEY: "sk-ant-test",
            },
            clear=True,
        ):
            config = load_env_config()
            assert config.llm is not None
            assert config.llm.backend == LLMBackend.CUSTOM
            assert config.llm.api_key == "sk-ant-test"

    def test_custom_endpoint_without_key(self) -> None:
        """Custom endpoint works with empty key if no keys available."""
        with patch.dict(
            os.environ,
            {
                ENV_LLM_BASE_URL: "http://localhost:8080/v1",
            },
            clear=True,
        ):
            config = load_env_config()
            assert config.llm is not None
            assert config.llm.backend == LLMBackend.CUSTOM
            assert config.llm.api_key == ""
