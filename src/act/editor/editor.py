"""Main Editor orchestrator.

The Editor is the sole orchestrator and single source of truth for all
repository modifications. It coordinates Scouts, implements changes,
triggers verification, and produces final summaries.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from act.artifacts.context import (
    EditorState,
    Milestone,
    write_context_snapshot,
)
from act.artifacts.context_dir import ensure_agent_dir, get_agent_dir
from act.config.env import EnvConfig, LLMConfig, load_env_config
from act.config.schema import AgentConfig
from act.editor.boundaries import WriteBoundaryEnforcer, create_boundary_enforcer
from act.editor.coordinator import (
    ScoutCoordinator,
    ScoutResults,
    create_scout_coordinator,
)
from act.editor.debug_loop import (
    TOTAL_VERIFY_LOOP_THRESHOLD,
    DebugLoop,
    LoopAction,
    create_debug_loop,
)
from act.editor.dry_run import DryRunManager, DryRunProposal, create_dry_run_manager
from act.editor.exceptions import (
    EditorError,
    HardStopError,
    InfrastructureError,
)
from act.editor.outputs import (
    StuckReport,
    SuccessSummary,
    generate_stuck_report,
    generate_success_summary,
    has_stuck_report,
    read_stuck_report,
    write_stuck_report,
)
from act.editor.task import ParsedTask, parse_task
from act.verifier import VerifierResponse, VerifierStatus


class WorkflowState(Enum):
    """State of the Editor."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    DEBUGGING = "debugging"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    STUCK = "stuck"
    INFRA_ERROR = "infra_error"


@dataclass
class EditorContext:
    """Current context of the Editor."""

    task: ParsedTask | None = None
    scout_results: ScoutResults | None = None
    files_modified: list[str] = field(default_factory=list)
    current_hypothesis: str = ""
    last_verification: VerifierResponse | None = None
    dry_run_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        scout_dict = self.scout_results.to_dict() if self.scout_results else None
        return {
            "task": self.task.to_dict() if self.task else None,
            "scout_results": scout_dict,
            "files_modified": self.files_modified,
            "current_hypothesis": self.current_hypothesis,
            "dry_run_mode": self.dry_run_mode,
        }


