# HIGH: Unsanitized Step Name Allows Path Escape in Log Files

## Summary

The `get_step_log_filename()` function constructs log filenames without sanitizing the `step_name` parameter, allowing potential path traversal attacks.

## Location

`src/act/verifier/logs.py` - Lines 71-83, 164-165

## Vulnerable Code

```python
def get_step_log_filename(step_number: int, step_name: str) -> str:
    """Generate step log filename."""
    return f"step-{step_number:02d}-{step_name}.log"  # No sanitization

# Used at line 164-165:
filename = get_step_log_filename(step_number, step_name)
log_path = logs_dir / filename
```

## Issue Details

If `step_name` contains path separators (`/`, `..`) or special characters, the resulting path could escape the logs directory.

## Exploit Scenario

A step named `../../etc/cron.d/job` would create:
```
logs_dir / "step-01-../../etc/cron.d/job.log"
```

Which resolves to a path outside the intended logs directory.

## Current Risk Assessment

Currently `step_name` comes from configuration (`VerificationStep.name`), so the immediate risk depends on whether config values are trusted. However:

1. Config could be modified by compromised LLM output
2. Future changes might introduce user-controllable step names
3. Defense in depth requires input sanitization

## Impact

- **Severity:** HIGH
- Log files written outside artifact directory
- Could overwrite important system or application files
- Violates artifact isolation guarantees

## Recommended Fix

Sanitize the step name before using it in filenames:

```python
import re

def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames."""
    # Remove path separators and special characters
    sanitized = re.sub(r'[/\\:*?"<>|]', '_', name)
    # Remove path traversal attempts
    sanitized = sanitized.replace('..', '__')
    # Limit length
    return sanitized[:64]

def get_step_log_filename(step_number: int, step_name: str) -> str:
    safe_name = sanitize_filename(step_name)
    return f"step-{step_number:02d}-{safe_name}.log"
```

## Labels

- security
- high-priority
- bug
