# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AgentCommandTool (`act`) is a pull-based, editor-centric coding agent system. The system is fully implemented with all components operational.

- **Package**: `agent-command-tool` v0.1.0
- **Python**: >= 3.11
- **License**: MIT

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Run a task
act run "fix the failing test in auth module"

# Check status
act status
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `act run <task>` | Submit and run a task (`--dry-run`, `-v/--verbose`) |
| `act status` | Show current task status |
| `act queue` | List queued tasks |
| `act cancel [--id N]` | Cancel running or queued task |
| `act history [--clear]` | View or clear task history |

## Development Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_editor_debug_loop.py

# Run tests with coverage
uv run pytest --cov=src

# Linting
uv run ruff check src/

# Type checking
uv run mypy src/
```

## Architecture

The system implements a four-component architecture:

| Component    | Role         | Write Access              | Responsibility                                          |
| ------------ | ------------ | ------------------------- | ------------------------------------------------------- |
| **Editor**   | Orchestrator | Repo + `agent/` files     | Sole authority for code changes; coordinates workflow   |
| **Scout A**  | Analyzer     | Read-only                 | Codebase mapping, file location, API discovery          |
| **Scout B**  | Detector     | Read-only                 | Build/test discovery, failure interpretation            |
| **Verifier** | Sandbox      | Artifacts only            | Runs build/test in isolated Docker container            |

### Data Flow

```text
User Task -> Editor -> Scouts (pull-based queries)
                    -> Records context -> agent/context_###.md
                    -> Implements changes (minimal diffs)
                    -> Triggers Verifier (sandbox execution)
                    -> Debug loop or final summary
```

### Core Invariants

1. **Only Editor writes to repo** - single edit authority
2. **Scouts are strictly read-only** - analysis/mutation separation
3. **Verifier repo mount is read-only** - prevents accidental source modification
4. **Green build+tests required** - hard correctness gate
5. **REPLAN after 3 consecutive failures** - forces strategy change (up to 3 REPLANs)
6. **Hard stop at 12 total verify loops** - prevents infinite thrash
7. **INFRA_ERROR triggers immediate stop** - infrastructure issues require human intervention

## Source Code Structure

```
src/act/
├── cli.py       - CLI entry point (act command)
├── editor/      - Orchestrator with debug loop
├── scouts/      - Read-only analyzers (Scout A & B)
├── verifier/    - Docker sandbox executor
├── task/        - Task queue and state machine
├── config/      - Configuration loading
├── artifacts/   - Context files and verification outputs
└── core/        - Logging, metrics, validation
```

## Specification Files

| File                      | Purpose                                                                          |
| ------------------------- | -------------------------------------------------------------------------------- |
| `specs/blueprint.md`      | System-wide architecture & invariants                                            |
| `specs/editor.md`         | Editor responsibilities and debug loop logic                                     |
| `specs/scout-a.md`        | Scout A (Codebase Mapper) JSON schema and behavior                               |
| `specs/scout-b.md`        | Scout B (Build/Test Detective) JSON schema and behavior                          |
| `specs/verifier.md`       | Sandbox execution, artifact output contract                                      |
| `specs/task-lifecycle.md` | Task queue states: QUEUED -> RUNNING -> {SUCCESS\|CANCELLED\|STUCK\|INFRA_ERROR} |
| `specs/configuration.md`  | `agent.yaml` structure, env vars, LLM config                                     |
| `specs/artifacts.md`      | Context files (`agent/`) and verification artifacts                              |

## Key Concepts

### Pull-Based Architecture

Editor **pulls** information from Scouts via synchronous, blocking calls. No continuous monitoring or background analysis.

### Fix-Forward Strategy

On test failure, don't revert—fix forward. Keep broken state, diagnose, implement fix, re-verify.

### Iteration Controls

- 3 consecutive failures -> REPLAN (new strategy)
- 12 total verify loops -> Hard stop
- Infrastructure failure -> Immediate stop (INFRA_ERROR)

### Context Management

- `agent/context_###.md` - Scout payloads and Editor state (gitignored)
- `~/.agent-artifacts/` - Verification logs, build artifacts, manifests
- Retention: 20 runs OR 14 days (whichever first)

## Configuration

### Repository Config (`agent.yaml`)

```yaml
verification:
  image: "python:3.11"
  steps:
    - name: "install"
      command: "pip install -e ."
    - name: "test"
      command: "pytest"
  timeout: 300
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `OPENAI_API_KEY` | OpenAI API key (alternative backend) |
| `AGENT_LLM_BASE_URL` | Custom LLM endpoint (OpenAI-compatible) |
| `AGENT_ARTIFACT_DIR` | Override artifact directory (default: `~/.agent-artifacts/`) |

## Development Guidelines

1. **Spec compliance** - implementation must match behavior defined in `specs/`
2. **Error handling** - Scout and Verifier INFRA_ERROR follow identical patterns
3. **Schema versioning** - Scout A and B have separate schema versions (v1)
4. **State transitions** - REPLAN/hard-stop logic must match `task-lifecycle.md` and `editor.md`
5. **Testing** - all changes should include tests; run `uv run pytest` before committing
6. **Code style** - enforced by ruff and mypy; run both before submitting PRs
