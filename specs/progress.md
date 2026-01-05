# Implementation Progress

This document tracks the implementation progress of AgentCommandTool.

---

## Phase 0: Project Setup (Completed)

**Date:** 2026-01-04

### What was implemented

1. **pyproject.toml** - Full project configuration with:
   - Name: `agent-command-tool`
   - Python version: `>=3.11`
   - Src layout with hatchling build backend
   - CLI entry point: `act = "act.cli:main"`
   - Runtime dependencies: anthropic, openai, docker, pyyaml, rich, click
   - Dev dependencies: pytest, pytest-asyncio, ruff, mypy
   - Tool configurations for pytest, ruff, and mypy

2. **.gitignore** - Standard Python ignores plus:
   - `agent/` (context files per specs/artifacts.md)
   - `.agent-artifacts/` (verification artifacts)

3. **Package structure** (`src/act/`):
   - `__init__.py` - Package init with version
   - `cli.py` - Click-based CLI with commands: run, status, queue, cancel
   - `config/` - Configuration parsing (placeholder)
   - `artifacts/` - Artifact management (placeholder)
   - `verifier/` - Docker sandbox (placeholder)
   - `scouts/` - Scout A and B (placeholder)
   - `editor/` - Orchestrator (placeholder)
   - `task/` - Task lifecycle (placeholder)

4. **Test structure** (`tests/`):
   - `unit/` - Unit tests
   - `integration/` - Component interaction tests
   - `container/` - Docker sandbox tests
   - `system/` - End-to-end flow tests

5. **README.md** - Basic usage documentation

### Validation results

All validation tests from the implementation plan pass:

| Test | Command | Result |
|------|---------|--------|
| Virtual env created | `uv sync` | Installed 41 packages |
| CLI responds | `uv run act --help` | Shows commands: cancel, queue, run, status |
| Version works | `uv run act --version` | `act, version 0.1.0` |
| Test discovery | `uv run pytest` | Works (0 tests collected) |
| Linting works | `uv run ruff check src/` | All checks passed |
| Package imports | Python import test | All runtime packages imported successfully |

### Files created

```
pyproject.toml
.gitignore
README.md
src/act/__init__.py
src/act/cli.py
src/act/config/__init__.py
src/act/artifacts/__init__.py
src/act/verifier/__init__.py
src/act/scouts/__init__.py
src/act/editor/__init__.py
src/act/task/__init__.py
tests/__init__.py
tests/unit/__init__.py
tests/integration/__init__.py
tests/container/__init__.py
tests/system/__init__.py
```

### Next steps

Proceed to **Phase 1: Foundation — Configuration and Artifact Infrastructure** as defined in `specs/implementation-plan.md`.

---

## Phase 1: Foundation — Configuration and Artifact Infrastructure (Completed)

**Date:** 2026-01-04

### What was implemented

#### 1.1 Configuration Parser (`src/act/config/`)

**1.1.1 agent.yaml Schema Validator** (`schema.py`)
- YAML parsing with `pyyaml` and validation against expected schema
- Required fields: `verification.container_image`, `verification.steps[]`
- Each step requires `name` and `command` fields
- Optional fields: `monorepo.package`, `timeouts.*`
- Dataclasses: `VerificationStep`, `VerificationConfig`, `TimeoutsConfig`, `MonorepoConfig`, `AgentConfig`
- Exceptions: `ConfigError`, `ConfigParseError`, `ConfigValidationError`

