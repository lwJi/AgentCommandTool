"""Scout B (Build/Test Detective) implementation.

Scout B is a read-only analyst specializing in build systems, test infrastructure,
and failure diagnosis. It determines how to build and test the project, interprets
failures, and flags environment issues.
"""

from pathlib import Path
from typing import Any

from act.config.env import LLMConfig
from act.scouts.llm_client import LLMMessage, create_llm_client
from act.scouts.schemas import SCHEMA_VERSION, ScoutBResponse, validate_scout_b_response

# Build configuration files to look for
BUILD_CONFIG_FILES = [
    # Node.js / JavaScript
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    # Python
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "poetry.lock",
    # Go
    "go.mod",
    "go.sum",
    # Rust
    "Cargo.toml",
    "Cargo.lock",
    # Build systems
    "Makefile",
    "CMakeLists.txt",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
    # CI/CD
    ".github/workflows/ci.yml",
    ".github/workflows/test.yml",
    ".github/workflows/build.yml",
    ".gitlab-ci.yml",
    ".travis.yml",
    "Jenkinsfile",
    # Test configuration
    "jest.config.js",
    "jest.config.ts",
    "jest.config.mjs",
    "vitest.config.js",
    "vitest.config.ts",
    "pytest.ini",
    "conftest.py",
    "tox.ini",
    ".nycrc",
    ".nycrc.json",
]

# Maximum log size to include (in characters)
MAX_LOG_SIZE = 20000

# Scout B system prompt
SCOUT_B_SYSTEM_PROMPT = f"""You are Scout B, a build and test infrastructure analyst.

Your role is to analyze repositories and provide structured guidance on:
1. Build Command Discovery - Identify how to build the project
2. Test Command Discovery - Identify how to run tests
3. Failure Interpretation - Analyze test/build output and explain root causes
4. Environment Issue Detection - Identify missing dependencies, version mismatches
5. Flakiness Detection - Flag potentially flaky tests (informational only)

CRITICAL CONSTRAINTS:
- You are STRICTLY READ-ONLY. You NEVER suggest executing commands directly.
- You ONLY analyze and report findings.
- You NEVER modify environment variables or install packages.
- You NEVER access binary files or secret files.
- All test failures are BLOCKING - you never recommend skipping or ignoring them.

OUTPUT FORMAT:
You MUST respond with a valid JSON object matching schema version {SCHEMA_VERSION}.

The JSON schema is:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "build": {{
    "detected_system": "npm | yarn | pnpm | make | cargo | go | ...",
    "commands": {{
      "install": "string | null - command to install dependencies",
      "build": "string - command to build the project",
      "clean": "string | null - command to clean build artifacts"
    }},
    "prerequisites": ["string - required tools/runtimes"],
    "notes": "string - additional notes about build"
  }},
  "test": {{
    "detected_framework": "jest | pytest | go test | cargo test | ...",
    "commands": {{
      "all": "string - command to run all tests",
      "unit": "string | null - command for unit tests only",
      "integration": "string | null - command for integration tests"
    }},
    "coverage_command": "string | null - command to run with coverage",
    "notes": "string - additional notes about testing"
  }},
  "failure_analysis": {{
    "root_cause": "string - what actually failed and why",
    "affected_files": ["string - source files implicated"],
    "suggested_investigation": ["string - next steps to debug"],
    "is_flaky": boolean - true if potentially non-deterministic,
    "flaky_reason": "string | null - why this might be flaky"
  }},
  "environment_issues": [
    {{
      "issue": "string - description of the issue",
      "severity": "blocking | warning",
      "suggested_fix": "string - how to fix (informational only)"
    }}
  ]
}}

Always include the schema_version field with value "{SCHEMA_VERSION}".
Respond ONLY with the JSON object, no additional text.

When analyzing failures:
- Be specific about the root cause
- List all affected files
- Provide actionable investigation steps
- Note if the failure could be flaky (but still treat as blocking)
"""


