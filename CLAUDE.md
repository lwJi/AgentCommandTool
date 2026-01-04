# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentCommandTool is a **specification repository** defining a pull-based, editor-centric coding agent architecture. This is a documentation-focused project—there is no build system, test suite, or executable code. The specs define how an autonomous coding agent should operate.

## Repository Structure

```
specs/                    # Core specifications (8 documents)
├── blueprint.md         # Canonical architectural reference (START HERE)
├── editor.md            # Editor (orchestrator) specification
├── scout-a.md           # Scout A: Codebase Mapper spec
├── scout-b.md           # Scout B: Build/Test Detective spec
├── verifier.md          # Verifier (sandbox executor) spec
├── task-lifecycle.md    # Task states and queue management
├── configuration.md     # agent.yaml + environment variables
└── artifacts.md         # Artifact storage and retention
```

## Architecture

The system follows a **multi-agent, pull-based architecture** with strict role boundaries:

| Component | Role | Write Access |
|-----------|------|--------------|
| **Editor** | Orchestrator; single source of truth for all repo modifications | Repo + `agent/` artifacts |
| **Scout A** | Codebase Mapper; locates files, patterns, APIs | Read-only |
| **Scout B** | Build/Test Detective; determines commands, interprets failures | Read-only |
| **Verifier** | Sandbox executor; runs build+tests in Docker | Read-only repo; writes only to ARTIFACT_DIR |

**Data flow:** Editor queries Scouts → records payloads to `agent/context_###.md` → implements minimal changes → triggers Verifier → consumes PASS/FAIL/INFRA_ERROR result.

## Key Invariants

1. **Only Editor writes to repo** - single edit authority
2. **Scouts are strictly read-only** - analysis separated from mutation
3. **Verifier repo mount is read-only** - tests cannot modify source
4. **Green verification required before "done"** - correctness is a hard gate
5. **REPLAN at 3 consecutive failures** - forces strategy change (counter resets after REPLAN)
6. **Hard stop at 12 total verify loops** - prevents infinite thrash; produces stuck report
7. **Scout queries retry 3× with exponential backoff; 3 failures → INFRA_ERROR**
8. **INFRA_ERROR triggers immediate termination** - infrastructure failures require human intervention

## Editing Specifications

When modifying specs:

- **blueprint.md is canonical** - other specs must align with it
- **Scout schemas are versioned** (`schema_version: "1"`) - changes require version bumps
- **Maintain consistency** across specs for: task states, iteration limits, error handling
- **Recent focus areas** (from git history): INFRA_ERROR unification, Scout error handling, REPLAN/hard-stop precedence rules
