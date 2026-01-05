"""Scout coordination for the Editor.

Handles pull-based, synchronous queries to Scout A and Scout B,
with support for parallel execution when queries are independent.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from act.config.env import LLMConfig
from act.editor.exceptions import InfrastructureError, ScoutCoordinationError
from act.scouts import (
    RetryExhaustedError,
    ScoutA,
    ScoutAResponse,
    ScoutB,
    ScoutBResponse,
    ScoutError,
    create_scout_a,
    create_scout_b,
)


@dataclass
class ScoutResults:
    """Results from Scout queries."""

    scout_a_response: ScoutAResponse | None = None
    scout_b_response: ScoutBResponse | None = None
    scout_a_raw: dict[str, Any] = field(default_factory=dict)
    scout_b_raw: dict[str, Any] = field(default_factory=dict)
    conflict_resolution: str | None = None

    def has_scout_a(self) -> bool:
        """Check if Scout A response is available."""
        return self.scout_a_response is not None

    def has_scout_b(self) -> bool:
        """Check if Scout B response is available."""
        return self.scout_b_response is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of Scout results.
        """
        result: dict[str, Any] = {}

        if self.scout_a_response:
            result["scout_a"] = self.scout_a_response.to_dict()
        if self.scout_b_response:
            result["scout_b"] = self.scout_b_response.to_dict()
        if self.conflict_resolution:
            result["conflict_resolution"] = self.conflict_resolution

        return result