**1.1.2 Environment Variable Loader** (`env.py`)
- Reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AGENT_LLM_BASE_URL`, `AGENT_LLM_MODEL`
- Backend selection priority: custom endpoint > Anthropic > OpenAI
- Reads `AGENT_ARTIFACT_DIR` with default `~/.agent-artifacts/`
- Dataclasses: `LLMConfig`, `EnvConfig`
- Enum: `LLMBackend` (ANTHROPIC, OPENAI, CUSTOM)

**1.1.3 Startup Validation** (`validator.py`)
- Validates `agent.yaml` exists in repo root
- Validates schema is correct with at least one verification step
- Validates Docker available via `docker info`
- Validates LLM API key present
- Dataclass: `ValidationResult`
- Functions: `validate_startup()`, `require_valid_startup()`

#### 1.2 Artifact Directory Infrastructure (`src/act/artifacts/`)

**1.2.1 ARTIFACT_DIR Structure** (`dirs.py`)
- Creates `runs/` and `cache/` subdirectories
- Handles existing directory gracefully
- Functions: `ensure_artifact_dir_structure()`, `get_runs_dir()`, `get_cache_dir()`, `is_artifact_dir_initialized()`

**1.2.2 run_id Generator** (`run_id.py`)
- Format: `run_{YYYYMMDD}_{HHMMSS}_{random6chars}` (UTC timezone)
- Ensures uniqueness via random suffix
- Creates run directory: `ARTIFACT_DIR/runs/{run_id}/`
- Functions: `generate_run_id()`, `create_run_dir()`, `get_run_dir()`, `parse_run_id_timestamp()`, `is_valid_run_id()`

**1.2.3 manifest.json Writer** (`manifest.py`)
- Writes manifest with: `run_id`, `timestamp_start`, `timestamp_end`, `commit_sha`, `status`, `commands_executed[]`, `platform{}`
- Each command entry: `name`, `command`, `exit_code`, `duration_ms`
- Platform info: `os`, `arch`, `container_image`
- Dataclasses: `Manifest`, `CommandResult`, `PlatformInfo`
- Functions: `write_manifest()`, `read_manifest()`, `get_utc_timestamp()`, `get_current_commit_sha()`

**1.2.4 Artifact Retention Cleanup** (`cleanup.py`)
- Counts runs in ARTIFACT_DIR
- Deletes oldest runs when count > 20 (MAX_RUNS)
- Deletes runs older than 14 days (MAX_AGE_DAYS)
- Preserves runs with `stuck_report.md` files
- Dataclass: `RunInfo`
- Functions: `list_runs()`, `get_runs_to_delete()`, `delete_run()`, `cleanup_runs()`, `get_run_count()`

#### 1.3 Context File Infrastructure (`src/act/artifacts/`)

**1.3.1 agent/ Directory Initializer** (`context_dir.py`)
- Creates `agent/` directory in repo root if not exists
- Adds `agent/` to `.gitignore` if not already present (appends, doesn't overwrite)
- Functions: `get_agent_dir()`, `ensure_agent_dir()`, `ensure_gitignore_entry()`, `initialize_agent_dir()`, `is_agent_dir_initialized()`

**1.3.2 Context Snapshot Writer** (`context.py`)
- Generates incrementing snapshot numbers: `context_001.md`, `context_002.md`, etc.
- Writes markdown with: timestamp (UTC), milestone type, raw Scout payloads, Editor state
- Updates `context_latest.md` symlink to point to newest snapshot
- Falls back to file copy on systems without symlink support
- Dataclasses: `ContextSnapshot`, `EditorState`
- Functions: `write_context_snapshot()`, `get_latest_snapshot_path()`, `get_snapshot_count()`

**1.3.3 Context Snapshot Triggers** (`context.py`)
- Milestone enum: `TASK_START`, `REPLAN`, `TASK_SUCCESS`
- Only these milestones trigger snapshot creation
- Scout queries, verify attempts, and fix iterations do NOT create snapshots
- Function: `should_create_snapshot()`

### Validation results

All validation criteria from the implementation plan pass:

| Test | Command | Result |
|------|---------|--------|
| Unit tests | `uv run pytest tests/unit/ -v` | 147 passed |
| Linting | `uv run ruff check src/` | All checks passed |
| Type checking | `uv run mypy src/` | Success: no issues found in 17 source files |

### Files created

```
src/act/config/schema.py
src/act/config/env.py
src/act/config/validator.py
src/act/config/__init__.py (updated with exports)
src/act/artifacts/dirs.py
src/act/artifacts/run_id.py
src/act/artifacts/manifest.py
src/act/artifacts/cleanup.py
src/act/artifacts/context_dir.py
src/act/artifacts/context.py
src/act/artifacts/__init__.py (updated with exports)
tests/unit/test_config_schema.py (22 tests)
tests/unit/test_config_env.py (14 tests)
tests/unit/test_config_validator.py (14 tests)
tests/unit/test_artifacts_dirs.py (11 tests)
tests/unit/test_artifacts_run_id.py (17 tests)
tests/unit/test_artifacts_manifest.py (15 tests)
tests/unit/test_artifacts_cleanup.py (15 tests)
tests/unit/test_artifacts_context_dir.py (14 tests)
tests/unit/test_artifacts_context.py (25 tests)
```

### Dependencies added

- `types-PyYAML>=6.0.0` added to dev dependencies for mypy type checking

### Next steps

Proceed to **Phase 2: Verifier — Docker Sandbox Execution** as defined in `specs/implementation-plan.md`.

---

## Phase 2: Verifier — Sandboxed Execution (Completed)

**Date:** 2026-01-05

### What was implemented

#### 2.1 Exception Hierarchy (`src/act/verifier/exceptions.py`)

- Custom exception classes for Verifier errors
- `VerifierError` - Base exception for all Verifier errors
- `ContainerError(VerifierError)` - Docker container-related errors
- `PipelineError(VerifierError)` - Pipeline execution errors
- `LogError(VerifierError)` - Log file operation errors
- `InfraErrorType` enum with values: `DOCKER_UNAVAILABLE`, `CONTAINER_CREATION`, `IMAGE_PULL`, `RESOURCE_EXHAUSTION`, `UNKNOWN`

#### 2.2 Response Contract (`src/act/verifier/response.py`)

- `VerifierStatus` enum: `PASS`, `FAIL`, `INFRA_ERROR`
- `VerifierResponse` dataclass with:
  - `status` - Required VerifierStatus
  - `run_id` - Optional run identifier
  - `tail_log` - Optional last 200 lines of combined log
  - `artifact_paths` - List of artifact file paths
  - `manifest` - Optional Manifest from verification run
  - `error_type` - Optional InfraErrorType (for INFRA_ERROR only)
  - `error_message` - Optional error description (for INFRA_ERROR only)
- `to_dict()` method for JSON serialization (omits null optional fields)
- Factory functions:
  - `create_pass_response()` - Creates PASS response with all fields
  - `create_fail_response()` - Creates FAIL response with all fields
  - `create_infra_error_response()` - Creates INFRA_ERROR with error details

#### 2.3 Log Utilities (`src/act/verifier/logs.py`)

- `TAIL_LOG_LINES = 200` - Default lines for tail extraction
- Directory creation functions:
  - `create_logs_dir()` - Creates `logs/` subdirectory
  - `create_tmp_dir()` - Creates `tmp/` subdirectory
  - `create_db_dir()` - Creates `db/` subdirectory
- Log file utilities:
  - `get_step_log_filename()` - Generates `step-01-install.log` format
  - `write_step_log()` - Writes individual step log files
  - `append_combined_log()` - Appends to combined.log
  - `extract_tail_log()` - Extracts last N lines (default 200)
  - `list_artifact_paths()` - Lists all files in run directory

#### 2.4 Container Management (`src/act/verifier/container.py`)

- `DEFAULT_CPU_LIMIT = 4` - Default CPU cores
- `DEFAULT_MEMORY_LIMIT = "8g"` - Default memory limit
- `ContainerConfig` dataclass:
  - `image` - Docker image name and tag
  - `repo_path` - Path to repository (mounted read-only at `/workspace`)
  - `run_dir` - Path to run directory (mounted read-write at `/artifacts`)
  - `cpu_limit` - CPU limit (default 4)
  - `memory_limit` - Memory limit (default "8g")
  - `working_dir` - Container working directory (default "/workspace")
- `ContainerManager` class:
  - `__init__(client)` - Accepts optional Docker client for testing
  - `is_docker_available()` - Checks Docker daemon availability
  - `pull_image(image)` - Pulls Docker image
  - `image_exists(image)` - Checks if image exists locally
  - `create_container(config)` - Creates container with mounts
  - `start_container(container)` - Starts container
  - `destroy_container(container)` - Stops and removes container
  - `exec_in_container(container, command, env_vars)` - Executes command
- `classify_docker_error(error)` - Maps Docker exceptions to InfraErrorType

#### 2.5 Pipeline Execution (`src/act/verifier/pipeline.py`)

- `DEFAULT_TIMEOUT_MS = 300000` - Default 5-minute timeout
- `StepResult` dataclass:
  - `name` - Step name
  - `command` - Command executed
  - `exit_code` - Exit code (0 = success)
  - `duration_ms` - Duration in milliseconds
  - `timed_out` - Whether step timed out
- `PipelineExecutor` class:
  - `__init__(container_manager, container, logs_dir, timeout_ms)`
  - `execute_steps(steps, env_vars)` - Executes steps sequentially
  - Stops on first failure (exit_code != 0)
  - Writes per-step logs: `step-01-install.log`, etc.
  - Appends all output to `combined.log`
  - Handles timeouts with thread-based execution

#### 2.6 Main Entry Point (`src/act/verifier/executor.py`)

- `verify(repo_path, config, artifact_dir)` - Main verification function
- Orchestrates full verification flow:
  1. Resolves artifact directory (uses env default if not provided)
  2. Creates run directory via `create_run_dir()`
  3. Creates `logs/`, `tmp/`, `db/` subdirectories
  4. Checks Docker availability → INFRA_ERROR if unavailable
  5. Pulls image if needed → INFRA_ERROR on failure
  6. Creates container with read-only repo mount
  7. Starts container → INFRA_ERROR on failure
  8. Sets environment variables (`TMPDIR=/artifacts/tmp`, `TEST_DB_PATH=/artifacts/db`)
  9. Executes pipeline steps with timeout
  10. Writes manifest via `write_manifest()`
  11. Extracts tail log (last 200 lines)
  12. Lists artifact paths
  13. Destroys container (always, via try/finally)
  14. Returns PASS/FAIL/INFRA_ERROR response

#### 2.7 Public API (`src/act/verifier/__init__.py`)

Exports:
- `verify` - Main entry point
- `VerifierResponse`, `VerifierStatus`
- `create_pass_response`, `create_fail_response`, `create_infra_error_response`
- `VerifierError`, `ContainerError`, `PipelineError`, `LogError`, `InfraErrorType`
- `ContainerManager`, `ContainerConfig`
- `DEFAULT_CPU_LIMIT`, `DEFAULT_MEMORY_LIMIT`
- `PipelineExecutor`, `StepResult`
- `TAIL_LOG_LINES`

### Validation results

All validation criteria from the implementation plan pass:

| Test | Command | Result |
|------|---------|--------|
| Unit tests | `uv run pytest tests/unit/ -v` | 281 passed |
| Linting | `uv run ruff check src/` | All checks passed |
| Type checking | `uv run mypy src/` | Success: no issues found in 23 source files |

### Files created

```
src/act/verifier/exceptions.py
src/act/verifier/response.py
src/act/verifier/logs.py
src/act/verifier/container.py
src/act/verifier/pipeline.py
src/act/verifier/executor.py
src/act/verifier/__init__.py (updated with exports)
tests/unit/test_verifier_exceptions.py (13 tests)
tests/unit/test_verifier_response.py (20 tests)
tests/unit/test_verifier_logs.py (22 tests)
tests/unit/test_verifier_container.py (31 tests)
tests/unit/test_verifier_pipeline.py (22 tests)
tests/unit/test_verifier_executor.py (26 tests)
```

### Dependencies

- Uses `docker` package (already in dependencies from Phase 0)
- Integrates with `act.artifacts` module for run directory, manifest, and timestamps
- Integrates with `act.config` module for AgentConfig and VerificationStep

### Design decisions

1. **Lazy Docker client initialization** - Client created on first use, not at construction
2. **Mocked Docker for unit tests** - All tests use mocked Docker client (no Docker required)
3. **Thread-based timeout** - Uses threading.Thread for command timeout (more portable than signals)
4. **contextlib.suppress for cleanup** - Gracefully handles already-stopped containers
5. **Environment as list of strings** - Docker SDK expects `["KEY=VALUE"]` format for env vars

### Next steps

Proceed to **Phase 3: Scouts — Read-Only Analysis Components** as defined in `specs/implementation-plan.md`.

---

## Phase 3: Scouts — Read-Only Analysis Components (Completed)

**Date:** 2026-01-05

### What was implemented

#### 3.1 Scout Infrastructure (Shared)

**3.1.1 Exception Hierarchy** (`src/act/scouts/exceptions.py`)
- `ScoutError` - Base exception for all Scout errors
- `LLMError(ScoutError)` - LLM communication errors with error type
- `SchemaError(ScoutError)` - Schema validation errors with payload
- `RetryExhaustedError(ScoutError)` - All retries exhausted with attempt count
- `FileExclusionError(ScoutError)` - File exclusion filter errors
- `ScoutErrorType` enum: `LLM_UNAVAILABLE`, `LLM_TIMEOUT`, `LLM_RATE_LIMIT`, `LLM_RESPONSE_INVALID`, `SCHEMA_VALIDATION`, `RETRY_EXHAUSTED`, `UNKNOWN`

**3.1.2 File Exclusion Filter** (`src/act/scouts/file_filter.py`)
- `BINARY_EXTENSIONS` - Frozen set of binary file extensions (.png, .jpg, .exe, .dll, .zip, etc.)
- `SECRET_PATTERNS` - Tuple of secret file patterns (.env, *credentials*, *secrets*, *.pem, etc.)
- `EXCLUDED_DIRECTORIES` - Frozen set of excluded directories (.git, node_modules, __pycache__, etc.)
- Functions:
  - `is_binary_file()` - Check if file is binary by extension
  - `is_secret_file()` - Check if file matches secret patterns
  - `is_excluded_directory()` - Check if directory should be excluded
  - `should_exclude_file()` - Combined binary/secret check
  - `should_exclude_path()` - Full path exclusion check
  - `filter_files()` - Filter file list
  - `discover_files()` - Walk directory and discover analyzable files

**3.1.3 Retry with Exponential Backoff** (`src/act/scouts/retry.py`)
- Default configuration: 3 retries, 1s initial delay, 2x multiplier, 10s max delay
- Backoff pattern: 1s, 2s, 4s
- `calculate_delay()` - Calculate delay for given attempt
- `is_retryable_error()` - Determine if error should trigger retry
- `retry_sync()` - Synchronous retry wrapper
- `retry_async()` - Asynchronous retry wrapper
- `RetryConfig` dataclass with `calculate_total_wait_time()`

**3.1.4 LLM Client** (`src/act/scouts/llm_client.py`)
- `LLMMessage` dataclass: role, content
- `LLMResponse` dataclass: content, raw_response, model, usage
- `LLMClient` class:
  - Supports Anthropic, OpenAI, and custom OpenAI-compatible endpoints
  - `query()` - Single query to LLM
  - `query_with_retry()` - Query with automatic retry on transient failures
  - `query_json()` - Query and parse JSON response (handles markdown code blocks)
- Default models: `claude-sonnet-4-20250514` (Anthropic), `gpt-4o` (OpenAI)
- Timeout handling with `TimeoutError`
- Error classification for rate limits, connection issues

#### 3.2 Scout Schemas (v1) (`src/act/scouts/schemas.py`)

**Scout A Response Schema:**
- `RelevantFile` - path, purpose, relevance (primary/secondary/context)
- `RepoMap` - relevant_files, entry_points, dependency_graph
- `RiskZone` - file, start_line, end_line, risk_level, complexity, dependencies, invariants, rationale
- `SafeSlice` - id, files, description, complexity, order
- `ChangeBoundaries` - safe_slices, ordering_constraints
- `Conventions` - naming, patterns, anti_patterns
- `PriorArt` - file, description, relevance
- `ScoutAResponse` - Full response with all fields and `to_dict()` method

**Scout B Response Schema:**
- `BuildCommands` - install, build, clean
- `BuildInfo` - detected_system, commands, prerequisites, notes
- `TestCommands` - all, unit, integration
- `TestInfo` - detected_framework, commands, coverage_command, notes
- `FailureAnalysis` - root_cause, affected_files, suggested_investigation, is_flaky, flaky_reason
- `EnvironmentIssue` - issue, severity (blocking/warning), suggested_fix
- `ScoutBResponse` - Full response with all fields and `to_dict()` method

**Enums:**
- `Relevance` - PRIMARY, SECONDARY, CONTEXT
- `RiskLevel` - LOW, MEDIUM, HIGH
- `Complexity` - LOW, MEDIUM, HIGH
- `Severity` - BLOCKING, WARNING
- `BuildSystem` - NPM, YARN, PNPM, MAKE, CARGO, GO, GRADLE, MAVEN, CUSTOM
- `TestFramework` - JEST, PYTEST, GO_TEST, CARGO_TEST, JUNIT, MOCHA, VITEST, CUSTOM

**Validation Functions:**
- `validate_scout_a_response()` - Validate and parse Scout A response
- `validate_scout_b_response()` - Validate and parse Scout B response
- Schema version: `"1"` (fixed, versioned)

#### 3.3 Scout A (Codebase Mapper) (`src/act/scouts/scout_a.py`)

- System prompt with JSON schema v1 and read-only constraints
- `ScoutA` class:
  - `reset_context()` - Clear conversation history
  - `query()` - Query with optional file list discovery
  - `analyze_files()` - Query with specific file contents
  - `find_relevant_files()` - Find files for a task
  - `analyze_risk_zones()` - Analyze risk zones in files
  - `identify_conventions()` - Identify code conventions
  - `get_raw_response()` - Get last raw JSON response
- Constants: `MAX_FILES_IN_CONTEXT = 100`, `MAX_FILE_CONTENT_SIZE = 50000`
- Maintains conversation history for multi-turn queries
- Factory function: `create_scout_a()`

#### 3.4 Scout B (Build/Test Detective) (`src/act/scouts/scout_b.py`)

- System prompt with JSON schema v1 and read-only constraints
- `BUILD_CONFIG_FILES` - List of build/test config files to detect (package.json, pyproject.toml, Cargo.toml, go.mod, Makefile, jest.config.*, pytest.ini, etc.)
- `ScoutB` class:
  - `reset_context()` - Clear conversation history
  - `query()` - Query with optional build configs and log content
  - `discover_build_commands()` - Discover build system and commands
  - `discover_test_commands()` - Discover test framework and commands
  - `analyze_failure()` - Analyze build/test failure logs
  - `detect_environment_issues()` - Detect environment problems
  - `full_discovery()` - Complete build/test infrastructure analysis
  - `get_raw_response()` - Get last raw JSON response
- Constants: `MAX_LOG_SIZE = 20000`
- Auto-detects and includes build config files in queries
- Factory function: `create_scout_b()`

#### 3.5 Public API (`src/act/scouts/__init__.py`)

Exports all Scout components:
- Exceptions: `ScoutError`, `LLMError`, `SchemaError`, `RetryExhaustedError`, `FileExclusionError`, `ScoutErrorType`
- File filter: All filter functions and constants
- Retry: `RetryConfig`, `retry_sync`, `retry_async`, `calculate_delay`, `is_retryable_error`
- LLM client: `LLMClient`, `LLMMessage`, `LLMResponse`, `create_llm_client`
- Schemas: All dataclasses, enums, and validation functions
- Scout A: `ScoutA`, `create_scout_a`, `SCOUT_A_SYSTEM_PROMPT`
- Scout B: `ScoutB`, `create_scout_b`, `SCOUT_B_SYSTEM_PROMPT`, `BUILD_CONFIG_FILES`

### Validation results

All validation criteria from the implementation plan pass:

| Test | Command | Result |
|------|---------|--------|
| Unit tests | `uv run pytest tests/unit/ -v` | 444 passed |
| Linting | `uv run ruff check src/` | All checks passed |
| Type checking | `uv run mypy src/` | Success: no issues found in 30 source files |

### Files created

```
src/act/scouts/exceptions.py
src/act/scouts/file_filter.py
src/act/scouts/retry.py
src/act/scouts/llm_client.py
src/act/scouts/schemas.py
src/act/scouts/scout_a.py
src/act/scouts/scout_b.py
src/act/scouts/__init__.py (updated with exports)
tests/unit/test_scouts_exceptions.py (17 tests)
tests/unit/test_scouts_file_filter.py (34 tests)
tests/unit/test_scouts_retry.py (22 tests)
tests/unit/test_scouts_llm_client.py (20 tests)
tests/unit/test_scouts_schemas.py (35 tests)
tests/unit/test_scouts_scout_a.py (17 tests)
tests/unit/test_scouts_scout_b.py (18 tests)
```

### Dependencies

- Uses `anthropic` and `openai` packages (already in dependencies from Phase 0)
- Integrates with `act.config.env` module for `LLMConfig` and `LLMBackend`

### Design decisions

1. **Separate LLM context per Scout** - Each Scout instance maintains its own conversation history
2. **Schema versioning** - Fixed schema v1 with validation on parse
3. **Lazy SDK initialization** - Anthropic/OpenAI clients created on first use
4. **Thread pool for sync APIs** - Uses `run_in_executor` for blocking SDK calls in async context
5. **JSON extraction from markdown** - Handles ```json code blocks in LLM responses
6. **Comprehensive file exclusion** - Binary files, secrets, and common non-source directories excluded
7. **Pull-based architecture** - Scouts are queried by Editor, not push-based

