"""Scout A (Codebase Mapper) and Scout B (Build/Test Detective) implementations.

Scouts are read-only analysts that provide structured guidance to the Editor.
- Scout A: Codebase mapping, file location, API discovery, invariant detection
- Scout B: Build/test discovery, failure interpretation, environment issue detection

Both Scouts use fixed, versioned JSON schemas (v1) for their responses.
"""

from act.scouts.exceptions import (
    FileExclusionError,
    LLMError,
    RetryExhaustedError,
    SchemaError,
    ScoutError,
    ScoutErrorType,
)
from act.scouts.file_filter import (
    BINARY_EXTENSIONS,
    EXCLUDED_DIRECTORIES,
    SECRET_PATTERNS,
    discover_files,
    filter_files,
    is_binary_file,
    is_excluded_directory,
    is_secret_file,
    should_exclude_file,
    should_exclude_path,
)
from act.scouts.llm_client import (
    DEFAULT_TIMEOUT_SECONDS,
    LLMClient,
    LLMMessage,
    LLMResponse,
    create_llm_client,
)
from act.scouts.retry import (
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_INITIAL_DELAY_SECONDS,
    DEFAULT_MAX_DELAY_SECONDS,
    DEFAULT_MAX_RETRIES,
    RetryConfig,
    calculate_delay,
    is_retryable_error,
    retry_async,
    retry_sync,
)
from act.scouts.schemas import (
    SCHEMA_VERSION,
    BuildCommands,
    BuildInfo,
    BuildSystem,
    ChangeBoundaries,
    Complexity,
    Conventions,
    EnvironmentIssue,
    FailureAnalysis,
    PriorArt,
    Relevance,
    RelevantFile,
    RepoMap,
    RiskLevel,
    RiskZone,
    SafeSlice,
    ScoutAResponse,
    ScoutBResponse,
    Severity,
    TestCommands,
    TestFramework,
    TestInfo,
    validate_scout_a_response,
    validate_scout_b_response,
)
from act.scouts.scout_a import (
    MAX_FILE_CONTENT_SIZE,
    MAX_FILES_IN_CONTEXT,
    SCOUT_A_SYSTEM_PROMPT,
    ScoutA,
    create_scout_a,
)
from act.scouts.scout_b import (
    BUILD_CONFIG_FILES,
    MAX_LOG_SIZE,
    SCOUT_B_SYSTEM_PROMPT,
    ScoutB,
    create_scout_b,
)

__all__ = [
    # Exceptions
    "ScoutError",
    "LLMError",
    "SchemaError",
    "RetryExhaustedError",
    "FileExclusionError",
    "ScoutErrorType",
    # File filter
    "BINARY_EXTENSIONS",
    "SECRET_PATTERNS",
    "EXCLUDED_DIRECTORIES",
    "is_binary_file",
    "is_secret_file",
    "is_excluded_directory",
    "should_exclude_file",
    "should_exclude_path",
    "filter_files",
    "discover_files",
    # Retry
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_INITIAL_DELAY_SECONDS",
    "DEFAULT_BACKOFF_MULTIPLIER",
    "DEFAULT_MAX_DELAY_SECONDS",
    "RetryConfig",
    "calculate_delay",
    "is_retryable_error",
    "retry_sync",
    "retry_async",
    # LLM client
    "DEFAULT_TIMEOUT_SECONDS",
    "LLMMessage",
    "LLMResponse",
    "LLMClient",
    "create_llm_client",
    # Schemas
    "SCHEMA_VERSION",
    "Relevance",
    "RiskLevel",
    "Complexity",
    "Severity",
    "BuildSystem",
    "TestFramework",
    # Scout A schemas
    "RelevantFile",
    "RepoMap",
    "RiskZone",
    "SafeSlice",
    "ChangeBoundaries",
    "Conventions",
    "PriorArt",
    "ScoutAResponse",
    "validate_scout_a_response",
    # Scout B schemas
    "BuildCommands",
    "BuildInfo",
    "TestCommands",
    "TestInfo",
    "FailureAnalysis",
    "EnvironmentIssue",
    "ScoutBResponse",
    "validate_scout_b_response",
    # Scout A
    "MAX_FILES_IN_CONTEXT",
    "MAX_FILE_CONTENT_SIZE",
    "SCOUT_A_SYSTEM_PROMPT",
    "ScoutA",
    "create_scout_a",
    # Scout B
    "BUILD_CONFIG_FILES",
    "MAX_LOG_SIZE",
    "SCOUT_B_SYSTEM_PROMPT",
    "ScoutB",
    "create_scout_b",
]
