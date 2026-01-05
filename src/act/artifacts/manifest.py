"""Verification run manifest management."""

import json
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ManifestError(Exception):
    """Error related to manifest operations."""

    pass


@dataclass
class CommandResult:
    """Result of executing a verification command."""

    name: str
    command: str
    exit_code: int
    duration_ms: int


@dataclass
class PlatformInfo:
    """Platform information for the verification run."""

    os: str
    arch: str
    container_image: str


@dataclass
class Manifest:
    """Verification run manifest."""

    run_id: str
    timestamp_start: str
    timestamp_end: str
    commit_sha: str
    status: str
    commands_executed: list[CommandResult]
    platform: PlatformInfo

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "commit_sha": self.commit_sha,
            "status": self.status,
            "commands_executed": [
                {
                    "name": cmd.name,
                    "command": cmd.command,
                    "exit_code": cmd.exit_code,
                    "duration_ms": cmd.duration_ms,
                }
                for cmd in self.commands_executed
            ],
            "platform": {
                "os": self.platform.os,
                "arch": self.platform.arch,
                "container_image": self.platform.container_image,
            },
        }


def get_current_commit_sha() -> str:
    """Get the current git commit SHA.

    Returns:
        The commit SHA or "unknown" if not in a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def get_platform_info(container_image: str) -> PlatformInfo:
    """Get current platform information.

    Args:
        container_image: The container image used for verification.

    Returns:
        PlatformInfo with current OS and architecture.
    """
    return PlatformInfo(
        os=platform.system().lower(),
        arch=platform.machine(),
        container_image=container_image,
    )


def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO8601 format.

    Returns:
        ISO8601 formatted timestamp string.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_manifest(
    run_dir: Path,
    run_id: str,
    timestamp_start: str,
    timestamp_end: str,
    status: str,
    commands_executed: list[CommandResult],
    container_image: str,
    commit_sha: str | None = None,
) -> Path:
    """Write a verification manifest to the run directory.

    Args:
        run_dir: Path to the run directory.
        run_id: The run ID.
        timestamp_start: ISO8601 start timestamp.
        timestamp_end: ISO8601 end timestamp.
        status: Verification status (PASS, FAIL, INFRA_ERROR).
        commands_executed: List of executed commands with results.
        container_image: The container image used.
        commit_sha: Optional commit SHA. If None, fetches current HEAD.

    Returns:
        Path to the written manifest file.

    Raises:
        ManifestError: If writing fails.
    """
    if commit_sha is None:
        commit_sha = get_current_commit_sha()

    manifest = Manifest(
        run_id=run_id,
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
        commit_sha=commit_sha,
        status=status,
        commands_executed=commands_executed,
        platform=get_platform_info(container_image),
    )

    manifest_path = run_dir / "manifest.json"

    try:
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))
    except OSError as e:
        raise ManifestError(f"Failed to write manifest: {e}") from e

    return manifest_path


def read_manifest(manifest_path: Path) -> Manifest:
    """Read a manifest from a file.

    Args:
        manifest_path: Path to the manifest file.

    Returns:
        Parsed Manifest object.

    Raises:
        ManifestError: If reading or parsing fails.
    """
    try:
        content = manifest_path.read_text()
        data = json.loads(content)

        return Manifest(
            run_id=data["run_id"],
            timestamp_start=data["timestamp_start"],
            timestamp_end=data["timestamp_end"],
            commit_sha=data["commit_sha"],
            status=data["status"],
            commands_executed=[
                CommandResult(
                    name=cmd["name"],
                    command=cmd["command"],
                    exit_code=cmd["exit_code"],
                    duration_ms=cmd["duration_ms"],
                )
                for cmd in data["commands_executed"]
            ],
            platform=PlatformInfo(
                os=data["platform"]["os"],
                arch=data["platform"]["arch"],
                container_image=data["platform"]["container_image"],
            ),
        )
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise ManifestError(f"Failed to read manifest: {e}") from e


def create_command_result(
    name: str,
    command: str,
    exit_code: int,
    start_time: datetime,
    end_time: datetime,
) -> CommandResult:
    """Create a CommandResult from execution data.

    Args:
        name: Step name.
        command: The command that was executed.
        exit_code: Exit code of the command.
        start_time: When the command started.
        end_time: When the command finished.

    Returns:
        CommandResult with calculated duration.
    """
    duration = end_time - start_time
    duration_ms = int(duration.total_seconds() * 1000)
    return CommandResult(
        name=name,
        command=command,
        exit_code=exit_code,
        duration_ms=duration_ms,
    )