### Next steps

Proceed to **Phase 4: Editor — Orchestrator** as defined in `specs/implementation-plan.md`.

---

## Phase 4: Editor — Orchestrator (Completed)

**Date:** 2026-01-05

### What was implemented

#### 4.1 Exception Hierarchy (`src/act/editor/exceptions.py`)

- `EditorErrorType` enum: `TASK_PARSE`, `SCOUT_FAILURE`, `VERIFICATION_FAILURE`, `IMPLEMENTATION`, `WRITE_BOUNDARY`, `HARD_STOP`, `INFRA_ERROR`, `UNKNOWN`
- `EditorError` - Base exception for all Editor errors with error type
- `TaskParseError(EditorError)` - Task parsing errors
- `ScoutCoordinationError(EditorError)` - Scout query failures with scout name
- `ImplementationError(EditorError)` - Code implementation errors with file path
- `WriteBoundaryError(EditorError)` - Writes outside allowed boundaries with path and boundary info
- `HardStopError(EditorError)` - Hard stop threshold reached with attempt count and run IDs
- `InfrastructureError(EditorError)` - Infrastructure failures with source and original error

#### 4.2 Task Parser (`src/act/editor/task.py`)

- `TaskConstraints` dataclass:
  - `must_preserve` - Files/behaviors that must not change
  - `non_goals` - Explicitly out-of-scope items
  - `boundaries` - Limits on what can be modified
