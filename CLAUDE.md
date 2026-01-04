# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AgentCommandTool is the implementation repository for a pull-based, editor-centric coding agent system. The `specs/` folder contains architectural specifications that define how the system should be built.

## Architecture

The system implements a four-component architecture:

| Component    | Role         | Write Access              | Responsibility                                          |
| ------------ | ------------ | ------------------------- | ------------------------------------------------------- |
| **Editor**   | Orchestrator | ✅ Repo + `agent/` files  | Sole authority for code changes; coordinates workflow   |
| **Scout A**  | Analyzer     | ❌ Read-only              | Codebase mapping, file location, API discovery          |
| **Scout B**  | Detector     | ❌ Read-only              | Build/test discovery, failure interpretation            |
| **Verifier** | Sandbox      | ❌ (artifacts only)       | Runs build/test in isolated Docker container            |

### Data Flow

```text
User Task → Editor → Scouts (pull-based queries)
                  → Records context → agent/context_###.md
                  → Implements changes (minimal diffs)
                  → Triggers Verifier (sandbox execution)
                  → Debug loop or final summary
```

### Core Invariants

1. **Only Editor writes to repo** — single edit authority
2. **Scouts are strictly read-only** — analysis/mutation separation
3. **Verifier repo mount is read-only** — prevents accidental source modification
4. **Green build+tests required** — hard correctness gate
5. **REPLAN after 3 consecutive failures** — forces strategy change (up to 3 REPLANs)
6. **Hard stop at 12 total verify loops** — prevents infinite thrash
7. **INFRA_ERROR triggers immediate stop** — infrastructure issues require human intervention

## Specification Files

| File                      | Purpose                                                                          |
| ------------------------- | -------------------------------------------------------------------------------- |
| `specs/blueprint.md`      | System-wide architecture & invariants                                            |
| `specs/editor.md`         | Editor responsibilities and debug loop logic                                     |
| `specs/scout-a.md`        | Scout A (Codebase Mapper) JSON schema and behavior                               |
| `specs/scout-b.md`        | Scout B (Build/Test Detective) JSON schema and behavior                          |
| `specs/verifier.md`       | Sandbox execution, artifact output contract                                      |
| `specs/task-lifecycle.md` | Task queue states: QUEUED → RUNNING → {SUCCESS\|CANCELLED\|STUCK\|INFRA_ERROR}   |
| `specs/configuration.md`  | `agent.yaml` structure, env vars, LLM config                                     |
| `specs/artifacts.md`      | Context files (`agent/`) and verification artifacts                              |

## Key Concepts

### Pull-Based Architecture

Editor **pulls** information from Scouts via synchronous, blocking calls. No continuous monitoring or background analysis.

### Fix-Forward Strategy

On test failure, don't revert—fix forward. Keep broken state, diagnose, implement fix, re-verify.

### Iteration Controls

- 3 consecutive failures → REPLAN (new strategy)
- 12 total verify loops → Hard stop
- Infrastructure failure → Immediate stop (INFRA_ERROR)

### Context Management

- `agent/context_###.md` — Scout payloads and Editor state (gitignored)
- `~/.agent-artifacts/` — Verification logs, build artifacts, manifests
- Retention: 20 runs OR 14 days (whichever first)

## Implementation Guidelines

When implementing components based on specs:

1. **Spec compliance** — implementation must match the behavior defined in `specs/`
2. **Error handling** — Scout and Verifier INFRA_ERROR should follow identical patterns
3. **Schema versioning** — Scout A and B have separate schema versions
4. **State transitions** — REPLAN/hard-stop logic must match `task-lifecycle.md` and `editor.md`
