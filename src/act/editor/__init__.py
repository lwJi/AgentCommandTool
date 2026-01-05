"""Editor - the sole orchestrator for repository modifications.

The Editor is the single source of truth for all repo modifications.
It coordinates Scouts, implements changes, triggers verification,
and produces final summaries.
"""

# Exceptions
# Write boundaries
from act.editor.boundaries import (
    WriteBoundaryEnforcer,
    create_boundary_enforcer,
)

# Scout coordination
from act.editor.coordinator import (
    ScoutCoordinator,
    ScoutResults,
    create_scout_coordinator,
)

# Debug loop
from act.editor.debug_loop import (
    CONSECUTIVE_FAILURE_THRESHOLD,
    MAX_REPLANS,
    TOTAL_VERIFY_LOOP_THRESHOLD,
    DebugLoop,
    DebugLoopState,
    LoopAction,
    VerifyAttempt,
    create_debug_loop,
)

# Dry-run mode
from act.editor.dry_run import (
    DryRunManager,
    DryRunProposal,
    FileChange,
    create_dry_run_manager,
    format_proposal_output,
)

# Main Editor
from act.editor.editor import (
    Editor,
    EditorContext,
    WorkflowState,
    create_editor,
)
from act.editor.exceptions import (
    EditorError,
    EditorErrorType,
    HardStopError,
    ImplementationError,
    InfrastructureError,
    ScoutCoordinationError,
    TaskParseError,
    WriteBoundaryError,
)

# Outputs
from act.editor.outputs import (
    STUCK_REPORT_FILENAME,
    StuckReport,
    StuckReportHypothesis,
    SuccessSummary,
    generate_stuck_report,
    generate_stuck_report_hypotheses,
    generate_success_summary,
    has_stuck_report,
    read_stuck_report,
    write_stuck_report,
)

# Task parsing
from act.editor.task import (
    ParsedTask,
    SuccessCriteria,
    TaskConstraints,
    parse_task,
    validate_task,
)

__all__ = [
    # Exceptions
    "EditorError",
    "EditorErrorType",
    "TaskParseError",
    "ScoutCoordinationError",
    "ImplementationError",
    "WriteBoundaryError",
    "HardStopError",
    "InfrastructureError",
    # Task parsing
    "ParsedTask",
    "TaskConstraints",
    "SuccessCriteria",
    "parse_task",
    "validate_task",
    # Scout coordination
    "ScoutCoordinator",
    "ScoutResults",
    "create_scout_coordinator",
    # Debug loop
    "DebugLoop",
    "DebugLoopState",
    "LoopAction",
    "VerifyAttempt",
    "create_debug_loop",
    "CONSECUTIVE_FAILURE_THRESHOLD",
    "TOTAL_VERIFY_LOOP_THRESHOLD",
    "MAX_REPLANS",
    # Outputs
    "SuccessSummary",
    "StuckReport",
    "StuckReportHypothesis",
    "generate_success_summary",
    "generate_stuck_report",
    "generate_stuck_report_hypotheses",
    "write_stuck_report",
    "read_stuck_report",
    "has_stuck_report",
    "STUCK_REPORT_FILENAME",
    # Dry-run mode
    "DryRunManager",
    "DryRunProposal",
    "FileChange",
    "create_dry_run_manager",
    "format_proposal_output",
    # Write boundaries
    "WriteBoundaryEnforcer",
    "create_boundary_enforcer",
    # Main Editor
    "Editor",
    "EditorContext",
    "WorkflowState",
    "create_editor",
]
