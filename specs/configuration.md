# Configuration Specification

## Overview

System configuration is split between repository-level settings (agent.yaml) and deployment-level settings (environment variables).

---

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `agent.yaml` | Repository-specific settings | Repository root |
| Environment variables | Deployment settings, secrets | System environment |

---

## agent.yaml

### Format

**Dedicated YAML file** in repository root.

### Structure

Single flat configuration — no environment-specific overrides (dev/staging/prod sections).

```yaml
# agent.yaml - Repository configuration

verification:
  container_image: node:20-slim  # Docker image for sandbox execution
  steps:
    - name: install
      command: npm ci --frozen-lockfile
    - name: typecheck
      command: npm run typecheck
    - name: lint
      command: npm run lint
    - name: build
      command: npm run build
    - name: test
      command: npm test -- --no-update-snapshots

monorepo:
  # For monorepos: specify which package this config applies to
  package: packages/core  # optional, omit for single-package repos

timeouts:
  verification_step: 300000  # ms per step (5 min default)
  scout_query: 60000         # ms per scout query (1 min default)
```

### Verification Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `container_image` | string | ✅ Yes | Docker image for Verifier sandbox execution |
| `steps` | array | ✅ Yes | List of verification steps to run |

### Verification Steps

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable step name |
| `command` | string | Shell command to execute |

Commands are **arbitrary shell commands** — no predefined vocabulary.

### Monorepo Configuration

For monorepos with multiple packages:
- User specifies target package path
- Task scoped to single package only
- Cross-package changes not supported in single task

---

## Environment Variables

### LLM Configuration

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `AGENT_LLM_BASE_URL` | Custom OpenAI-compatible endpoint |
| `AGENT_LLM_MODEL` | Model identifier to use |

### Backend Selection

The system uses a **pluggable backend** supporting any OpenAI-compatible API.

Configuration priority:
1. `AGENT_LLM_BASE_URL` + `AGENT_LLM_MODEL` (custom endpoint)
2. `ANTHROPIC_API_KEY` (Anthropic Claude)
3. `OPENAI_API_KEY` (OpenAI)

### Model Configuration

- **Single model** for entire system
- Same model used for Editor, Scout A, Scout B
- No per-component model mixing

### Artifact Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_ARTIFACT_DIR` | `~/.agent-artifacts/` | Local artifact storage path |

---

## What is NOT Configurable

### Editor Behavior

- System prompts are **hardcoded**
- Not customizable per-repository
- Ensures consistent behavior

### Schema Extensions

- Scout A's JSON schema is **fixed and versioned**
- No per-repository custom fields
- No extensions mechanism

### Iteration Limits

| Limit | Value | Configurable |
|-------|-------|--------------|
| REPLAN trigger | 3 failures | ❌ No |
| Hard stop | 12 loops | ❌ No |
| Scout retries | 3 attempts | ❌ No |

### File Exclusions

- Binary file exclusion patterns are fixed
- Secret file patterns are fixed
- Cannot add custom exclusions

---

## Configuration Validation

On task start, system validates:
1. `agent.yaml` exists and is valid YAML
2. Required environment variables present
3. Verification steps have valid command fields
4. Docker available for Verifier sandbox

### Missing Configuration

| Scenario | Behavior |
|----------|----------|
| No `agent.yaml` | Error: configuration required |
| No `container_image` | Error: container image required for Verifier |
| No verification steps | Error: at least one step required |
| No LLM API key | Error: cannot proceed without model access |
| Invalid YAML | Error with parse details |

---

## Example Configurations

### Node.js Project

```yaml
verification:
  container_image: node:20-slim
  steps:
    - name: install
      command: npm ci --frozen-lockfile
    - name: typecheck
      command: npx tsc --noEmit
    - name: lint
      command: npm run lint
    - name: test
      command: npm test -- --coverage --watchAll=false
```

### Python Project

```yaml
verification:
  container_image: python:3.12-slim
  steps:
    - name: install
      command: pip install -e ".[dev]"
    - name: typecheck
      command: mypy src/
    - name: lint
      command: ruff check src/
    - name: test
      command: pytest --tb=short
```

### Go Project

```yaml
verification:
  container_image: golang:1.22
  steps:
    - name: build
      command: go build ./...
    - name: vet
      command: go vet ./...
    - name: test
      command: go test -v ./...
```

### Rust Project

```yaml
verification:
  container_image: rust:1.75
  steps:
    - name: check
      command: cargo check
    - name: clippy
      command: cargo clippy -- -D warnings
    - name: test
      command: cargo test
```

---

## Environment Variable Examples

```bash
# Using Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# Using OpenAI
export OPENAI_API_KEY="sk-..."

# Using custom endpoint (e.g., local model)
export AGENT_LLM_BASE_URL="http://localhost:8080/v1"
export AGENT_LLM_MODEL="llama-3.1-70b"

# Custom artifact directory
export AGENT_ARTIFACT_DIR="/var/agent-data/artifacts"
```
