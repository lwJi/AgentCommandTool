# Coding Agent Workflow — Canonical Architectural Reference

## 1. System Overview

This architecture defines a **pull-based, editor-centric coding agent** optimized for **correctness** and **maintainability**. A single Editor role holds exclusive write authority over the repository, while read-only Scouts provide on-demand analysis and a sandboxed Verifier enforces a hard quality gate. The design prevents agent thrash through strict role boundaries, incremental change slices, and explicit iteration controls (REPLAN at 3 failures, hard stop at 12).

---

## 2. Component Inventory

| Component | Responsibility | Write Access |
|-----------|----------------|--------------|
| **Editor** | Single source of truth for all repo modifications. Orchestrates workflow, records scout reports, implements changes, triggers verification, produces final summaries. | ✅ Repo + `agent/` artifacts |
| **Scout A** (Codebase Mapper) | Locates files, patterns, APIs, invariants. Produces actionable guidance on *where/how* to change. | ❌ Read-only |
| **Scout B** (Build/Test Detective) | Determines build/test commands, interprets failures, flags flakiness and environment issues. | ❌ Read-only |
| **Verifier** | Executes build + unit tests in a sandbox. Gates "done" on green status. Emits truncated logs + artifact references. | ❌ Repo read-only; writes only to external `ARTIFACT_DIR` |

---

## 3. Data Flow
```
┌─────────────────────────────────────────────────────────────┐
│                      EDITOR (orchestrator)                  │
│  - Requests scout analysis (pull-based)                     │
│  - Records scout payloads → agent/context_###.md            │
│  - Implements smallest safe slice                           │
│  - Triggers Verifier                                        │
└──────────┬────────────────────────────────┬─────────────────┘
           │ question                       │ trigger
           ▼                                ▼
   ┌───────────────┐                ┌───────────────┐
   │   SCOUTS A/B  │                │   VERIFIER    │
   │  (read-only)  │                │  (sandboxed)  │
   └───────┬───────┘                └───────┬───────┘
           │ report payload                 │ PASS/FAIL + last 200 lines
           ▼                                │ + artifact reference (run_id)
     Editor records                         ▼
     to context file               Editor consumes result
```

**Numbered Flow:**
1. Editor defines success criteria (behavior change, acceptance criteria, non-goals)
2. Editor pulls Scouts with targeted questions → Scouts return report payloads
3. Editor records payloads to `agent/context_###.md`, updates `agent/context_latest.md`
4. Editor implements minimal diff following repo conventions
5. Editor triggers Verifier → Verifier runs build+tests in read-only sandbox
6. Verifier returns status; on failure, Editor enters tight debug loop (localize → fix → re-verify)
7. On green: Editor produces summary (what, why, how verified, `run_id`)

---

## 4. Interaction Contracts

### Scout → Editor
- **Input:** Targeted question from Editor
- **Output:** Report payload (message/structured output)
- **Constraint:** Scouts never write; Editor records all persistent artifacts

### Editor → Verifier
- **Input:** Trigger to run verification
- **Output:** Unified response with `status: PASS|FAIL|INFRA_ERROR` (see [Verifier Specification](verifier.md#output-contract) for full schema)

### Verifier Sandbox Contract
| Aspect | Rule |
|--------|------|
| Repo mount | **Read-only** (fail-fast on write attempts) |
| Writable root | `ARTIFACT_DIR/` only: `logs/`, `build/`, `cache/`, `tmp/` |
| Run manifest | `run_id`, timestamps, commit SHA, commands, exit codes, platform info |
| Test mode | No-update / no-snapshot-rewrite flags required |

### Scout Artifact Schema
- `agent/context_latest.md` → pointer to newest snapshot
- `agent/context_###.md` → versioned snapshots containing: repo map, target files, APIs, constraints, prior art, verification tips, hypotheses

---

## 5. Invariants

| # | Rule | Rationale |
|---|------|-----------|
| 1 | **Only Editor writes to repo/working tree** | Single edit authority prevents conflicts and audit confusion |
| 2 | **Scouts are strictly read-only** | Separation of analysis from mutation |
| 3 | **Verifier repo mount is read-only** | Tests cannot accidentally modify source; all artifacts externalized |
| 4 | **Green build + unit tests required before "done"** | Correctness is a hard gate, not advisory |
| 5 | **REPLAN after 3 consecutive verify failures** | Forces strategy change, not scope creep; Editor may optionally re-query Scouts if failures suggest stale analysis. Consecutive counter resets after REPLAN (allows up to 3 REPLANs at attempts 3, 6, 9). |
| 6 | **Hard stop at 12 total verify loops** | Prevents infinite thrash; produces stuck report with hypotheses + artifact refs. Total counter only resets on green. Hard stop takes precedence when both triggers fire simultaneously. |
| 7 | **Diffs must be minimal and pattern-consistent** | Maintainability over cleverness |
| 8 | **Artifact retention: 20 runs or 14 days; stuck-report artifacts retained until resolved** | Auditability without unbounded storage |
| 9 | **Scout queries retry 3× with exponential backoff; after 3 failures transition to INFRA_ERROR** | Resilience against transient failures while preventing infinite retry loops; Scout failures are infrastructure issues requiring human intervention |
| 10 | **INFRA_ERROR triggers immediate task termination with stuck report** | Infrastructure failures (Verifier or Scout) require human intervention; retrying wastes time |

---

## Quick Reference: Definition of Done

✅ Verifier returns `PASS`  
✅ Diff is minimal, follows repo conventions  
✅ New/changed behavior has appropriate tests  
✅ Summary documents: what changed, why, how verified (`run_id` included)
