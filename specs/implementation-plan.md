# Implementation Plan

This document provides a step-by-step implementation plan for the AgentCommandTool system. Each step is small, specific, and includes a validation test.

---

## Phase 1: Foundation — Configuration and Artifact Infrastructure

### 1.1 Configuration Parser

**Step 1.1.1: Create `agent.yaml` schema validator**

- Implement YAML parser that validates against the expected schema
- Required fields: `verification.container_image`, `verification.steps[]`
- Each step requires `name` and `command` fields

**Test:** Create sample `agent.yaml` files (valid and invalid). Validator returns success for valid files, returns specific error messages for missing `container_image`, missing steps, and malformed YAML.

---

**Step 1.1.2: Implement environment variable loader**

- Read `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AGENT_LLM_BASE_URL`, `AGENT_LLM_MODEL`
- Implement priority: custom endpoint > Anthropic > OpenAI
- Read `AGENT_ARTIFACT_DIR` with default `~/.agent-artifacts/`

**Test:** Set various env var combinations. Verify correct backend selected per priority rules. Verify default artifact dir used when env var unset.

---

**Step 1.1.3: Implement configuration validation on startup**

- Check `agent.yaml` exists in repo root
- Validate at least one verification step defined
- Validate Docker is available (run `docker info`)
- Validate LLM API key present

**Test:** Start system with missing `agent.yaml` → error "configuration required". Start with no API key → error "cannot proceed without model access". Start with Docker stopped → error about Docker unavailable.

---

### 1.2 Artifact Directory Infrastructure

**Step 1.2.1: Create ARTIFACT_DIR directory structure**

- Create `runs/` subdirectory
- Create `cache/` subdirectory
- Handle existing directory gracefully

**Test:** Run initializer on fresh path → directories created. Run again on existing path → no error, structure unchanged.

---

**Step 1.2.2: Implement run_id generator**

- Format: `run_{YYYYMMDD}_{HHMMSS}_{random6chars}`
- Ensure uniqueness via random suffix
- Create run directory: `ARTIFACT_DIR/runs/{run_id}/`

**Test:** Generate 100 run_ids in quick succession → all unique. Directory created at expected path.

---

**Step 1.2.3: Implement manifest.json writer**

- Write manifest with: `run_id`, `timestamp_start`, `timestamp_end`, `commit_sha`, `commands_executed[]`, `platform{}`
- Each command entry: `name`, `command`, `exit_code`, `duration_ms`

**Test:** Execute mock verification, write manifest. Read manifest back → all fields present and correctly typed. `commit_sha` matches current HEAD.

---

**Step 1.2.4: Implement artifact retention cleanup**

- Count runs in ARTIFACT_DIR
- Delete oldest runs when count > 20
- Delete runs older than 14 days
- Skip runs associated with stuck reports

**Test:** Create 25 mock run directories with varied timestamps. Run cleanup → exactly 20 remain, oldest 5 deleted. Create run older than 14 days → deleted regardless of count.

---

### 1.3 Context File Infrastructure

**Step 1.3.1: Create agent/ directory initializer**