- `SuccessCriteria` dataclass:
  - `acceptance_criteria` - Specific conditions for success
  - `behavior_changes` - Expected behavior changes
- `ParsedTask` dataclass:
  - `raw_description` - Original task description
  - `main_objective` - Primary goal extracted
  - `constraints` - TaskConstraints instance
  - `success_criteria` - SuccessCriteria instance
  - `to_dict()` - Serialization method
- Functions:
  - `parse_task()` - Parse free-form task description into structured format
  - `validate_task()` - Validate parsed task and return warnings
- Extracts constraints from markdown sections (Constraints:, Non-goals:, Boundaries:)
- Infers success criteria from task verbs (fix, add, refactor, test, update)

#### 4.3 Scout Coordination (`src/act/editor/coordinator.py`)

- `ScoutResults` dataclass:
  - `scout_a_response` - ScoutAResponse or None
  - `scout_b_response` - ScoutBResponse or None
  - `scout_a_raw` - Raw JSON dict from Scout A
  - `scout_b_raw` - Raw JSON dict from Scout B
  - `conflict_resolution` - Resolution rationale if conflicts existed
  - `has_scout_a()`, `has_scout_b()` - Check response availability
  - `to_dict()` - Serialization method
- `ScoutCoordinator` class:
  - `reset()` - Clear Scout contexts for new task
  - `query_scouts_parallel()` - Query both Scouts concurrently
  - `query_scout_a()` - Query Scout A only (with optional file contents)
  - `query_scout_b()` - Query Scout B only (with optional log content)
  - `analyze_failure()` - Analyze verification failure via Scout B
  - `initial_analysis()` - Combined initial analysis for new task
  - `resolve_conflict()` - Autonomous conflict resolution (prefers Scout B for build/test, Scout A for code)
  - `get_last_results()` - Access last query results
