"""Scout A (Codebase Mapper) implementation.

Scout A is a read-only analyst that locates files, patterns, APIs, and invariants
within the codebase. It produces structured guidance on where and how to make changes.
"""

from pathlib import Path
from typing import Any

from act.config.env import LLMConfig
from act.scouts.file_filter import discover_files
from act.scouts.llm_client import LLMMessage, create_llm_client
from act.scouts.schemas import SCHEMA_VERSION, ScoutAResponse, validate_scout_a_response

# Maximum files to include in context
MAX_FILES_IN_CONTEXT = 100

# Maximum file content size to include (in characters)
MAX_FILE_CONTENT_SIZE = 50000

# Scout A system prompt
SCOUT_A_SYSTEM_PROMPT = f"""You are Scout A, a read-only codebase analyst.

Your role is to analyze code repositories and provide structured guidance on:
1. File Location - Identify relevant files for a given task
2. Pattern Recognition - Find code patterns, conventions, and idioms
3. API Discovery - Locate internal APIs, interfaces, and contracts
4. Invariant Detection - Identify constraints that must be preserved
5. Risk Zone Mapping - Mark change boundaries with complexity estimates
6. Safe Slice Definition - Define minimal, atomic change units

CRITICAL CONSTRAINTS:
- You are STRICTLY READ-ONLY. You NEVER suggest executing commands or modifying files.
- You ONLY analyze and report findings.
- You NEVER access binary files (.png, .jpg, .exe, .dll, etc.)
- You NEVER access secret files (.env, credentials, secrets)

OUTPUT FORMAT:
You MUST respond with a valid JSON object matching schema version {SCHEMA_VERSION}.

The JSON schema is:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "repo_map": {{
    "relevant_files": [
      {{
        "path": "string - file path relative to repo root",
        "purpose": "string - what this file does",
        "relevance": "primary | secondary | context"
      }}
    ],
    "entry_points": ["string - main entry point files"],
    "dependency_graph": {{}} // optional dependency relationships
  }},
  "risk_zones": [
    {{
      "file": "string - file path",
      "start_line": number,
      "end_line": number,
      "risk_level": "low | medium | high",
      "complexity": "low | medium | high",
      "dependencies": ["string - files that depend on this zone"],
      "invariants": ["string - constraints that must be preserved"],
      "rationale": "string - explanation of risk assessment"
    }}
  ],
  "change_boundaries": {{
    "safe_slices": [
      {{
        "id": "string - unique identifier",
        "files": ["string - files in this slice"],
        "description": "string - what this slice changes",
        "complexity": "low | medium | high",
        "order": number | null // recommended implementation order
      }}
    ],
    "ordering_constraints": ["string - why certain slices must come first"]
  }},
  "conventions": {{
    "naming": "string - naming conventions used",
    "patterns": ["string - patterns used in codebase"],
    "anti_patterns": ["string - patterns to avoid"]
  }},
  "prior_art": [
    {{
      "file": "string - file with similar implementation",
      "description": "string - what makes it relevant",
      "relevance": "string - how it helps"
    }}
  ],
  "verification_tips": ["string - tips for verifying changes"],
  "hypotheses": ["string - hypotheses about best approaches"]
}}

Always include the schema_version field with value "{SCHEMA_VERSION}".
Respond ONLY with the JSON object, no additional text.
"""


