# CRITICAL: Dangerous pkill Pattern Kills All Container Processes

## Summary

When a verification step times out, the pipeline executor uses an overly broad `pkill` pattern that kills all processes in the container instead of just the timed-out command.

## Location

`src/act/verifier/pipeline.py` - Lines 201-205

## Vulnerable Code

```python
# Try to kill any running processes in the container
with contextlib.suppress(Exception):
    self._container_manager.exec_in_container(
        self._container,
        "pkill -9 -f .",   # Pattern "." matches ANY character
        env_vars=None,
    )
```

## Issue Details

The regex pattern `.` matches any single character. This means `pkill -9 -f .` will kill **all processes** in the container whose command line contains any character (i.e., virtually all processes).

## Impact

- **Severity:** CRITICAL
- Kills essential container processes (init, shell, etc.)
- Container becomes unstable or unusable after timeout
- Verification results become unreliable
- Resource leaks if cleanup processes are killed
- The thread at line 208 may still be alive after the 5-second wait, leaving dangling threads

## Recommended Fix

Use a more targeted approach to kill the specific command:

```python
# Option 1: Use timeout command wrapper (preferred)
# Wrap commands with `timeout` which handles signals properly
wrapped_command = f"timeout --signal=KILL {timeout_seconds}s {command}"

# Option 2: Track and kill specific process
# Execute command with exec to replace shell, then track PID

# Option 3: Kill user processes only (less aggressive)
"pkill -9 -u $(whoami)"
```

## Additional Issues

The code also has a potential thread leak:
```python
thread.join(timeout=5)  # Thread may still be alive after this
```

If the thread doesn't terminate within 5 seconds, it continues running as a dangling thread.

## Labels

- security
- critical
- bug
- reliability