- Factory function: `create_scout_coordinator()`
- Wraps Scout errors into `InfrastructureError` or `ScoutCoordinationError`

#### 4.4 Debug Loop (`src/act/editor/debug_loop.py`)

- Constants:
  - `CONSECUTIVE_FAILURE_THRESHOLD = 3` - Triggers REPLAN
  - `TOTAL_VERIFY_LOOP_THRESHOLD = 12` - Triggers hard stop
  - `MAX_REPLANS = 3` - Maximum REPLANs (at attempts 3, 6, 9)
- `LoopAction` enum: `CONTINUE`, `REPLAN`, `HARD_STOP`, `SUCCESS`
- `VerifyAttempt` dataclass: run_id, passed, failure_summary, attempt_number
- `DebugLoopState` dataclass:
  - `consecutive_failures` - Counter (resets on REPLAN)
  - `total_verify_loops` - Counter (never resets except on success)
  - `replan_count` - Number of REPLANs triggered
  - `attempts` - List of all verification attempts
  - `current_hypothesis` - Current strategy being tested
  - `strategy_history` - List of all strategies tried
  - `to_dict()`, `get_all_run_ids()` - Utility methods
- `DebugLoop` class:
  - `reset()` - Reset for new task
  - `record_success()` - Record pass, return SUCCESS
  - `record_failure()` - Record fail, return CONTINUE/REPLAN/HARD_STOP
  - `trigger_replan()` - Reset consecutive counter, increment replan count
  - `set_hypothesis()` - Update current hypothesis
  - `should_requery_scouts()` - Determine if Scouts need re-query
  - `get_failure_summary()` - Markdown summary of all failures
  - `get_attempt_count_display()` - Human-readable "Attempt N/12"
