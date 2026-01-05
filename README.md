# AgentCommandTool

A pull-based, editor-centric coding agent system with sandboxed verification.

## Overview

AgentCommandTool (`act`) is an automated coding agent that handles software engineering tasks through a four-component architecture:

- **Single Editor Authority**: Only one component (the Editor) can modify your repository, preventing conflicts
- **Read-Only Analysis**: Scouts analyze your codebase without making changes
- **Sandboxed Verification**: All builds and tests run in isolated Docker containers
- **Fix-Forward Strategy**: On test failure, the system diagnoses and fixes rather than reverting
- **Iteration Controls**: Automatic strategy changes and hard stops prevent infinite loops

## Requirements

- Python >= 3.11
- Docker (for sandboxed verification)

## Installation

```bash
uv sync --all-extras
```

## Quick Start

```bash
# Run a task
act run "Fix the authentication timeout bug"

# Preview changes without applying
act run --dry-run "Add logging to the API"

# Check status
act status
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `act run <task>` | Submit and run a task |
| `act status` | Show current task status |
| `act queue` | List queued tasks |
| `act cancel [--id N]` | Cancel running or queued task |
| `act history [--clear]` | View or clear task history |

### Command Options

**`act run`**
- `--dry-run` - Preview changes without applying them
- `-v, --verbose` - Enable verbose output

**`act cancel`**
- `--id N` - Cancel a specific queued task by ID (default: cancel running task)

**`act history`**
- `--clear` - Clear all task history

## Architecture

The system implements a four-component architecture with strict role separation:

| Component | Role | Write Access | Responsibility |
|-----------|------|--------------|----------------|
| **Editor** | Orchestrator | Repo + `agent/` | Sole authority for code changes; coordinates workflow |
| **Scout A** | Analyzer | Read-only | Codebase mapping, file location, API discovery |
| **Scout B** | Detector | Read-only | Build/test discovery, failure interpretation |
| **Verifier** | Sandbox | Artifacts only | Runs build/test in isolated Docker container |

### Data Flow

```
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

## Key Concepts

### Pull-Based Architecture

The Editor **pulls** information from Scouts via synchronous, blocking calls. There is no continuous monitoring or background analysis - the Editor requests specific information when needed.

### Fix-Forward Strategy

On test failure, the system doesn't revert changes. Instead, it:
1. Keeps the broken state
2. Diagnoses the issue
3. Implements a fix
4. Re-verifies

### Iteration Controls

- **3 consecutive failures** -> REPLAN (new strategy, resets consecutive counter)
- **12 total verify loops** -> Hard stop (produces stuck report)
- **Infrastructure failure** -> Immediate stop (INFRA_ERROR)

### Task States

```
QUEUED -> RUNNING -> SUCCESS
                  -> CANCELLED
                  -> STUCK
                  -> INFRA_ERROR
```

## Configuration

### Repository Config (`agent.yaml`)

Create an `agent.yaml` file in your repository root:

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

## Source Structure

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

## Specification Documents

Detailed specifications are available in the `specs/` directory:

| File | Purpose |
|------|---------|
| `specs/blueprint.md` | System-wide architecture & invariants |
| `specs/editor.md` | Editor responsibilities and debug loop logic |
| `specs/scout-a.md` | Scout A (Codebase Mapper) JSON schema and behavior |
| `specs/scout-b.md` | Scout B (Build/Test Detective) JSON schema and behavior |
| `specs/verifier.md` | Sandbox execution, artifact output contract |
| `specs/task-lifecycle.md` | Task queue states and transitions |
| `specs/configuration.md` | `agent.yaml` structure, env vars, LLM config |
| `specs/artifacts.md` | Context files and verification artifacts |

## Development

```bash
# Install dependencies
uv sync --all-extras

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src

# Linting
uv run ruff check src/

# Type checking
uv run mypy src/
```

See `CLAUDE.md` for detailed development guidelines.

## License

MIT
