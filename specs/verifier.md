# Verifier Specification

## Overview

The Verifier is a **sandboxed execution environment** that runs the configurable verification pipeline (build, tests, linting, etc.) and gates the "done" state on green status.

---

## Core Responsibilities

1. **Pipeline Execution**: Run configured verification steps
2. **Sandbox Enforcement**: Ensure repo isolation (read-only mount)
3. **Artifact Management**: Write logs and outputs to ARTIFACT_DIR
4. **Status Reporting**: Return PASS/FAIL with structured output
5. **Log Capture**: Provide tail logs and full artifact references

---

## Access Permissions

| Resource | Access |
|----------|--------|
| Repository | ✅ **Read-only mount** (fail-fast on write attempts) |
| ARTIFACT_DIR | ✅ Full write |
| External network | ✅ As needed for package resolution |
| System modification | ❌ Forbidden |

---

## Sandbox Implementation

### Technology

**Docker containers** with the following configuration:

| Aspect | Configuration |
|--------|---------------|
| Isolation | Standard container isolation with resource limits |
| Repo mount | Read-only bind mount |
| Writable paths | ARTIFACT_DIR only |
| Lifecycle | **Ephemeral** — fresh container per run (destroyed after) |

### Container Lifecycle

1. Create fresh container from base image
2. Mount repository as read-only
3. Mount ARTIFACT_DIR as writable
4. Execute pipeline steps
5. Capture outputs
6. Destroy container

No container reuse between runs. Each verification starts with a clean slate for reproducibility.

---

## Pipeline Configuration

### Source

Pipeline defined in `agent.yaml` configuration file.

### Format

**Arbitrary shell commands** — user specifies exact commands to run.

```yaml
verification:
  steps:
    - name: install
      command: npm ci
    - name: typecheck
      command: npm run typecheck
    - name: lint
      command: npm run lint
    - name: build
      command: npm run build
    - name: test
      command: npm test
```

### Execution

- Steps run **sequentially** in defined order
- Pipeline stops on first failure
- All outputs captured to artifacts

---

## Test Write Handling

When tests need to write temporary files:

### Redirect Strategy

- Test harness configured to write all temp/generated files to ARTIFACT_DIR
- Environment variables set to redirect:
  - Temp directories
  - Test databases
  - Generated fixtures
  - Snapshot outputs

### Example Environment

```bash
TMPDIR=/artifacts/tmp
TEST_DB_PATH=/artifacts/db
SNAPSHOT_DIR=/artifacts/snapshots
```

---

## Output Contract

### Response Structure

```json
{
  "status": "PASS | FAIL",
  "run_id": "string (unique identifier)",
  "tail_log": "string (≤200 lines)",
  "artifact_paths": ["string"],
  "manifest": {
    "timestamp_start": "ISO8601",
    "timestamp_end": "ISO8601",
    "commit_sha": "string",
    "commands_executed": [
      {
        "name": "string",
        "command": "string",
        "exit_code": "number",
        "duration_ms": "number"
      }
    ],
    "platform": {
      "os": "string",
      "arch": "string",
      "container_image": "string"
    }
  }
}
```

### Tail Log

- Last 200 lines of combined stdout/stderr
- Editor uses for quick diagnosis
- Full logs available via artifact_paths

---

## Timeout Handling

### Behavior

- Verification runs have configurable timeout
- Timeout **counts as failure** (identical treatment to test failure)
- No automatic retry with longer timeout

### Timeout Scenarios

- Infinite loops in tests
- Hanging network requests
- Deadlocks

---

## Run Manifest

Each verification run produces a manifest containing:

| Field | Description |
|-------|-------------|
| `run_id` | Unique identifier for this run |
| `timestamp_start` | When verification began |
| `timestamp_end` | When verification completed |
| `commit_sha` | Git SHA of code being verified |
| `commands_executed` | List of commands with exit codes |
| `platform` | OS, architecture, container image info |

---

## Artifact Directory Structure

```
ARTIFACT_DIR/
├── runs/
│   └── {run_id}/
│       ├── manifest.json
│       ├── logs/
│       │   ├── combined.log
│       │   ├── step-01-install.log
│       │   ├── step-02-typecheck.log
│       │   └── ...
│       ├── build/
│       │   └── (build outputs)
│       └── tmp/
│           └── (test temporaries)
└── cache/
    └── (optional build cache)
```

---

## Full Pipeline Enforcement

### Debug Loop Behavior

During Editor's debug loop:
- **Full pipeline always runs** — no targeted test execution
- Every fix attempt triggers complete verification
- Ensures consistent, reproducible results

### No Partial Verification

The Verifier does not support:
- Running single test files
- Skipping steps
- Partial verification modes

---

## Test Mode Requirements

Pipeline commands should use flags that prevent modifications:
- `--no-update` for snapshot tests
- `--frozen-lockfile` for package installs
- `--no-snapshot-rewrite`
- Read-only database connections

These flags should be configured in the `agent.yaml` pipeline commands.

---

## Storage

### Location

**Local directory** (not cloud storage)

### Path Configuration

ARTIFACT_DIR path configured via:
- Environment variable: `AGENT_ARTIFACT_DIR`
- Default: `~/.agent-artifacts/`

---

## Integration with Editor

1. Editor triggers Verifier (no parameters — Verifier reads current working tree)
2. Verifier executes pipeline in sandboxed container
3. Verifier returns structured response
4. Editor reads `status` for pass/fail gate
5. On failure, Editor accesses full logs via `artifact_paths`
6. Summary includes `run_id` for audit trail