- Factory function: `create_debug_loop()`

#### 4.5 Output Generators (`src/act/editor/outputs.py`)

- `STUCK_REPORT_FILENAME = "stuck_report.md"`
- `SuccessSummary` dataclass:
  - `task_description`, `what_changed`, `why`, `how_verified`, `run_id`
  - `files_modified` - List of modified files
  - `timestamp` - UTC timestamp
  - `to_markdown()` - Generate markdown summary
- `StuckReportHypothesis` dataclass:
  - `title`, `description`, `suggested_investigation`
- `StuckReport` dataclass:
  - `task_description`, `constraints`, `status`
  - `hypotheses` - List of StuckReportHypothesis
  - `verification_history` - List of attempt records
  - `artifact_references` - List of run IDs
  - `files_modified`, `is_infra_error`, `infra_error_source`, `infra_error_message`
  - `to_markdown()` - Generate comprehensive markdown report
- Functions:
  - `generate_success_summary()` - Create SuccessSummary from task/run data
  - `generate_stuck_report_hypotheses()` - Autonomously generate hypotheses from failure patterns
  - `generate_stuck_report()` - Create StuckReport from task/loop state
  - `write_stuck_report()` - Write report to agent directory
  - `read_stuck_report()` - Read existing report
  - `has_stuck_report()` - Check if report exists