- Create `agent/` directory in repo root if not exists
- Add `agent/` to `.gitignore` if not already present (append, don't overwrite)

**Test:** Run on repo without `agent/` dir → created. Check `.gitignore` → contains `agent/`. Run again → no duplicate entry added.

---

**Step 1.3.2: Implement context snapshot writer**

- Generate incrementing snapshot number: `context_001.md`, `context_002.md`, etc.
- Write markdown with: timestamp, milestone type, raw Scout payloads, Editor state
- Update `context_latest.md` symlink (or copy on Windows)

**Test:** Write first snapshot → `context_001.md` created, `context_latest.md` points to it. Write second → `context_002.md` created, `context_latest.md` updated.

---

**Step 1.3.3: Implement context snapshot triggers**

- Create snapshot on: task start, REPLAN event, task success
- Do NOT create snapshot on: each Scout query, each verify attempt, each fix iteration

**Test:** Mock task execution with 3 verify attempts and 1 REPLAN. Count snapshots → exactly 3 (start, REPLAN, success). Not 3 + 3 extra.

---

## Phase 2: Verifier — Sandboxed Execution

### 2.1 Docker Container Management

**Step 2.1.1: Implement container creation with read-only repo mount**

- Create ephemeral container from configured `container_image`
- Mount repository at `/workspace` as read-only
- Mount ARTIFACT_DIR at `/artifacts` as read-write

**Test:** Create container, attempt to write file in `/workspace` → command fails with permission error. Write to `/artifacts` → succeeds.

---

**Step 2.1.2: Implement container lifecycle management**

- Fresh container per verification run (no reuse)
- Automatic container destruction after run completes
- Handle container creation failure gracefully

**Test:** Run verification → container created. Check after completion → container removed (`docker ps -a` shows no orphan). Simulate image pull failure → `INFRA_ERROR` returned with `error_type: image_pull`.

---

**Step 2.1.3: Implement resource limits**

- Set reasonable CPU and memory limits via Docker
- Handle resource exhaustion gracefully

**Test:** Configure very low memory limit, run memory-intensive command → fails gracefully with `INFRA_ERROR` and `error_type: resource_exhaustion`, not system crash.

---

### 2.2 Pipeline Execution

**Step 2.2.1: Implement sequential step execution**

- Read steps from `agent.yaml`
- Execute each step in order
- Stop on first non-zero exit code

**Test:** Configure 3 steps where step 2 fails. Run pipeline → step 1 executes, step 2 fails, step 3 never runs. Logs show step 1 and step 2 only.

---

**Step 2.2.2: Implement per-step logging**

- Capture stdout and stderr for each step
- Write to `logs/step-{nn}-{name}.log`
- Write combined output to `logs/combined.log`

**Test:** Run pipeline with 3 steps. Check `runs/{run_id}/logs/` → contains `step-01-install.log`, `step-02-build.log`, `step-03-test.log`, and `combined.log`.

---

**Step 2.2.3: Implement step timeout handling**

- Apply `timeouts.verification_step` from config (default 5 min)
- Kill step on timeout
- Treat timeout as failure (not INFRA_ERROR)

**Test:** Configure 1-second timeout, run `sleep 10` as step → step killed after 1 second, status is `FAIL` (not `INFRA_ERROR`).

---

**Step 2.2.4: Implement test write redirection**

- Set environment variables: `TMPDIR=/artifacts/tmp`, `TEST_DB_PATH=/artifacts/db`
- Create these directories before pipeline runs

**Test:** Run test that writes to `$TMPDIR` → file appears in `ARTIFACT_DIR/runs/{run_id}/tmp/`, not in repo.

---

### 2.3 Output Contract

**Step 2.3.1: Implement PASS response**

- Return when all steps exit 0
- Include: `status: "PASS"`, `run_id`, `tail_log` (last 200 lines), `artifact_paths[]`, `manifest`

**Test:** Run passing pipeline → response has all required fields, `status` is `"PASS"`, no `error_type` field.

---

**Step 2.3.2: Implement FAIL response**

- Return when any step exits non-zero
- Same structure as PASS but `status: "FAIL"`
- `tail_log` shows failure output

**Test:** Run failing pipeline → `status` is `"FAIL"`, `tail_log` contains error message from failing step.

---

**Step 2.3.3: Implement INFRA_ERROR response**

- Return for: Docker unavailable, container creation fail, image pull fail, resource exhaustion
- Include: `error_type`, `error_message`
- Optional fields (may be null): `run_id`, `tail_log`, `manifest`

**Test:** Stop Docker daemon, trigger verification → `status: "INFRA_ERROR"`, `error_type: "docker_unavailable"`, `run_id` is null.

---

**Step 2.3.4: Implement tail_log extraction**

- Extract last 200 lines of combined log
- Handle logs shorter than 200 lines
- Handle empty logs

**Test:** Generate 500-line log → `tail_log` has exactly 200 lines (last ones). Generate 50-line log → `tail_log` has all 50 lines.

---

## Phase 3: Scouts — Read-Only Analyzers

### 3.1 Scout Infrastructure (Shared)

**Step 3.1.1: Implement Scout LLM client**

- Create LLM client using configured backend
- Separate context window per Scout instance
- Include schema version in system prompt

**Test:** Create Scout A and Scout B clients → each has independent conversation history. Query Scout A → Scout B context unchanged.

---

**Step 3.1.2: Implement file exclusion filter**

- Exclude binary files: `.png`, `.jpg`, `.gif`, `.exe`, `.dll`, `.so`, `.zip`, etc.
- Exclude secret files: `.env`, `*credentials*`, `*secrets*`
- Apply to all Scout file analysis

**Test:** Create repo with `.env`, `secrets.json`, `image.png`, `code.js`. Run Scout file discovery → only `code.js` in results.

---

**Step 3.1.3: Implement retry with exponential backoff**

- On Scout query failure: retry up to 3 times
- Backoff: 1s, 2s, 4s (exponential)
- After 3 failures: return INFRA_ERROR

**Test:** Mock LLM to fail twice then succeed → query succeeds on 3rd attempt. Mock LLM to fail 3 times → INFRA_ERROR returned after ~7 seconds total.

---

**Step 3.1.4: Implement query timeout**

- Apply `timeouts.scout_query` from config (default 60s)
- Timeout triggers retry flow

**Test:** Configure 1-second timeout, mock slow LLM response → timeout triggers retry. After 3 timeouts → INFRA_ERROR.

---

### 3.2 Scout A (Codebase Mapper)

**Step 3.2.1: Implement Scout A system prompt**

- Define role as read-only codebase analyst
- Include JSON schema (v1) for output format
- Instruct on file/pattern/API/invariant discovery

**Test:** Query Scout A about auth files → response parses as valid JSON matching schema v1. Contains `repo_map`, `risk_zones`, `change_boundaries`.

---

**Step 3.2.2: Implement repo_map generation**

- `relevant_files[]` with path, purpose, relevance (primary/secondary/context)
- `entry_points[]` identification
- `dependency_graph` construction

**Test:** Query Scout A on simple project → `relevant_files` contains actual project files (not node_modules). `relevance` values are valid enum values.

---

**Step 3.2.3: Implement risk_zone mapping**

- For each zone: file, start_line, end_line, risk_level, complexity, dependencies, invariants, rationale
- All enum fields use valid values (low/medium/high)

**Test:** Query Scout A about modifying a function → response includes risk_zone with valid line numbers that exist in file. `risk_level` and `complexity` are valid enums.

---

**Step 3.2.4: Implement safe_slice definition**

- Each slice: id, files[], description, complexity, order
- Include ordering_constraints for dependencies

**Test:** Query Scout A about multi-file change → `safe_slices` returned with valid file paths. If order matters, `ordering_constraints` explains why.

---

**Step 3.2.5: Implement conventions extraction**

- `naming` conventions
- `patterns[]` used in codebase
- `anti_patterns[]` to avoid

**Test:** Query Scout A on TypeScript project → `conventions.naming` mentions camelCase or similar. `patterns` lists actual patterns found.

---

### 3.3 Scout B (Build/Test Detective)

**Step 3.3.1: Implement Scout B system prompt**

- Define role as build/test infrastructure analyst
- Include JSON schema (v1) for output format
- Instruct on build/test command discovery and failure interpretation

**Test:** Query Scout B about build commands → response parses as valid JSON matching schema v1. Contains `build`, `test` sections.

---

**Step 3.3.2: Implement build command discovery**

- Detect build system: npm/yarn/pnpm/make/cargo/go/gradle/maven/custom
- Extract commands: install, build, clean
- List prerequisites

**Test:** Query Scout B on npm project → `build.detected_system` is "npm". `build.commands.build` contains valid npm command.

---

**Step 3.3.3: Implement test command discovery**

- Detect test framework: jest/pytest/go test/cargo test/junit/mocha/custom
- Extract commands: all, unit, integration
- Include coverage_command if available

**Test:** Query Scout B on Jest project → `test.detected_framework` is "jest". `test.commands.all` contains valid Jest invocation.

---

**Step 3.3.4: Implement failure analysis**

- Parse Verifier logs to determine root_cause
- Identify affected_files
- Provide suggested_investigation steps
- Flag is_flaky with reason if applicable

**Test:** Feed Scout B a TypeScript compilation error log → `failure_analysis.root_cause` identifies the type error. `affected_files` lists the file with error.

---

**Step 3.3.5: Implement environment issue detection**

- Detect: missing dependencies, version mismatches, permission issues
- Classify severity: blocking vs warning
- Provide suggested_fix (informational only)

**Test:** Feed Scout B "node: command not found" error → `environment_issues[]` contains entry with `issue` about Node, `severity: "blocking"`, `suggested_fix` about installation.

---

## Phase 4: Editor — Orchestrator

### 4.1 Task Interpretation

**Step 4.1.1: Implement task parser**

- Accept free-form natural language task
- Extract optional constraints, non-goals, boundaries
- Store constraints as immutable (cannot be modified by REPLAN)

**Test:** Submit task with "Constraints:" section → constraints extracted and stored. Later REPLAN attempt → constraints still enforced.

---

**Step 4.1.2: Implement success criteria derivation**

- Parse task to understand behavior change expected
- Define acceptance criteria
- Identify non-goals

**Test:** Submit "Fix login timeout bug" → derived criteria includes "login works without timeout". Non-goals don't include refactoring.

---

### 4.2 Scout Coordination

**Step 4.2.1: Implement pull-based Scout queries**

- Editor initiates queries (not push from Scouts)
- Synchronous blocking calls
- Wait for response before proceeding

**Test:** Start task → Editor queries Scout A, waits for response, then proceeds. No parallel Scout execution unless Editor chooses.

---

**Step 4.2.2: Implement conflict resolution**

- When Scout A and Scout B disagree, Editor decides
- No escalation to user
- Document decision in context

**Test:** Mock conflicting Scout guidance → Editor picks one approach autonomously. No user prompt generated. Decision recorded in context file.

---

**Step 4.2.3: Implement context recording**

- Record raw Scout responses to context file
- No summarization or distillation
- Include Editor state (hypothesis, files modified, attempt count)

**Test:** Query both Scouts → `context_###.md` contains exact JSON payloads from both. Editor state section shows current attempt count.

---

### 4.3 Implementation

**Step 4.3.1: Implement minimal diff generation**

- Changes must be smallest safe slice per Scout A
- Follow existing code conventions (infer from sampling)
- No changes outside repo root

**Test:** Request simple bug fix → diff contains only lines necessary for fix. Style matches surrounding code. No unrelated refactoring.

---

**Step 4.3.2: Implement convention inference**

- Sample existing files for: indentation, naming, patterns
- Apply inferred conventions to new code

**Test:** In project using tabs and PascalCase → generated code uses tabs and PascalCase. In 2-space project → uses 2 spaces.

---

**Step 4.3.3: Implement test generation for uncovered code**

- Detect if repo has test suite
- If no tests exist, generate tests for changed code
- Auto-detect test framework from package files

**Test:** Modify code in project with no tests → tests generated. Tests use framework inferable from `package.json` (Jest) or similar.

---

**Step 4.3.4: Implement write boundary enforcement**

- Editor can write to repo and `agent/` only
- Reject any write outside repo root
- ARTIFACT_DIR is read-only for Editor

**Test:** Attempt to write to `/tmp/foo` → rejected with error. Attempt to write to `agent/context.md` → succeeds.

---

### 4.4 Debug Loop

**Step 4.4.1: Implement consecutive failure counter**

- Increment on each FAIL
- Reset on REPLAN or full green

**Test:** Three consecutive failures → counter at 3. REPLAN triggered → counter resets to 0. Next failure → counter at 1.

---

**Step 4.4.2: Implement total verify loop counter**

- Increment on each verify attempt
- Reset only on full green

**Test:** 6 failures, 1 REPLAN, 3 more failures → total counter at 9 (not reset by REPLAN). Success → counter resets to 0.

---

**Step 4.4.3: Implement REPLAN trigger**

- Fire when consecutive_failures reaches 3
- Generate new strategy autonomously
- Optionally re-query Scouts
- Create new context snapshot

**Test:** 3 consecutive failures → REPLAN fires. New context snapshot created. Strategy changed (implementation differs from previous approach).

---

**Step 4.4.4: Implement hard stop trigger**

- Fire when total_verify_loops reaches 12
- Takes precedence over REPLAN
- Generate stuck report

**Test:** At loop 12 with consecutive_failures at 3 → hard stop fires (not REPLAN). Stuck report generated with hypotheses.

---

**Step 4.4.5: Implement fix-forward strategy**

- On failure: keep broken state (no revert)
- Diagnose from Verifier logs
- Implement fix
- Re-verify

**Test:** Verification fails → working tree still contains failed changes. Editor analyzes logs, applies fix. Verify again.

---

**Step 4.4.6: Implement INFRA_ERROR immediate stop**

- On Verifier INFRA_ERROR: bypass debug loop
- Generate stuck report immediately
- Do not retry

**Test:** Verifier returns INFRA_ERROR → no retry attempts. Task immediately transitions to INFRA_ERROR state. Stuck report generated.

---

**Step 4.4.7: Implement Scout INFRA_ERROR handling**

- Scout fails 3 times → immediate stop
- Generate stuck report with infrastructure diagnosis
- Transition to INFRA_ERROR state

**Test:** Scout query fails 3 times with backoff → stuck report generated. State is INFRA_ERROR (not STUCK).

---

### 4.5 Outputs

**Step 4.5.1: Implement success summary generation**

- Prose markdown with: what changed, why, how verified
- Include `run_id` of passing verification
- Do NOT include commit message or PR description

**Test:** Task succeeds → summary generated. Contains `run_id`. Does not contain "commit message" or "PR" sections.

---

**Step 4.5.2: Implement stuck report generation**

- Hypotheses generated by Editor (Scouts not consulted)
- All artifact references (run_ids)
- Persisted for future retry

**Test:** Hard stop reached → stuck report contains 3+ hypotheses. Contains all 12 run_ids. File persists after task ends.

---

**Step 4.5.3: Implement working tree state preservation**

- On success: leave dirty (user commits manually)
- On cancel: preserve partial changes
- On stuck: leave dirty with stuck report

**Test:** Task succeeds → `git status` shows modified files. Task cancelled mid-way → partial changes remain.

---

### 4.6 Dry-Run Mode

**Step 4.6.1: Implement dry-run proposal generation**

- Analyze and plan as normal
- Generate proposed changes
- Do NOT write to filesystem
- Skip Verifier invocation

**Test:** Request dry-run → files unchanged on disk. Verifier never called (check logs).

---

**Step 4.6.2: Implement unified diff output**

- Format changes as git-style unified diff
- Show file paths, line numbers, context

**Test:** Dry-run produces diff → valid unified diff format. Can apply with `git apply`.

---

**Step 4.6.3: Implement dry-run apply flow**

- When user approves: write changes to filesystem
- Trigger full verification pipeline
- Enter normal debug loop if verification fails

**Test:** Apply dry-run changes → files written. Verification runs. On failure → enters debug loop (REPLAN at 3 failures).

---

## Phase 5: Task Lifecycle

### 5.1 Task Queue

**Step 5.1.1: Implement FIFO task queue**

- Sequential execution (no concurrency)
- Strict first-in-first-out ordering
- No priority levels or reordering

**Test:** Submit tasks A, B, C rapidly → execute in order A, B, C. No way to execute B before A finishes.

---

**Step 5.1.2: Implement queue viewing**

- List all queued tasks with position
- Show task descriptions

**Test:** Submit 3 tasks while one running → view shows 3 queued tasks with positions 1, 2, 3.

---

**Step 5.1.3: Implement pending task cancellation**

- Remove task from queue
- No artifacts created
- Remaining tasks shift up

**Test:** Cancel task at position 2 → task removed. Task formerly at position 3 now at position 2.

---

### 5.2 State Transitions

**Step 5.2.1: Implement QUEUED → RUNNING transition**

- Occurs when prior tasks complete
- Editor becomes active

**Test:** Submit task while queue empty → immediately RUNNING. Submit task while one running → QUEUED, then RUNNING when first completes.

---

**Step 5.2.2: Implement RUNNING → SUCCESS transition**

- Verifier returns PASS
- Summary generated
- Working tree left dirty

**Test:** Verification passes → state is SUCCESS. Summary file exists. `git status` shows changes.

---

**Step 5.2.3: Implement RUNNING → CANCELLED transition**

- User cancels mid-execution
- Partial changes preserved
- No artifact created

**Test:** Cancel running task → state is CANCELLED. Partial changes remain in working tree. No summary or stuck report.

---

**Step 5.2.4: Implement RUNNING → STUCK transition**

- 12 verify loops exhausted
- Stuck report generated
- Working tree left dirty

**Test:** Force 12 failures → state is STUCK (not INFRA_ERROR). Stuck report exists with all 12 run_ids.

---

**Step 5.2.5: Implement RUNNING → INFRA_ERROR transition**

- Verifier or Scout infrastructure failure
- Stuck report with infrastructure diagnosis
- Working tree preserved

**Test:** Simulate Docker failure → state is INFRA_ERROR. Stuck report mentions Docker. Different from STUCK state.

---

### 5.3 Status Updates

**Step 5.3.1: Implement push notification system**

- WebSocket or SSE for real-time updates
- Stream status milestones to client

**Test:** Connect WebSocket, start task → receive status updates as they occur. Updates arrive without polling.

---

**Step 5.3.2: Implement milestone messages**

- "Analyzing codebase..."
- "Querying Scout A..."
- "Implementing changes..."
- "Running verification..."
- "Verification failed, debugging..."
- "Attempt 3/12..."

**Test:** Run full task → client receives all relevant milestone messages in order. Attempt count updates correctly.

---

**Step 5.3.3: Implement on-demand detail expansion**

- Summary view by default
- Expand to see full failure logs, diagnosis, fix details

**Test:** Client requests expanded view → receives full Verifier logs and Editor diagnosis. Default view shows only milestones.

---

### 5.4 Future Retry

**Step 5.4.1: Implement stuck report loading**

- When resuming from stuck state: load stuck report
- Do NOT load full context history
- Access artifacts via run_id references

**Test:** Start task on repo with stuck report → Editor sees stuck report and hypotheses. Does not see previous Scout conversation history.

---

## Phase 6: Integration and Polish

### 6.1 End-to-End Flows

**Step 6.1.1: Integration test — success flow**

- Submit simple task (e.g., "Add console.log to main function")
- Full flow: Scouts → Implementation → Verification → Summary

**Test:** Task completes with SUCCESS state. Code change is correct. Summary references passing run_id.

---

**Step 6.1.2: Integration test — REPLAN flow**

- Submit task that requires REPLAN
- Verify 3 failures trigger REPLAN
- Verify new strategy attempted

**Test:** First approach fails 3 times → REPLAN fires. Second approach differs. Context snapshot created at REPLAN.

---

**Step 6.1.3: Integration test — hard stop flow**

- Submit impossible task
- Verify 12 iterations then stop
- Verify stuck report quality

**Test:** Task reaches 12 attempts → STUCK state. Stuck report contains useful hypotheses. All 12 run_ids present.

---

**Step 6.1.4: Integration test — INFRA_ERROR flow (Verifier)**

- Stop Docker mid-task
- Verify immediate stop
- Verify INFRA_ERROR state

**Test:** Docker stops → task immediately enters INFRA_ERROR. No retry attempts. Stuck report mentions infrastructure.

---

**Step 6.1.5: Integration test — INFRA_ERROR flow (Scout)**

- Block LLM API mid-task
- Verify 3 retries with backoff
- Verify INFRA_ERROR state

**Test:** LLM blocked → 3 retry attempts with delays. After 3rd failure → INFRA_ERROR state.

---

**Step 6.1.6: Integration test — cancellation flow**

- Start task, cancel mid-execution
- Verify partial changes preserved
- Verify queue continues

**Test:** Cancel running task → CANCELLED state. Partial changes in working tree. Next queued task starts.

---

**Step 6.1.7: Integration test — dry-run flow**

- Request dry-run
- Verify no filesystem changes
- Apply changes, verify full pipeline runs

**Test:** Dry-run → files unchanged. Apply → files written, verification runs. On failure → debug loop activates.

---

### 6.2 Error Handling

**Step 6.2.1: Implement graceful degradation**

- Handle unexpected errors without crashing
- Log errors with context
- Transition to appropriate terminal state

**Test:** Inject unexpected exception during Scout query → error logged. Task enters INFRA_ERROR (not crash).

---

**Step 6.2.2: Implement input validation**

- Validate task input is non-empty
- Validate `agent.yaml` on each task start
- Validate Docker available before RUNNING

**Test:** Submit empty task → rejected with clear error. Submit task with invalid `agent.yaml` → rejected with parse error details.

---

### 6.3 Observability

**Step 6.3.1: Implement structured logging**

- Log all state transitions
- Log all Scout queries and responses (summarized)
- Log all Verifier triggers and results

**Test:** Run task → logs show clear progression through states. Can reconstruct timeline from logs.

---

**Step 6.3.2: Implement metrics collection**

- Track: tasks by final state, average verification attempts, REPLAN frequency
- Track: Scout query latency, Verifier execution time

**Test:** Run 10 tasks → metrics show correct counts per state. Latency percentiles available.

---

## Appendix: Test Categories

### Unit Tests
- Configuration parsing
- Artifact management (run_id generation, manifest writing)
- Counter logic (consecutive, total)
- Schema validation

### Integration Tests
- Scout ↔ Editor communication
- Editor ↔ Verifier communication
- Full task flows

### Container Tests
- Read-only mount enforcement
- Artifact directory writes
- Container lifecycle (creation, destruction)

### System Tests
- Multi-task queue behavior
- Real-time status updates
- Stuck report persistence and reload