class ScoutB:
    """Scout B (Build/Test Detective) - Build and test infrastructure analyst."""

    def __init__(
        self,
        llm_config: LLMConfig,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Scout B.

        Args:
            llm_config: LLM configuration for queries.
            timeout_seconds: Timeout for each query.
            max_retries: Maximum retry attempts.
        """
        self.llm_client = create_llm_client(
            llm_config,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._conversation_history: list[LLMMessage] = []

    def reset_context(self) -> None:
        """Reset the conversation context.

        This starts a fresh context window for new analysis.
        """
        self._conversation_history = []

    def _find_build_config_files(self, repo_root: str | Path) -> dict[str, str]:
        """Find and read build configuration files in the repository.

        Args:
            repo_root: Root directory of the repository.

        Returns:
            Dictionary of file path -> content for found config files.
        """
        root = Path(repo_root)
        configs: dict[str, str] = {}

        for config_file in BUILD_CONFIG_FILES:
            file_path = root / config_file
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # Limit content size
                    if len(content) > MAX_LOG_SIZE:
                        content = content[:MAX_LOG_SIZE] + "\n... (truncated)"
                    configs[config_file] = content
                except (OSError, UnicodeDecodeError):
                    # Skip files we can't read
                    pass

        return configs

    async def query(
        self,
        question: str,
        repo_root: str | Path,
        include_build_configs: bool = True,
        log_content: str | None = None,
    ) -> ScoutBResponse:
        """Query Scout B with a question about build/test infrastructure.

        Args:
            question: The question to ask.
            repo_root: Root directory of the repository.
            include_build_configs: Whether to include build config files.
            log_content: Optional log content to analyze.

        Returns:
            Structured ScoutBResponse.

        Raises:
            SchemaError: If response doesn't match expected schema.
            RetryExhaustedError: If all retries are exhausted.
            LLMError: On LLM communication errors.
        """
        context_parts = [f"Question: {question}"]

        if include_build_configs:
            configs = self._find_build_config_files(repo_root)
            if configs:
                context_parts.append("\nBuild configuration files:")
                for path, content in configs.items():
                    context_parts.append(f"\n--- {path} ---\n{content}")

        if log_content:
            # Truncate log if too long
            if len(log_content) > MAX_LOG_SIZE:
                log_content = log_content[-MAX_LOG_SIZE:]
                log_content = "... (truncated)\n" + log_content
            context_parts.append(f"\nLog output:\n{log_content}")

        user_message = LLMMessage(role="user", content="\n".join(context_parts))

        # Add to conversation history
        self._conversation_history.append(user_message)

        # Query LLM
        response_data = await self.llm_client.query_json(
            self._conversation_history,
            system_prompt=SCOUT_B_SYSTEM_PROMPT,
        )

        # Validate response
        response = validate_scout_b_response(response_data)

        # Add assistant response to history
        import json

        assistant_message = LLMMessage(
            role="assistant",
            content=json.dumps(response_data),
        )
        self._conversation_history.append(assistant_message)

        return response

    async def discover_build_commands(
        self,
        repo_root: str | Path,
    ) -> ScoutBResponse:
        """Discover build commands for the project.

        Args:
            repo_root: Root directory of the repository.

        Returns:
            ScoutBResponse with build information.
        """
        question = """Analyze this project and determine:

1. What build system is used (npm, yarn, make, cargo, go, gradle, maven, etc.)
2. The command to install dependencies
3. The command to build the project
4. The command to clean build artifacts
5. Any prerequisites (required tools, runtimes, versions)

Focus on providing accurate, working commands based on the configuration files."""

        return await self.query(question, repo_root)

    async def discover_test_commands(
        self,
        repo_root: str | Path,
    ) -> ScoutBResponse:
        """Discover test commands for the project.

        Args:
            repo_root: Root directory of the repository.

        Returns:
            ScoutBResponse with test information.
        """
        question = """Analyze this project and determine:

1. What test framework is used (jest, pytest, go test, cargo test, junit, mocha, etc.)
2. The command to run all tests
3. Commands to run unit tests only (if separate)
4. Commands to run integration tests only (if separate)
5. The command to run tests with coverage

Focus on providing accurate, working commands based on the configuration files."""

        return await self.query(question, repo_root)

    async def analyze_failure(
        self,
        log_content: str,
        repo_root: str | Path,
        context: str | None = None,
    ) -> ScoutBResponse:
        """Analyze a build or test failure.

        Args:
            log_content: The failure log output.
            repo_root: Root directory of the repository.
            context: Optional context about what was being tested.

        Returns:
            ScoutBResponse with failure_analysis populated.
        """
        question_parts = ["Analyze this build/test failure:"]

        if context:
            question_parts.append(f"\nContext: {context}")

        question_parts.append("""
Provide:
1. The root cause of the failure
2. Which source files are implicated
3. Suggested investigation steps
4. Whether this could be a flaky test (and why)

Be specific and actionable in your analysis.""")

        return await self.query(
            "\n".join(question_parts),
            repo_root,
            include_build_configs=True,
            log_content=log_content,
        )

    async def detect_environment_issues(
        self,
        log_content: str | None,
        repo_root: str | Path,
    ) -> ScoutBResponse:
        """Detect environment issues from logs or configuration.

        Args:
            log_content: Optional log content to analyze.
            repo_root: Root directory of the repository.

        Returns:
            ScoutBResponse with environment_issues populated.
        """
        question = """Analyze for environment issues:

1. Missing dependencies (packages, binaries)
2. Version mismatches (Node version, Python version, etc.)
3. Missing configuration files
4. Permission issues
5. Path problems

For each issue, classify as:
- blocking: prevents build/test from running
- warning: may cause problems but doesn't block

Provide suggested fixes (informational only - you cannot execute them)."""

        return await self.query(
            question,
            repo_root,
            include_build_configs=True,
            log_content=log_content,
        )

    async def full_discovery(
        self,
        repo_root: str | Path,
    ) -> ScoutBResponse:
        """Perform full discovery of build and test infrastructure.

        Args:
            repo_root: Root directory of the repository.

        Returns:
            ScoutBResponse with both build and test information.
        """
        question = (
            """Perform a complete analysis of this project's """
            """build and test infrastructure:

1. BUILD SYSTEM:
   - Detected build system
   - Install command
   - Build command
   - Clean command
   - Prerequisites

2. TEST FRAMEWORK:
   - Detected test framework
   - All tests command
   - Unit tests command (if separate)
   - Integration tests command (if separate)
   - Coverage command

3. ENVIRONMENT:
   - Any potential environment issues
   - Missing or outdated dependencies

Provide accurate, working commands based on the configuration files."""
        )

        return await self.query(question, repo_root)

    def get_raw_response(self) -> dict[str, Any] | None:
        """Get the raw JSON response from the last query.

        Returns:
            Raw response dictionary or None if no queries made.
        """
        if len(self._conversation_history) < 2:
            return None

        # Last message should be assistant response
        last_message = self._conversation_history[-1]
        if last_message.role == "assistant":
            import json

            try:
                result: dict[str, Any] = json.loads(last_message.content)
                return result
            except json.JSONDecodeError:
                return None
        return None


def create_scout_b(
    llm_config: LLMConfig,
    timeout_seconds: float = 60.0,
    max_retries: int = 3,
) -> ScoutB:
    """Create a Scout B instance.

    Args:
        llm_config: LLM configuration.
        timeout_seconds: Query timeout in seconds.
        max_retries: Maximum retry attempts.

    Returns:
        Configured ScoutB instance.
    """
    return ScoutB(llm_config, timeout_seconds, max_retries)
