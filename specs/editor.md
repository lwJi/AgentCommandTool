# Editor Specification

## Overview

The Editor is the **sole orchestrator** and **single source of truth** for all repository modifications. It coordinates Scouts, implements changes, triggers verification, and produces final summaries.

---

## Core Responsibilities

1. **Task Interpretation**: Parse free-form natural language task descriptions
2. **Scout Coordination**: Issue targeted queries to Scouts (synchronous, blocking)
3. **Context Recording**: Persist raw Scout payloads to versioned context files
4. **Implementation**: Write minimal, convention-following code changes
5. **Verification Triggering**: Invoke Verifier and consume results
6. **Debug Loop**: Fix-forward on failures until green or REPLAN/hard-stop
7. **Summary Production**: Generate prose markdown summary on completion

---

## Write Authority

| Target | Editor Access |
|--------|---------------|
| Repository working tree | ✅ Full write |
| `agent/` context files | ✅ Full write |
| ARTIFACT_DIR | ❌ Read-only (Verifier writes) |
| Files outside repo root | ❌ Strictly rejected |

---

## Scout Interaction Model

### Pull-Based, Synchronous

- Editor **pulls** information from Scouts with targeted questions
- Calls are **synchronous blocking** — Editor waits for response before proceeding
- Editor may query Scout A and Scout B in any order based on task needs

### Conflict Resolution

When Scout A and Scout B provide conflicting guidance:
- **Editor makes the final call** autonomously
- No escalation to user or priority hierarchy
- Editor's judgment based on accumulated context

---

## Implementation Behavior

### Minimal Diff Principle

- Changes must be the **smallest safe slice** as marked by Scout A's risk zones
- "Minimal" is a **qualitative judgment** — no hard size limits
- Follow existing code conventions (inferred from sampling existing files)
- No changes outside repository root boundary

### Test Generation

When repository has no existing test suite:
- Editor **generates tests** for changed code as part of implementation
- Test framework **auto-detected** from package manager files (package.json, pyproject.toml, go.mod, etc.)

### Convention Inference

- Editor samples existing files to match:
  - Indentation style
  - Naming conventions
  - Code patterns and idioms
- No explicit style guide required

---

## Debug Loop

### Fix-Forward Strategy

On verification failure:
1. Keep broken state in working tree (no revert)
2. Diagnose failure from Verifier logs (tail + full artifact access)
3. Implement fix
4. Re-trigger full verification pipeline
5. Repeat until green or counter threshold reached

### Iteration Controls

| Threshold | Trigger | Action |
|-----------|---------|--------|
| 3 consecutive failures | REPLAN | Autonomous re-strategize (new approach without Scout re-query or human input) |
| 12 total verify loops | Hard Stop | Generate stuck report with Editor-generated hypotheses |

### Counter Reset

- Counters reset **only on full green** (complete PASS from Verifier)
- Partial progress (e.g., build passes but tests fail) does not reset counters

---

## REPLAN Behavior

When REPLAN triggers:
1. Editor autonomously generates alternative strategy
2. **Scope constraints remain immutable** — cannot violate user's original boundaries
3. New context snapshot created (`context_###.md`)
4. **Optional Scout re-query** — Editor may request fresh analysis if warranted
5. Continue with new approach

### Scout Re-query Decision

Editor has autonomy to re-query Scouts during REPLAN when:
- **Re-query Scout A**: Failures suggest wrong files targeted, missed dependencies, or violated invariants
- **Re-query Scout B**: Failures suggest misinterpreted build/test output or undetected environment issues
- **Skip re-query**: Failures are clearly implementation logic errors with no codebase context gap

REPLAN does NOT:
- Escalate to human for approval
- Modify user-defined scope constraints

---

## Dry-Run Mode

When user requests dry-run:
- Editor proposes changes but does **not** write to filesystem
- Output format: **Git-style unified diff**
- User reviews before deciding to apply

---

## Final Outputs

### Summary (on success)

Prose markdown document containing:
- **What changed**: Description of modifications
- **Why**: Rationale tied to original task
- **How verified**: Confirmation of green Verifier run with `run_id`

Does NOT include:
- Suggested commit message
- PR description
- Git artifacts

### Stuck Report (on hard stop)

Contains:
- **Hypotheses**: Editor-generated diagnostic theories (Scouts not consulted)
- **Artifact references**: `run_id` pointers to all failed verification runs
- **Persists for future retry**: Next session receives stuck report only (not full history)

---

## State on Completion

| Outcome | Working Tree State |
|---------|-------------------|
| Success | Changes remain **dirty** — user reviews and commits manually |
| Cancel | Partial changes **preserved** — no artifact created |
| Hard Stop | Changes remain dirty; stuck report generated |

---

## Network Access

- **Unrestricted** — Editor can access external resources as needed
- Package registries, documentation sites, GitHub API all allowed

---

## Prompt Configuration

- Editor behavior defined by **hardcoded system prompts**
- Not customizable per-repository
- Consistent behavior across all deployments
