# AgentCommandTool

A pull-based, editor-centric coding agent system.

## Installation

```bash
uv sync --all-extras
```

## Usage

```bash
# Run a task
act run "Fix the authentication timeout bug"

# Preview changes without applying
act run --dry-run "Add logging to the API"

# Check status
act status

# View queue
act queue

# Cancel running task
act cancel
```

## Development

```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check src/

# Run type checking
uv run mypy src/
```

## License

MIT