- Hypothesis patterns: import/module errors, type errors, timeouts, permissions, too many replans, large change scope

#### 4.6 Dry-Run Mode (`src/act/editor/dry_run.py`)

- `FileChange` dataclass:
  - `relative_path`, `original_content`, `new_content`
  - `is_new_file`, `is_deletion`
  - `to_unified_diff()` - Generate unified diff output
- `DryRunProposal` dataclass:
  - `changes` - List of FileChange
  - `timestamp` - Creation timestamp
  - `to_markdown()` - Generate markdown proposal
- `DryRunManager` class:
  - `start()` - Begin dry-run mode
  - `is_active` - Check if active
  - `propose_file_change()` - Stage a file change
  - `propose_file_deletion()` - Stage a file deletion
  - `get_diff()` - Get combined unified diff
  - `apply_changes()` - Write all changes to filesystem
  - `discard_changes()` - Discard without applying
  - `reset()` - Clear state
- Factory function: `create_dry_run_manager()`
- Function: `format_proposal_output()` - Format proposal for display

#### 4.7 Write Boundaries (`src/act/editor/boundaries.py`)

- `WriteBoundaryEnforcer` class:
  - `validate_path()` - Ensure path is within repo or agent directory
  - `is_in_repo()` - Check if path is in repository
  - `is_in_agent_dir()` - Check if path is in agent/ directory
  - `is_in_artifact_dir()` - Check if path is in artifact directory (NOT allowed for write)
  - `get_relative_path()` - Get path relative to repo root
- Factory function: `create_boundary_enforcer()`
- Prevents writes outside repo + agent/ boundaries
- Explicitly blocks writes to artifact directory

#### 4.8 Main Editor Orchestrator (`src/act/editor/editor.py`)

- `WorkflowState` enum: `IDLE`, `ANALYZING`, `IMPLEMENTING`, `VERIFYING`, `DEBUGGING`, `REPLANNING`, `COMPLETED`, `STUCK`, `INFRA_ERROR`
- `EditorContext` dataclass:
  - `task` - Current ParsedTask
  - `scout_results` - Latest ScoutResults
  - `files_modified` - List of modified files
  - `current_hypothesis` - Current strategy
  - `last_verification` - Last VerifierResponse
  - `dry_run_mode` - Whether in dry-run mode
  - `to_dict()` - Serialization method