class ScoutCoordinator:
    """Coordinates queries to Scout A and Scout B.

    The coordinator handles:
    - Pull-based queries (Editor initiates)
    - Parallel execution when queries are independent
    - Sequential execution when queries depend on each other
    - Conflict resolution when Scouts disagree
    - Error handling with retry exhaustion detection
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        repo_root: Path | str,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize the Scout coordinator.

        Args:
            llm_config: LLM configuration for Scout queries.
            repo_root: Root directory of the repository.
            timeout_seconds: Timeout for each Scout query.
            max_retries: Maximum retry attempts per query.
        """
        self.llm_config = llm_config
        self.repo_root = Path(repo_root)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Create Scout instances
        self._scout_a = create_scout_a(
            llm_config,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._scout_b = create_scout_b(
            llm_config,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        # Track last results
        self._last_results: ScoutResults | None = None

    def reset(self) -> None:
        """Reset Scout contexts for a new task."""
        self._scout_a.reset_context()
        self._scout_b.reset_context()
        self._last_results = None

    async def query_scouts_parallel(
        self,
        scout_a_question: str,
        scout_b_question: str,
    ) -> ScoutResults:
        """Query both Scouts in parallel.

        Use when Scout A and Scout B questions are independent.

        Args:
            scout_a_question: Question for Scout A.
            scout_b_question: Question for Scout B.

        Returns:
            Combined Scout results.

        Raises:
            InfrastructureError: If a Scout fails after all retries.
            ScoutCoordinationError: On other coordination errors.
        """
        results = ScoutResults()

        async def query_scout_a() -> tuple[ScoutAResponse, dict[str, Any]]:
            try:
                response = await self._scout_a.query(
                    scout_a_question,
                    self.repo_root,
                )
                raw = self._scout_a.get_raw_response() or {}
                return response, raw
            except RetryExhaustedError as e:
                raise InfrastructureError(
                    f"Scout A failed after {self.max_retries} retries: {e}",
                    source="scout_a",
                    original_error=e,
                ) from e
            except ScoutError as e:
                raise ScoutCoordinationError(
                    f"Scout A query failed: {e}",
                    scout_name="Scout A",
                ) from e

        async def query_scout_b() -> tuple[ScoutBResponse, dict[str, Any]]:
            try:
                response = await self._scout_b.query(
                    scout_b_question,
                    self.repo_root,
                )
                raw = self._scout_b.get_raw_response() or {}
                return response, raw
            except RetryExhaustedError as e:
                raise InfrastructureError(
                    f"Scout B failed after {self.max_retries} retries: {e}",
                    source="scout_b",
                    original_error=e,
                ) from e
            except ScoutError as e:
                raise ScoutCoordinationError(
                    f"Scout B query failed: {e}",
                    scout_name="Scout B",
                ) from e

        # Execute both queries in parallel
        scout_a_result, scout_b_result = await asyncio.gather(
            query_scout_a(),
            query_scout_b(),
        )

        results.scout_a_response, results.scout_a_raw = scout_a_result
        results.scout_b_response, results.scout_b_raw = scout_b_result

        self._last_results = results
        return results

    async def query_scout_a(
        self,
        question: str,
        file_contents: dict[str, str] | None = None,
    ) -> ScoutResults:
        """Query Scout A only.

        Args:
            question: Question for Scout A.
            file_contents: Optional file contents to include in context.

        Returns:
            Scout results with Scout A response only.

        Raises:
            InfrastructureError: If Scout A fails after all retries.
            ScoutCoordinationError: On other coordination errors.
        """
        results = ScoutResults()

        try:
            if file_contents:
                response = await self._scout_a.analyze_files(
                    question,
                    self.repo_root,
                    file_contents,
                )
            else:
                response = await self._scout_a.query(question, self.repo_root)

            results.scout_a_response = response
            results.scout_a_raw = self._scout_a.get_raw_response() or {}

        except RetryExhaustedError as e:
            raise InfrastructureError(
                f"Scout A failed after {self.max_retries} retries: {e}",
                source="scout_a",
                original_error=e,
            ) from e
        except ScoutError as e:
            raise ScoutCoordinationError(
                f"Scout A query failed: {e}",
                scout_name="Scout A",
            ) from e

        self._last_results = results
        return results

    async def query_scout_b(
        self,
        question: str,
        log_content: str | None = None,
    ) -> ScoutResults:
        """Query Scout B only.

        Args:
            question: Question for Scout B.
            log_content: Optional log content for failure analysis.

        Returns:
            Scout results with Scout B response only.

        Raises:
            InfrastructureError: If Scout B fails after all retries.
            ScoutCoordinationError: On other coordination errors.
        """
        results = ScoutResults()

        try:
            response = await self._scout_b.query(
                question,
                self.repo_root,
                log_content=log_content,
            )
            results.scout_b_response = response
            results.scout_b_raw = self._scout_b.get_raw_response() or {}

        except RetryExhaustedError as e:
            raise InfrastructureError(
                f"Scout B failed after {self.max_retries} retries: {e}",
                source="scout_b",
                original_error=e,
            ) from e
        except ScoutError as e:
            raise ScoutCoordinationError(
                f"Scout B query failed: {e}",
                scout_name="Scout B",
            ) from e

        self._last_results = results
        return results

    async def analyze_failure(
        self,
        log_content: str,
        affected_files: list[str] | None = None,
    ) -> ScoutResults:
        """Analyze a verification failure using Scout B.

        Args:
            log_content: The failure log content.
            affected_files: Optional list of files that might be affected.

        Returns:
            Scout B analysis results.

        Raises:
            InfrastructureError: If Scout B fails after all retries.
            ScoutCoordinationError: On other coordination errors.
        """
        results = ScoutResults()

        try:
            response = await self._scout_b.analyze_failure(log_content, self.repo_root)
            results.scout_b_response = response
            results.scout_b_raw = self._scout_b.get_raw_response() or {}

        except RetryExhaustedError as e:
            raise InfrastructureError(
                f"Scout B failed after {self.max_retries} retries: {e}",
                source="scout_b",
                original_error=e,
            ) from e
        except ScoutError as e:
            raise ScoutCoordinationError(
                f"Scout B failure analysis failed: {e}",
                scout_name="Scout B",
            ) from e

        self._last_results = results
        return results

    async def initial_analysis(
        self,
        task_description: str,
    ) -> ScoutResults:
        """Perform initial analysis for a new task.

        Queries both Scouts in parallel:
        - Scout A: Find relevant files and risk zones
        - Scout B: Discover build/test infrastructure

        Args:
            task_description: The task to be performed.

        Returns:
            Combined Scout results.

        Raises:
            InfrastructureError: If a Scout fails after all retries.
            ScoutCoordinationError: On other coordination errors.
        """
        scout_a_question = f"""Analyze this task and identify all relevant files:

Task: {task_description}

Provide:
1. All files that need to be modified (primary relevance)
2. Files that provide context but don't need changes (secondary/context)
3. Entry points that would be affected
4. Risk zones that need careful handling
5. Safe slices for implementing this task in stages
6. Coding conventions used in the codebase"""

        scout_b_question = """Analyze the build and test infrastructure:

1. Detect the build system and provide build commands
2. Detect the test framework and provide test commands
3. List any prerequisites or environment setup needed
4. Note any potential environment issues"""

        return await self.query_scouts_parallel(scout_a_question, scout_b_question)

    def resolve_conflict(
        self,
        scout_a_suggestion: str,
        scout_b_suggestion: str,
        context: str,
    ) -> str:
        """Resolve a conflict between Scout A and Scout B suggestions.

        The Editor makes the final call autonomously based on context.
        No escalation to user.

        Args:
            scout_a_suggestion: Scout A's suggestion.
            scout_b_suggestion: Scout B's suggestion.
            context: Additional context for the decision.

        Returns:
            The chosen approach with rationale.
        """
        # Editor's autonomous conflict resolution logic
        # In a real implementation, this would use more sophisticated reasoning
        # For now, we prioritize based on failure context

        if "test" in context.lower() or "build" in context.lower():
            # If the context is about testing/building, prefer Scout B
            decision = scout_b_suggestion
            rationale = (
                "Chose Scout B's suggestion as context relates to build/test "
                "infrastructure where Scout B has specialized knowledge."
            )
        else:
            # Default to Scout A for code-related decisions
            decision = scout_a_suggestion
            rationale = (
                "Chose Scout A's suggestion as context relates to codebase "
                "structure where Scout A has specialized knowledge."
            )

        resolution = f"{decision}\n\nRationale: {rationale}"

        if self._last_results:
            self._last_results.conflict_resolution = resolution

        return resolution

    def get_last_results(self) -> ScoutResults | None:
        """Get the last Scout query results.

        Returns:
            Last ScoutResults or None if no queries made.
        """
        return self._last_results

    @property
    def scout_a(self) -> ScoutA:
        """Access the Scout A instance."""
        return self._scout_a

    @property
    def scout_b(self) -> ScoutB:
        """Access the Scout B instance."""
        return self._scout_b


def create_scout_coordinator(
    llm_config: LLMConfig,
    repo_root: Path | str,
    timeout_seconds: float = 60.0,
    max_retries: int = 3,
) -> ScoutCoordinator:
    """Create a Scout coordinator.

    Args:
        llm_config: LLM configuration.
        repo_root: Repository root path.
        timeout_seconds: Query timeout.
        max_retries: Maximum retries per query.

    Returns:
        Configured ScoutCoordinator.
    """
    return ScoutCoordinator(
        llm_config,
        repo_root,
        timeout_seconds,
        max_retries,
    )
