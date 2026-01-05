# CRITICAL: Path Traversal Vulnerability in DryRunManager

## Summary

The `DryRunManager` class constructs file paths by directly concatenating user-supplied `relative_path` with `repo_root` without any path traversal validation.

## Location

`src/act/editor/dry_run.py` - Lines 224, 253, 301

## Vulnerable Code

```python
# Line 224 (propose_file_change)
file_path = self.repo_root / relative_path

# Line 253 (propose_file_deletion)
file_path = self.repo_root / relative_path

# Line 301 (apply_changes)
file_path = self.repo_root / change.path
```

## Issue Details

There is no check for path traversal sequences like `..`. While a `WriteBoundaryEnforcer` exists in `boundaries.py`, it is **never called** in `DryRunManager`.

## Exploit Scenario

If an LLM or other input source provides a path like `../../etc/cron.d/malicious`, the system would:
1. Construct a path escaping the repository root
2. Read/write files outside the intended boundary
3. Violate the core invariant: "Only Editor writes to repo"

## Impact

- **Severity:** CRITICAL
- Arbitrary file write outside repository boundary
- Complete bypass of security constraints
- Potential system compromise via config file manipulation
- Violates Invariant #1: "Only Editor writes to repo"

## Recommended Fix

Call `WriteBoundaryEnforcer.validate_path()` before all path operations in `DryRunManager`:

```python
def __init__(self, repo_root: Path, boundary_enforcer: WriteBoundaryEnforcer | None = None) -> None:
    self.repo_root = repo_root
    self._boundary_enforcer = boundary_enforcer or WriteBoundaryEnforcer(repo_root)
    # ...

def propose_file_change(self, relative_path: str, new_content: str) -> None:
    if not self._is_active or not self._proposal:
        raise RuntimeError("Dry-run mode is not active")

    # Add validation
    validated_path = self._boundary_enforcer.validate_path(relative_path)
    file_path = validated_path
    # ... rest of method
```

## Labels

- security
- critical
- bug