- `Editor` class:
  - Properties: `state`, `context`, `debug_loop`, `coordinator`, `dry_run_manager`, `boundary_enforcer`
  - `reset()` - Reset for new task
  - `start_task()` - Begin new task (with optional dry-run)
  - `analyze_codebase()` - Perform initial Scout analysis
  - `validate_write_path()` - Validate path against boundaries
  - `record_file_modification()` - Track modified files
  - `handle_verification_result()` - Process verification response, determine next action
  - `trigger_replan()` - Execute REPLAN with optional Scout re-query
  - `generate_success_summary()` - Create success summary
  - `generate_stuck_report()` - Create and write stuck report
  - `get_dry_run_proposal()` - Get current proposal
  - `apply_dry_run_changes()` - Apply dry-run changes
  - `discard_dry_run_changes()` - Discard dry-run changes
  - `get_status_message()` - Human-readable status
- Creates context snapshots at milestones (TASK_START, REPLAN, TASK_SUCCESS)
- Checks for existing stuck report on task resume
- Factory function: `create_editor()`

#### 4.9 Public API (`src/act/editor/__init__.py`)

Exports all Editor components:
- Exceptions: `EditorError`, `EditorErrorType`, `TaskParseError`, `ScoutCoordinationError`, `ImplementationError`, `WriteBoundaryError`, `HardStopError`, `InfrastructureError`
- Task parsing: `ParsedTask`, `TaskConstraints`, `SuccessCriteria`, `parse_task`, `validate_task`
- Scout coordination: `ScoutCoordinator`, `ScoutResults`, `create_scout_coordinator`
- Debug loop: `DebugLoop`, `DebugLoopState`, `LoopAction`, `VerifyAttempt`, `create_debug_loop`, `CONSECUTIVE_FAILURE_THRESHOLD`, `TOTAL_VERIFY_LOOP_THRESHOLD`, `MAX_REPLANS`
- Outputs: `SuccessSummary`, `StuckReport`, `StuckReportHypothesis`, `generate_success_summary`, `generate_stuck_report`, `generate_stuck_report_hypotheses`, `write_stuck_report`, `read_stuck_report`, `has_stuck_report`, `STUCK_REPORT_FILENAME`
- Dry-run: `DryRunManager`, `DryRunProposal`, `FileChange`, `create_dry_run_manager`, `format_proposal_output`
- Boundaries: `WriteBoundaryEnforcer`, `create_boundary_enforcer`
- Main Editor: `Editor`, `EditorContext`, `WorkflowState`, `create_editor`

### Validation results

All validation criteria from the implementation plan pass:

| Test | Command | Result |
|------|---------|--------|
| Unit tests | `uv run pytest tests/unit/ -v` | 644 passed |
| Linting | `uv run ruff check src/act/editor/` | All checks passed |
| Type checking | `uv run mypy src/act/editor/` | Success: no issues found in 9 source files |

### Files created

```
src/act/editor/exceptions.py
src/act/editor/task.py
src/act/editor/coordinator.py
src/act/editor/debug_loop.py
src/act/editor/outputs.py
src/act/editor/dry_run.py
src/act/editor/boundaries.py
src/act/editor/editor.py
src/act/editor/__init__.py (updated with exports)
tests/unit/test_editor_exceptions.py (19 tests)
tests/unit/test_editor_task.py (21 tests)
tests/unit/test_editor_coordinator.py (22 tests)
tests/unit/test_editor_debug_loop.py (29 tests)
tests/unit/test_editor_outputs.py (27 tests)
tests/unit/test_editor_dry_run.py (27 tests)
tests/unit/test_editor_boundaries.py (19 tests)
tests/unit/test_editor_editor.py (36 tests)
```

### Dependencies

- Integrates with `act.config` module for `AgentConfig`, `LLMConfig`, `EnvConfig`
- Integrates with `act.artifacts` module for context snapshots and agent directory
- Integrates with `act.scouts` module for Scout A/B coordination
- Integrates with `act.verifier` module for VerifierResponse handling

### Design decisions

1. **Pull-based Scout queries** - Editor initiates all Scout queries; Scouts never push data
2. **Autonomous conflict resolution** - Editor resolves Scout disagreements without user input
3. **Fix-forward strategy** - Never revert on failure; diagnose and fix forward
4. **Immutable constraints** - Task constraints are extracted once and never modified
5. **Hypothesis tracking** - Each REPLAN records the new strategy for debugging
6. **Context snapshots only at milestones** - Reduces noise; snapshots at TASK_START, REPLAN, TASK_SUCCESS only
7. **Dry-run as separate mode** - Changes staged in memory until explicit apply/discard
8. **Strict write boundaries** - Only repo/ and agent/ are writable; artifact dir is read-only from Editor perspective

### Next steps

Proceed to **Phase 5: Integration — CLI Entry Points** as defined in `specs/implementation-plan.md`.

---
