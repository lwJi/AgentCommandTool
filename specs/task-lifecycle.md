# Task Lifecycle Specification

## Overview

This document defines how tasks flow through the system from submission to completion, including queue management, state transitions, cancellation, and observability.

---

## Task Input

### Format

**Free-form natural language** — user describes what they want done.

No structured template required. Editor interprets intent from description.

### Scope Constraints

Users may optionally specify:
- **Constraints**: What must be preserved
- **Non-goals**: What should NOT be changed
- **Boundaries**: Files or modules out of scope

These constraints are **immutable** — REPLAN cannot violate them.

### Example Input

```
Fix the authentication timeout bug in the login flow.

Constraints:
- Don't modify the session storage mechanism
- Preserve backward compatibility with existing tokens

Non-goals:
- Don't refactor the auth module
- Don't add new dependencies
```

---

## Task Queue

### Model

**Queue serialization** — tasks execute sequentially, not concurrently.

When a second task is submitted while first is running:
- Second task enters queue
- Waits for first to complete
- Then starts execution

### Ordering

**Strict FIFO** — first-come, first-served.
- No priority levels
- No deadline-based scheduling
- No reordering

### Queue Management

| Capability | Supported |
|------------|-----------|
| View queued tasks | ✅ Yes |
| Cancel pending task | ✅ Yes |
| Reorder queue | ❌ No |
| Priority override | ❌ No |

### Pending Task Cancellation

Users can cancel tasks in QUEUED state:

| Aspect | Behavior |
|--------|----------|
| Removal | Task immediately removed from queue |
| Artifacts | No artifacts created |
| Queue shift | Remaining tasks shift up in position |
| Running tasks | Not affected (use running task cancellation) |

Cancelled pending tasks leave no trace — as if never submitted.

---

## Task States

```
┌─────────────┐
│   QUEUED    │ (waiting for prior tasks)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   RUNNING   │ (Editor active)
└──────┬──────┘
       │
       ├──────────────┬────────────────┐
       ▼              ▼                ▼
┌───────────┐  ┌────────────┐  ┌────────────┐
│  SUCCESS  │  │  CANCELLED │  │   STUCK    │
└───────────┘  └────────────┘  └────────────┘
```

### State Definitions

| State | Description |
|-------|-------------|
| QUEUED | Waiting for prior tasks to complete |
| RUNNING | Editor actively working on task |
| SUCCESS | Verifier returned PASS; summary generated |
| CANCELLED | User cancelled mid-execution |
| STUCK | Hard stop reached (12 verify loops); stuck report generated |

---

## Status Updates

### Delivery Mechanism

**Push notifications** via WebSocket or Server-Sent Events (SSE).

Real-time updates streamed to client.

### Visibility Level

**Status milestones** — high-level progress indicators.

Users see:
- "Analyzing codebase..."
- "Querying Scout A..."
- "Implementing changes..."
- "Running verification..."
- "Verification failed, debugging..."
- "Attempt 3/12..."

Users do NOT see (by default):
- Full Scout query/response content
- Editor's internal reasoning
- Debug loop details

### On-Demand Detail

Users can **expand** to see full context:
- Complete failure logs
- Editor's diagnosis
- Fix attempt details

This is opt-in — summary by default, detail on request.

---

## Cancellation

### Capability

Users **can cancel** running tasks.

### Behavior on Cancel

| Aspect | Behavior |
|--------|----------|
| Working tree | Partial changes **preserved** |
| Context files | **No artifact created** |
| Queue | Next queued task starts |

### Post-Cancellation State

- Changes remain in working tree (dirty state)
- User can review, keep, or discard manually
- No documentation of what was attempted

---

## Dry-Run Mode

### Activation

User explicitly requests dry-run mode at task submission.

### Behavior

1. Editor analyzes and plans as normal
2. Generates proposed changes
3. **Does not write** to filesystem
4. **Verification is skipped** — Verifier is not invoked
5. Outputs **Git-style unified diff** showing proposed changes
6. User reviews and decides to apply or abort

### Output Format

Standard unified diff:
```diff
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -42,7 +42,7 @@ export function validateToken(token: string) {
-  const timeout = 30000;
+  const timeout = 60000;
   // ...
}
```

### Applying Dry-Run Changes

When user decides to apply:
1. Editor writes proposed changes to filesystem
2. Full verification pipeline runs automatically
3. Task transitions to RUNNING state with normal debug loop behavior
4. On success: generates summary; on failure: REPLAN/hard-stop rules apply

---

## Success Flow

```
1. User submits task (free-form text + optional constraints)
2. Task enters queue (QUEUED state)
3. When ready, task starts (RUNNING state)
4. Editor queries Scouts, implements changes, triggers Verifier
5. On green Verifier: Editor generates prose summary
6. Task completes (SUCCESS state)
7. Working tree left dirty for user review
```

### Definition of Done

✅ Verifier returns `PASS`
✅ Diff is minimal, follows repo conventions
✅ New/changed behavior has appropriate tests
✅ Summary documents: what, why, how verified (with `run_id`)

---

## Failure Flow (Debug Loop)

```
1. Verifier returns FAIL
2. Editor diagnoses from tail log + artifacts
3. Editor implements fix (fix-forward, no revert)
4. Editor re-triggers Verifier
5. If FAIL: increment both counters (consecutive_failures, total_verify_loops)
6. After 3 consecutive failures: REPLAN triggered, consecutive_failures resets to 0
7. Continue until green OR 12 total loops reached
```

Up to 3 REPLANs possible (at loops 3, 6, 9) before hard stop. At loop 12, hard stop takes precedence over REPLAN.

---

## Hard Stop Flow

When 12 verify loops exhausted:

```
1. Editor generates stuck report
   - Hypotheses (Editor-generated, no Scout consult)
   - Artifact references (all run_ids)
2. Task enters STUCK state
3. Working tree remains dirty
4. Stuck report persisted for future retry
5. Next queued task starts
```

---

## Future Retry

When a new task resumes from stuck state:

| Data Available | Description |
|----------------|-------------|
| Stuck report | Condensed summary with hypotheses |
| Artifact references | Access to prior run logs |

| Data NOT Available | Reason |
|--------------------|--------|
| Full context_###.md history | Only stuck report provided |
| Conversation logs | Not persisted |

New session starts relatively fresh, informed by stuck report.

---

## Deployment Model

### Single Repository

Each deployment targets **exactly one repository**.

- No multi-repo support
- No cross-repo coordination
- Separate deployment per repository

### Monorepo Handling

For monorepos:
- User specifies target package in `agent.yaml`
- Task scoped to single package
- Cross-package changes require separate tasks

---

## Task Timeout

### Verification Step Timeout

Individual verification steps can timeout (configured in agent.yaml).

Timeout **counts as failure** — treated identically to test failure.

### Task-Level Timeout

No overall task timeout. Tasks run until:
- Success (green verification)
- Cancellation (user-initiated)
- Hard stop (12 verify loops)

---

## Replay

### Feature Status

**Not supported**.

- No replay capability
- No re-running tasks against different commits
- Each task is standalone
