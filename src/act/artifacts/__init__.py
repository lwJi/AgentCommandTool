"""Artifact management for verification runs and context files."""

from act.artifacts.cleanup import (
    MAX_AGE_DAYS,
    MAX_RUNS,
    CleanupError,
    RunInfo,
    cleanup_runs,
    get_run_count,
    get_runs_to_delete,
    list_runs,
)
from act.artifacts.context import (
    ContextError,
    ContextSnapshot,
    EditorState,
    Milestone,
    get_latest_snapshot_path,
    get_snapshot_count,
    should_create_snapshot,
    write_context_snapshot,
)
from act.artifacts.context_dir import (
    ContextDirError,
    ensure_agent_dir,
    ensure_gitignore_entry,
    get_agent_dir,
    initialize_agent_dir,
    is_agent_dir_initialized,
)
from act.artifacts.dirs import (
    ArtifactDirError,
    ensure_artifact_dir_structure,
    get_cache_dir,
    get_runs_dir,
    is_artifact_dir_initialized,
)
from act.artifacts.manifest import (
    CommandResult,
    Manifest,
    ManifestError,
    PlatformInfo,
    create_command_result,
    get_current_commit_sha,
    get_platform_info,
    get_utc_timestamp,
    read_manifest,
    write_manifest,
)
from act.artifacts.run_id import (
    RunIDError,
    create_run_dir,
    generate_run_id,
    get_run_dir,
    is_valid_run_id,
    parse_run_id_timestamp,
)

__all__ = [
    # Directory structure
    "ArtifactDirError",
    "ensure_artifact_dir_structure",
    "get_runs_dir",
    "get_cache_dir",
    "is_artifact_dir_initialized",
    # Run ID management
    "RunIDError",
    "generate_run_id",
    "create_run_dir",
    "get_run_dir",
    "is_valid_run_id",
    "parse_run_id_timestamp",
    # Manifest management
    "ManifestError",
    "Manifest",
    "CommandResult",
    "PlatformInfo",
    "write_manifest",
    "read_manifest",
    "create_command_result",
    "get_current_commit_sha",
    "get_platform_info",
    "get_utc_timestamp",
    # Cleanup
    "CleanupError",
    "RunInfo",
    "list_runs",
    "get_runs_to_delete",
    "cleanup_runs",
    "get_run_count",
    "MAX_RUNS",
    "MAX_AGE_DAYS",
    # Context directory
    "ContextDirError",
    "get_agent_dir",
    "ensure_agent_dir",
    "ensure_gitignore_entry",
    "initialize_agent_dir",
    "is_agent_dir_initialized",
    # Context snapshots
    "ContextError",
    "Milestone",
    "EditorState",
    "ContextSnapshot",
    "write_context_snapshot",
    "get_latest_snapshot_path",
    "get_snapshot_count",
    "should_create_snapshot",
]
