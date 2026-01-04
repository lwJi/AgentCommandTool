# Scout B (Build/Test Detective) Specification

## Overview

Scout B is a **read-only analyst** specializing in build systems, test infrastructure, and failure diagnosis. It determines how to build and test the project, interprets failures, and flags environment issues.

---

## Core Responsibilities

1. **Build Command Discovery**: Identify how to build the project
2. **Test Command Discovery**: Identify how to run tests
3. **Failure Interpretation**: Analyze test/build output and explain root causes
4. **Environment Issue Detection**: Identify missing dependencies, version mismatches
5. **Flakiness Detection**: Flag potentially flaky tests (informational only)

---

## Access Permissions

| Resource | Access |
|----------|--------|
| Repository files | ✅ Read-only |
| Build configuration files | ✅ Read-only |
| Binary files | ❌ Excluded |
| Secret files | ❌ Excluded |
| External network | ✅ Unrestricted |
| Working tree writes | ❌ Strictly forbidden |
| Environment modification | ❌ Strictly forbidden |

---

## Input: Targeted Questions

Scout B receives focused questions from the Editor, such as:
- "How do I build this project?"
- "What test command should I run?"
- "What caused this test failure?" (with log excerpt)
- "Are there any environment issues I should address?"

---

## Output: Report Payload

Scout B returns structured analysis. Unlike Scout A's strict JSON schema, Scout B reports are more diagnostic in nature.

### Report Structure

```json
{
  "build": {
    "detected_system": "npm | yarn | pnpm | make | cargo | go | gradle | maven | custom",
    "commands": {
      "install": "string | null",
      "build": "string",
      "clean": "string | null"
    },
    "prerequisites": ["string"],
    "notes": "string"
  },
  "test": {
    "detected_framework": "jest | pytest | go test | cargo test | junit | mocha | custom",
    "commands": {
      "all": "string",
      "unit": "string | null",
      "integration": "string | null"
    },
    "coverage_command": "string | null",
    "notes": "string"
  },
  "failure_analysis": {
    "root_cause": "string",
    "affected_files": ["string"],
    "suggested_investigation": ["string"],
    "is_flaky": "boolean",
    "flaky_reason": "string | null"
  },
  "environment_issues": [
    {
      "issue": "string",
      "severity": "blocking | warning",
      "suggested_fix": "string"
    }
  ]
}
```

---

## Flaky Test Handling

### Detection

Scout B may detect potential flakiness indicators:
- Timing-dependent assertions
- Network-dependent tests
- Random data usage
- Race conditions
- Environment-sensitive paths

### Behavior

| Detection | Action |
|-----------|--------|
| Flaky test identified | Report as informational flag |
| Flaky test fails | **Still counts as blocking failure** |

Scout B **does not**:
- Automatically skip flaky tests
- Recommend ignoring failures
- Modify test behavior

All test failures are blocking. Flakiness must be fixed, not worked around.

---

## Environment Issue Handling

### Detection Scope

Scout B identifies:
- Missing dependencies (packages, binaries)
- Version mismatches (Node version, Python version)
- Missing configuration files
- Permission issues
- Path problems

### Behavior: Report Only

Scout B **never**:
- Installs missing dependencies
- Modifies environment variables
- Changes system configuration
- Executes fix commands

Scout B **only**:
- Diagnoses the issue
- Provides suggested fix command for human/Editor review
- Reports severity (blocking vs warning)

---

## Failure Interpretation

When analyzing verification failures:

### Input

Scout B receives:
- Tail log (≤200 lines) from Verifier
- Context about what was being tested
- Access to full logs via artifact reference

### Analysis Includes

1. **Root cause identification**: What actually failed and why
2. **Affected files**: Which source files are implicated
3. **Investigation suggestions**: Next steps to debug
4. **Flakiness assessment**: Is this potentially non-deterministic?

---

## Error Handling

### Retry Behavior

If Scout B becomes unresponsive:
1. Editor retries with **exponential backoff**
2. Maximum **3 retry attempts**
3. After 3 failures: generate partial stuck report

---

## Implementation

- Scout B is a **separate LLM instance**
- Distinct system prompt from Editor and Scout A
- Own context window (no shared state)
- Runs on the **same model** as the rest of the system

---

## File Analysis Scope

Scout B focuses on build/test configuration:
- `package.json`, `package-lock.json`, `yarn.lock`
- `pyproject.toml`, `setup.py`, `requirements.txt`
- `go.mod`, `go.sum`
- `Cargo.toml`, `Cargo.lock`
- `Makefile`, `CMakeLists.txt`
- `build.gradle`, `pom.xml`
- `.github/workflows/*` (CI configuration)
- `jest.config.*`, `pytest.ini`, `vitest.config.*`

Same exclusions as Scout A apply:
- No binary files
- No secret files