class Editor:
    """Main Editor orchestrator.

    The Editor is responsible for:
    - Task interpretation and parsing
    - Scout coordination (pull-based queries)
    - Context recording to agent/ directory
    - Implementing minimal, convention-following changes
    - Triggering verification and consuming results
    - Debug loop with fix-forward strategy
    - Summary/stuck report generation
    """

    def __init__(
        self,
        repo_root: Path | str,
        agent_config: AgentConfig,
        llm_config: LLMConfig | None = None,
        env_config: EnvConfig | None = None,
    ) -> None:
        """Initialize the Editor.

        Args:
            repo_root: Root directory of the repository.
            agent_config: Agent configuration from agent.yaml.
            llm_config: LLM configuration (optional, loaded from env if not provided).
            env_config: Environment configuration (optional).
        """
        self.repo_root = Path(repo_root).resolve()
        self.agent_config = agent_config

        # Load environment config if not provided
        if env_config is None:
            env_config = load_env_config()
        self.env_config = env_config

        # Use provided LLM config or from env
        resolved_llm_config = llm_config or env_config.llm
        if resolved_llm_config is None:
            raise EditorError("No LLM configuration available")
        self.llm_config = resolved_llm_config

        # Initialize agent directory
        self.agent_dir = get_agent_dir(self.repo_root)
        ensure_agent_dir(self.repo_root)

        # Initialize components
        self._coordinator = create_scout_coordinator(
            self.llm_config,
            self.repo_root,
        )
        self._debug_loop = create_debug_loop()
        self._dry_run_manager = create_dry_run_manager(self.repo_root)
        self._boundary_enforcer = create_boundary_enforcer(
            self.repo_root,
            artifact_dir=self.env_config.artifact_dir,
        )

        # State
        self._state = WorkflowState.IDLE
        self._context = EditorContext()

    @property
    def state(self) -> WorkflowState:
        """Get the current Editor state."""
        return self._state

    @property
    def context(self) -> EditorContext:
        """Get the current Editor context."""
        return self._context

    @property
    def debug_loop(self) -> DebugLoop:
        """Get the debug loop instance."""
        return self._debug_loop

    @property
    def coordinator(self) -> ScoutCoordinator:
        """Get the Scout coordinator."""
        return self._coordinator

    @property
    def dry_run_manager(self) -> DryRunManager:
        """Get the dry-run manager."""
        return self._dry_run_manager

    @property
    def boundary_enforcer(self) -> WriteBoundaryEnforcer:
        """Get the write boundary enforcer."""
        return self._boundary_enforcer

    def reset(self) -> None:
        """Reset the Editor for a new task."""
        self._state = WorkflowState.IDLE
        self._context = EditorContext()
        self._debug_loop.reset()
        self._coordinator.reset()
        self._dry_run_manager.reset()

    async def start_task(
        self,
        task_description: str,
        dry_run: bool = False,
    ) -> ParsedTask:
        """Start working on a new task.

        Args:
            task_description: Free-form natural language task description.
            dry_run: Whether to run in dry-run mode.

        Returns:
            Parsed task.

        Raises:
            EditorError: On task parsing or analysis errors.
        """
        self.reset()
        self._state = WorkflowState.ANALYZING
        self._context.dry_run_mode = dry_run

        if dry_run:
            self._dry_run_manager.start()

        # Parse the task
        self._context.task = parse_task(task_description)

        # Check for existing stuck report
        if has_stuck_report(self.agent_dir):
            stuck_report = read_stuck_report(self.agent_dir)
            if stuck_report:
                self._context.current_hypothesis = (
                    "Resuming from stuck state. "
                    "Previous stuck report available for reference."
                )

        # Create initial context snapshot
        self._write_context_snapshot(Milestone.TASK_START)

        return self._context.task

    async def analyze_codebase(self) -> ScoutResults:
        """Perform initial codebase analysis with Scouts.

        Queries Scout A and Scout B in parallel to understand the codebase.

        Returns:
            Combined Scout results.

        Raises:
            InfrastructureError: If Scouts fail after retries.
        """
        if not self._context.task:
            raise EditorError("No task started")

        self._state = WorkflowState.ANALYZING

        try:
            results = await self._coordinator.initial_analysis(
                self._context.task.main_objective
            )
            self._context.scout_results = results
            return results

        except InfrastructureError:
            self._state = WorkflowState.INFRA_ERROR
            raise

    def validate_write_path(self, path: str | Path) -> Path:
        """Validate that a path is within allowed write boundaries.

        Args:
            path: Path to validate.

        Returns:
            Validated path.

        Raises:
            WriteBoundaryError: If path is outside allowed boundaries.
        """
        return self._boundary_enforcer.validate_path(path)

    def record_file_modification(self, path: str) -> None:
        """Record that a file was modified.

        Args:
            path: Path to the modified file.
        """
        relative_path = self._boundary_enforcer.get_relative_path(path)
        if relative_path not in self._context.files_modified:
            self._context.files_modified.append(relative_path)

    async def handle_verification_result(
        self,
        response: VerifierResponse,
    ) -> LoopAction:
        """Handle a verification result.

        Implements the fix-forward strategy with REPLAN and hard stop.

        Args:
            response: The Verifier response.

        Returns:
            Action to take next.

        Raises:
            HardStopError: When hard stop threshold is reached.
            InfrastructureError: On Verifier infrastructure errors.
        """
        self._context.last_verification = response

        # Handle infrastructure error
        if response.status == VerifierStatus.INFRA_ERROR:
            self._state = WorkflowState.INFRA_ERROR
            raise InfrastructureError(
                response.error_message or "Verifier infrastructure error",
                source="verifier",
            )

        # Handle success
        if response.status == VerifierStatus.PASS:
            action = self._debug_loop.record_success(response.run_id or "unknown")
            self._state = WorkflowState.COMPLETED
            return action

        # Handle failure
        failure_summary = ""
        if response.tail_log:
            # Extract brief summary from tail log
            lines = response.tail_log.strip().split("\n")
            failure_summary = lines[-1][:100] if lines else "Unknown failure"

        action = self._debug_loop.record_failure(
            response.run_id or "unknown",
            failure_summary,
        )

        if action == LoopAction.HARD_STOP:
            self._state = WorkflowState.STUCK
            raise HardStopError(
                f"Hard stop after {TOTAL_VERIFY_LOOP_THRESHOLD} verification attempts",
                total_attempts=self._debug_loop.total_verify_loops,
                run_ids=self._debug_loop.state.get_all_run_ids(),
            )

        if action == LoopAction.REPLAN:
            self._state = WorkflowState.REPLANNING
            # REPLAN is triggered, but not executed here
            # Caller should handle REPLAN action
        else:
            self._state = WorkflowState.DEBUGGING

        return action

    async def trigger_replan(
        self,
        new_strategy: str,
        requery_scouts: bool = False,
    ) -> ScoutResults | None:
        """Trigger a REPLAN event.

        Args:
            new_strategy: Description of the new strategy.
            requery_scouts: Whether to re-query Scouts.

        Returns:
            New Scout results if re-queried, None otherwise.
        """
        self._debug_loop.trigger_replan(new_strategy)
        self._context.current_hypothesis = new_strategy

        # Create context snapshot for REPLAN
        self._write_context_snapshot(Milestone.REPLAN)

        if requery_scouts and self._context.task:
            return await self.analyze_codebase()

        return None

    def generate_success_summary(self) -> SuccessSummary:
        """Generate a success summary.

        Returns:
            Success summary.

        Raises:
            EditorError: If no successful verification available.
        """
        if not self._context.task:
            raise EditorError("No task to summarize")

        if not self._context.last_verification:
            raise EditorError("No verification result available")

        if self._context.last_verification.status != VerifierStatus.PASS:
            raise EditorError("Last verification was not successful")

        # Create success context snapshot
        self._write_context_snapshot(Milestone.TASK_SUCCESS)

        return generate_success_summary(
            self._context.task,
            what_changed=self._context.current_hypothesis or "Changes implemented",
            run_id=self._context.last_verification.run_id or "unknown",
            files_modified=self._context.files_modified,
        )

    def generate_stuck_report(
        self,
        is_infra_error: bool = False,
        infra_error_source: str = "",
        infra_error_message: str = "",
    ) -> StuckReport:
        """Generate a stuck report.

        Args:
            is_infra_error: Whether this is an infrastructure error.
            infra_error_source: Source of infrastructure error.
            infra_error_message: Infrastructure error message.

        Returns:
            Stuck report.

        Raises:
            EditorError: If no task available.
        """
        if not self._context.task:
            raise EditorError("No task for stuck report")

        report = generate_stuck_report(
            self._context.task,
            self._debug_loop.state,
            self._context.files_modified,
            is_infra_error=is_infra_error,
            infra_error_source=infra_error_source,
            infra_error_message=infra_error_message,
        )

        # Write stuck report to agent directory
        write_stuck_report(self.agent_dir, report)

        return report

    def get_dry_run_proposal(self) -> DryRunProposal | None:
        """Get the current dry-run proposal.

        Returns:
            Dry-run proposal or None if not in dry-run mode.
        """
        if not self._context.dry_run_mode:
            return None
        return self._dry_run_manager.proposal

    def apply_dry_run_changes(self) -> list[str]:
        """Apply dry-run changes to the filesystem.

        Returns:
            List of files that were modified.

        Raises:
            EditorError: If not in dry-run mode or no proposal.
        """
        if not self._context.dry_run_mode:
            raise EditorError("Not in dry-run mode")

        modified_files = self._dry_run_manager.apply_changes()
        self._context.files_modified.extend(modified_files)
        self._context.dry_run_mode = False

        return modified_files

    def discard_dry_run_changes(self) -> None:
        """Discard dry-run changes without applying."""
        self._dry_run_manager.discard_changes()
        self._context.dry_run_mode = False

    def _write_context_snapshot(self, milestone: Milestone) -> None:
        """Write a context snapshot.

        Args:
            milestone: The milestone that triggered this snapshot.
        """
        editor_state = EditorState(
            hypothesis=self._context.current_hypothesis,
            files_modified=self._context.files_modified.copy(),
            verify_attempts=self._debug_loop.total_verify_loops,
            consecutive_failures=self._debug_loop.consecutive_failures,
            total_verify_loops=self._debug_loop.total_verify_loops,
        )

        scout_a_raw = None
        scout_b_raw = None
        if self._context.scout_results:
            scout_a_raw = self._context.scout_results.scout_a_raw or None
            scout_b_raw = self._context.scout_results.scout_b_raw or None

        write_context_snapshot(
            self.agent_dir,
            milestone,
            scout_a_payload=scout_a_raw,
            scout_b_payload=scout_b_raw,
            editor_state=editor_state,
        )

    def get_status_message(self) -> str:
        """Get a human-readable status message.

        Returns:
            Status message.
        """
        attempt_display = self._debug_loop.get_attempt_count_display()
        state_messages = {
            WorkflowState.IDLE: "Idle",
            WorkflowState.ANALYZING: "Analyzing codebase...",
            WorkflowState.IMPLEMENTING: "Implementing changes...",
            WorkflowState.VERIFYING: "Running verification...",
            WorkflowState.DEBUGGING: f"Debugging... {attempt_display}",
            WorkflowState.REPLANNING: "Replanning strategy...",
            WorkflowState.COMPLETED: "Task completed successfully",
            WorkflowState.STUCK: "Task stuck - hard stop reached",
            WorkflowState.INFRA_ERROR: "Infrastructure error occurred",
        }
        return state_messages.get(self._state, "Unknown state")


def create_editor(
    repo_root: Path | str,
    agent_config: AgentConfig,
    llm_config: LLMConfig | None = None,
) -> Editor:
    """Create an Editor instance.

    Args:
        repo_root: Repository root path.
        agent_config: Agent configuration.
        llm_config: Optional LLM configuration.

    Returns:
        Configured Editor instance.
    """
    return Editor(repo_root, agent_config, llm_config)