class ScoutA:
    """Scout A (Codebase Mapper) - Read-only codebase analyst."""

    def __init__(
        self,
        llm_config: LLMConfig,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Scout A.

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

    async def query(
        self,
        question: str,
        repo_root: str | Path,
        include_file_list: bool = True,
    ) -> ScoutAResponse:
        """Query Scout A with a question about the codebase.

        Args:
            question: The question to ask (e.g., "Which files handle user auth?").
            repo_root: Root directory of the repository.
            include_file_list: Whether to include file list in context.

        Returns:
            Structured ScoutAResponse.

        Raises:
            SchemaError: If response doesn't match expected schema.
            RetryExhaustedError: If all retries are exhausted.
            LLMError: On LLM communication errors.
        """
        # Build context with file information
        context_parts = [f"Question: {question}"]

        if include_file_list:
            files = discover_files(repo_root, max_files=MAX_FILES_IN_CONTEXT)
            if files:
                file_list = "\n".join(f"- {f}" for f in files)
                context_parts.append(f"\nRepository files:\n{file_list}")

        user_message = LLMMessage(role="user", content="\n".join(context_parts))

        # Add to conversation history
        self._conversation_history.append(user_message)

        # Query LLM
        response_data = await self.llm_client.query_json(
            self._conversation_history,
            system_prompt=SCOUT_A_SYSTEM_PROMPT,
        )

        # Validate response
        response = validate_scout_a_response(response_data)

        # Add assistant response to history
        import json

        assistant_message = LLMMessage(
            role="assistant",
            content=json.dumps(response_data),
        )
        self._conversation_history.append(assistant_message)

        return response

    async def analyze_files(
        self,
        question: str,
        repo_root: str | Path,
        file_contents: dict[str, str],
    ) -> ScoutAResponse:
        """Query Scout A with specific file contents included.

        Args:
            question: The question to ask.
            repo_root: Root directory of the repository.
            file_contents: Dictionary of file path -> content to include.

        Returns:
            Structured ScoutAResponse.

        Raises:
            SchemaError: If response doesn't match expected schema.
            RetryExhaustedError: If all retries are exhausted.
            LLMError: On LLM communication errors.
        """
        # Build context with file contents
        context_parts = [f"Question: {question}", "\nFile contents:"]

        total_size = 0
        for path, content in file_contents.items():
            if total_size + len(content) > MAX_FILE_CONTENT_SIZE:
                context_parts.append(f"\n--- {path} (truncated, file too large) ---")
            else:
                context_parts.append(f"\n--- {path} ---\n{content}")
                total_size += len(content)

        user_message = LLMMessage(role="user", content="\n".join(context_parts))

        # Add to conversation history
        self._conversation_history.append(user_message)

        # Query LLM
        response_data = await self.llm_client.query_json(
            self._conversation_history,
            system_prompt=SCOUT_A_SYSTEM_PROMPT,
        )

        # Validate response
        response = validate_scout_a_response(response_data)

        # Add assistant response to history
        import json

        assistant_message = LLMMessage(
            role="assistant",
            content=json.dumps(response_data),
        )
        self._conversation_history.append(assistant_message)

        return response

    async def find_relevant_files(
        self,
        task_description: str,
        repo_root: str | Path,
    ) -> ScoutAResponse:
        """Find files relevant to a task.

        Args:
            task_description: Description of the task to accomplish.
            repo_root: Root directory of the repository.

        Returns:
            ScoutAResponse with relevant_files populated.
        """
        question = f"""Analyze this task and identify all relevant files:

Task: {task_description}

Provide:
1. All files that need to be modified (primary relevance)
2. Files that provide context but don't need changes (secondary/context)
3. Entry points that would be affected
4. Any risk zones that need careful handling
5. Safe slices for implementing this task in stages"""

        return await self.query(question, repo_root)

    async def analyze_risk_zones(
        self,
        file_paths: list[str],
        file_contents: dict[str, str],
        repo_root: str | Path,
    ) -> ScoutAResponse:
        """Analyze risk zones in specific files.

        Args:
            file_paths: List of file paths to analyze.
            file_contents: Dictionary of file path -> content.
            repo_root: Root directory of the repository.

        Returns:
            ScoutAResponse with risk_zones populated.
        """
        question = f"""Analyze the risk zones in these files:
{', '.join(file_paths)}

For each file, identify:
1. High-risk areas that could break other functionality
2. Areas with complex logic that need careful testing
3. Dependencies that could be affected
4. Invariants that must be preserved

Be specific about line numbers and provide rationale for each risk assessment."""

        return await self.analyze_files(question, repo_root, file_contents)

    async def identify_conventions(
        self,
        repo_root: str | Path,
        sample_files: dict[str, str] | None = None,
    ) -> ScoutAResponse:
        """Identify coding conventions used in the codebase.

        Args:
            repo_root: Root directory of the repository.
            sample_files: Optional sample files to analyze for conventions.

        Returns:
            ScoutAResponse with conventions populated.
        """
        question = """Analyze the codebase conventions:

1. Naming conventions (variables, functions, classes, files)
2. Common patterns used (e.g., factory pattern, singleton, etc.)
3. Anti-patterns to avoid in this codebase
4. Code organization patterns

Focus on patterns that any new code should follow to maintain consistency."""

        if sample_files:
            return await self.analyze_files(question, repo_root, sample_files)
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


def create_scout_a(
    llm_config: LLMConfig,
    timeout_seconds: float = 60.0,
    max_retries: int = 3,
) -> ScoutA:
    """Create a Scout A instance.

    Args:
        llm_config: LLM configuration.
        timeout_seconds: Query timeout in seconds.
        max_retries: Maximum retry attempts.

    Returns:
        Configured ScoutA instance.
    """
    return ScoutA(llm_config, timeout_seconds, max_retries)
