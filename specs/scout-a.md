# Scout A (Codebase Mapper) Specification

## Overview

Scout A is a **read-only analyst** that locates files, patterns, APIs, and invariants within the codebase. It produces structured guidance on *where* and *how* to make changes.

---

## Core Responsibilities

1. **File Location**: Identify relevant files for a given task
2. **Pattern Recognition**: Find code patterns, conventions, and idioms
3. **API Discovery**: Locate internal APIs, interfaces, and contracts
4. **Invariant Detection**: Identify constraints that must be preserved
5. **Risk Zone Mapping**: Mark change boundaries with complexity estimates
6. **Safe Slice Definition**: Define minimal, atomic change units

---

## Access Permissions

| Resource | Access |
|----------|--------|
| Repository files | ✅ Read-only |
| Binary files | ❌ Excluded from analysis |
| Secret files (.env, credentials) | ❌ Excluded from analysis |
| External network | ✅ Unrestricted |
| Working tree writes | ❌ Strictly forbidden |

---

## Input: Targeted Questions

Scout A receives focused questions from the Editor, such as:
- "Which files handle user authentication?"
- "What patterns does this codebase use for database access?"
- "What invariants must be preserved when modifying the payment flow?"

---

## Output: Structured Report Payload

### Format

**Structured JSON** with a fixed, versioned schema.

### Schema (v1)

```json
{
  "schema_version": "1",
  "repo_map": {
    "relevant_files": [
      {
        "path": "string",
        "purpose": "string",
        "relevance": "primary | secondary | context"
      }
    ],
    "entry_points": ["string"],
    "dependency_graph": {}
  },
  "risk_zones": [
    {
      "file": "string",
      "start_line": "number",
      "end_line": "number",
      "risk_level": "low | medium | high",
      "complexity": "low | medium | high",
      "dependencies": ["string"],
      "invariants": ["string"],
      "rationale": "string"
    }
  ],
  "change_boundaries": {
    "safe_slices": [
      {
        "id": "string",
        "files": ["string"],
        "description": "string",
        "complexity": "low | medium | high",
        "order": "number | null"
      }
    ],
    "ordering_constraints": ["string"]
  },
  "conventions": {
    "naming": "string",
    "patterns": ["string"],
    "anti_patterns": ["string"]
  },
  "prior_art": [
    {
      "file": "string",
      "description": "string",
      "relevance": "string"
    }
  ],
  "verification_tips": ["string"],
  "hypotheses": ["string"]
}
```

---

## Risk Zone Specification

Each risk zone includes:

| Field | Type | Description |
|-------|------|-------------|
| `file` | string | File path relative to repo root |
| `start_line` | number | First line of risk zone |
| `end_line` | number | Last line of risk zone |
| `risk_level` | enum | `low`, `medium`, or `high` |
| `complexity` | enum | Estimated implementation effort: `low`, `medium`, `high` |
| `dependencies` | string[] | Files/modules that depend on this zone |
| `invariants` | string[] | Constraints that must be preserved |
| `rationale` | string | Explanation of risk assessment |

### Complexity Estimation

Scout A **always includes** complexity estimates for each zone to help Editor prioritize slice ordering.

---

## Safe Slice Definition

A "safe slice" is the **smallest atomic change unit** that:
- Can be implemented independently
- Has well-defined boundaries
- Minimizes risk of breaking invariants
- Can be verified in isolation

Scout A marks:
- Which files belong to each slice
- Recommended implementation order
- Ordering constraints (if slice A must precede slice B)

---

## Schema Versioning

- Schema is **fixed and versioned**
- Breaking changes require **major version bump**
- Editor validates payload against expected schema version
- No per-repository extensions or custom fields

---

## File Exclusions

The following are **excluded from Scout A analysis**:

### Secrets
- `.env`, `.env.*`
- `*credentials*`, `*secrets*`
- Files matching patterns in `.gitignore` secret patterns

### Binaries
- Images: `.png`, `.jpg`, `.gif`, `.ico`, `.svg`
- Compiled: `.exe`, `.dll`, `.so`, `.dylib`
- Archives: `.zip`, `.tar`, `.gz`
- Other non-text files

---

## Error Handling

Scout error handling follows [Invariant #9](blueprint.md#5-invariants): retry 3× with exponential backoff. After 3 failures, task transitions to `INFRA_ERROR` state with a stuck report (see [Editor Specification](editor.md#scout-infra_error)).

### Timeout

- Scout queries have configurable timeout (see [Configuration](configuration.md))
- Timeout triggers retry flow
- After 3 timeouts, task transitions to `INFRA_ERROR`

---

## Implementation

- Scout A is a **separate LLM instance**
- Distinct system prompt from Editor and Scout B
- Own context window (no shared state with other components)
- Runs on the **same model** as the rest of the system (single-model configuration)
