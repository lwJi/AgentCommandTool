"""Tests for verification run manifest management."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from act.artifacts.manifest import (
    CommandResult,
    Manifest,
    ManifestError,
    PlatformInfo,
    create_command_result,
    get_current_commit_sha,
    get_platform_info,
    get_utc_timestamp,
    read_manifest,
    write_manifest,
)


class TestWriteManifest:
    """Tests for write_manifest function."""

    def test_writes_manifest_file(self, tmp_path: Path) -> None:
        """Writes manifest.json to run directory."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        commands = [
            CommandResult(name="test", command="npm test", exit_code=0, duration_ms=1234)
        ]

        manifest_path = write_manifest(
            run_dir=run_dir,
            run_id="run_20240115_143200_abc123",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:32:05Z",
            status="PASS",
            commands_executed=commands,
            container_image="node:20-slim",
            commit_sha="abc123def456",
        )

        assert manifest_path.exists()
        assert manifest_path == run_dir / "manifest.json"

    def test_manifest_contains_all_fields(self, tmp_path: Path) -> None:
        """Manifest contains all required fields."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        commands = [
            CommandResult(name="install", command="npm ci", exit_code=0, duration_ms=5000),
            CommandResult(name="test", command="npm test", exit_code=1, duration_ms=3000),
        ]

        write_manifest(
            run_dir=run_dir,
            run_id="run_20240115_143200_abc123",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:32:08Z",
            status="FAIL",
            commands_executed=commands,
            container_image="node:20-slim",
            commit_sha="abc123def456",
        )

        manifest_path = run_dir / "manifest.json"
        data = json.loads(manifest_path.read_text())

        # Check all required fields
        assert data["run_id"] == "run_20240115_143200_abc123"
        assert data["timestamp_start"] == "2024-01-15T14:32:00Z"
        assert data["timestamp_end"] == "2024-01-15T14:32:08Z"
        assert data["commit_sha"] == "abc123def456"
        assert data["status"] == "FAIL"

        # Check commands
        assert len(data["commands_executed"]) == 2
        assert data["commands_executed"][0]["name"] == "install"
        assert data["commands_executed"][0]["command"] == "npm ci"
        assert data["commands_executed"][0]["exit_code"] == 0
        assert data["commands_executed"][0]["duration_ms"] == 5000
        assert data["commands_executed"][1]["name"] == "test"
        assert data["commands_executed"][1]["exit_code"] == 1

        # Check platform
        assert "platform" in data
        assert "os" in data["platform"]
        assert "arch" in data["platform"]
        assert data["platform"]["container_image"] == "node:20-slim"

    def test_all_fields_correctly_typed(self, tmp_path: Path) -> None:
        """All manifest fields have correct types."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        commands = [
            CommandResult(name="test", command="npm test", exit_code=0, duration_ms=1000)
        ]

        write_manifest(
            run_dir=run_dir,
            run_id="run_20240115_143200_abc123",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:32:01Z",
            status="PASS",
            commands_executed=commands,
            container_image="node:20",
            commit_sha="sha123",
        )

        data = json.loads((run_dir / "manifest.json").read_text())

        # Type checks
        assert isinstance(data["run_id"], str)
        assert isinstance(data["timestamp_start"], str)
        assert isinstance(data["timestamp_end"], str)
        assert isinstance(data["commit_sha"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["commands_executed"], list)
        assert isinstance(data["platform"], dict)

        for cmd in data["commands_executed"]:
            assert isinstance(cmd["name"], str)
            assert isinstance(cmd["command"], str)
            assert isinstance(cmd["exit_code"], int)
            assert isinstance(cmd["duration_ms"], int)

        assert isinstance(data["platform"]["os"], str)
        assert isinstance(data["platform"]["arch"], str)
        assert isinstance(data["platform"]["container_image"], str)


class TestReadManifest:
    """Tests for read_manifest function."""

    def test_reads_written_manifest(self, tmp_path: Path) -> None:
        """Can read back a written manifest."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        commands = [
            CommandResult(name="test", command="npm test", exit_code=0, duration_ms=1234)
        ]

        manifest_path = write_manifest(
            run_dir=run_dir,
            run_id="run_20240115_143200_abc123",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:32:05Z",
            status="PASS",
            commands_executed=commands,
            container_image="node:20-slim",
            commit_sha="abc123",
        )

        manifest = read_manifest(manifest_path)

        assert manifest.run_id == "run_20240115_143200_abc123"
        assert manifest.timestamp_start == "2024-01-15T14:32:00Z"
        assert manifest.timestamp_end == "2024-01-15T14:32:05Z"
        assert manifest.commit_sha == "abc123"
        assert manifest.status == "PASS"
        assert len(manifest.commands_executed) == 1
        assert manifest.commands_executed[0].name == "test"
        assert manifest.platform.container_image == "node:20-slim"

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """Reading nonexistent file raises error."""
        manifest_path = tmp_path / "nonexistent.json"

        with pytest.raises(ManifestError) as exc_info:
            read_manifest(manifest_path)

        assert "Failed to read manifest" in str(exc_info.value)

    def test_read_invalid_json(self, tmp_path: Path) -> None:
        """Reading invalid JSON raises error."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("not valid json")

        with pytest.raises(ManifestError):
            read_manifest(manifest_path)


class TestGetCurrentCommitSha:
    """Tests for get_current_commit_sha function."""

    def test_returns_commit_sha(self) -> None:
        """Returns a valid commit SHA in a git repo."""
        sha = get_current_commit_sha()

        # Should be a valid hex string or "unknown"
        if sha != "unknown":
            assert len(sha) == 40
            assert all(c in "0123456789abcdef" for c in sha)


class TestGetPlatformInfo:
    """Tests for get_platform_info function."""

    def test_returns_platform_info(self) -> None:
        """Returns valid platform info."""
        info = get_platform_info("node:20-slim")

        assert isinstance(info.os, str)
        assert len(info.os) > 0
        assert isinstance(info.arch, str)
        assert len(info.arch) > 0
        assert info.container_image == "node:20-slim"


class TestGetUtcTimestamp:
    """Tests for get_utc_timestamp function."""

    def test_returns_iso8601_format(self) -> None:
        """Returns timestamp in ISO8601 format."""
        timestamp = get_utc_timestamp()

        # Should match pattern YYYY-MM-DDTHH:MM:SSZ
        assert len(timestamp) == 20
        assert timestamp[4] == "-"
        assert timestamp[7] == "-"
        assert timestamp[10] == "T"
        assert timestamp[13] == ":"
        assert timestamp[16] == ":"
        assert timestamp[19] == "Z"

    def test_timestamp_is_current(self) -> None:
        """Timestamp reflects current time."""
        before = datetime.now(UTC)
        timestamp_str = get_utc_timestamp()
        after = datetime.now(UTC)

        # Parse the timestamp
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )

        # Allow 1 second tolerance
        assert before - timedelta(seconds=1) <= timestamp <= after + timedelta(seconds=1)


class TestCreateCommandResult:
    """Tests for create_command_result function."""

    def test_calculates_duration(self) -> None:
        """Calculates duration in milliseconds."""
        start = datetime(2024, 1, 15, 14, 32, 0, tzinfo=UTC)
        end = datetime(2024, 1, 15, 14, 32, 5, tzinfo=UTC)

        result = create_command_result(
            name="test",
            command="npm test",
            exit_code=0,
            start_time=start,
            end_time=end,
        )

        assert result.duration_ms == 5000

    def test_preserves_command_info(self) -> None:
        """Preserves name, command, and exit code."""
        start = datetime.now(UTC)
        end = start + timedelta(seconds=1)

        result = create_command_result(
            name="build",
            command="npm run build",
            exit_code=1,
            start_time=start,
            end_time=end,
        )

        assert result.name == "build"
        assert result.command == "npm run build"
        assert result.exit_code == 1


class TestManifestDataclasses:
    """Tests for manifest dataclasses."""

    def test_command_result_creation(self) -> None:
        """CommandResult can be created directly."""
        cmd = CommandResult(
            name="test", command="npm test", exit_code=0, duration_ms=1234
        )

        assert cmd.name == "test"
        assert cmd.command == "npm test"
        assert cmd.exit_code == 0
        assert cmd.duration_ms == 1234

    def test_platform_info_creation(self) -> None:
        """PlatformInfo can be created directly."""
        info = PlatformInfo(os="linux", arch="x64", container_image="node:20")

        assert info.os == "linux"
        assert info.arch == "x64"
        assert info.container_image == "node:20"

    def test_manifest_to_dict(self) -> None:
        """Manifest.to_dict() produces correct structure."""
        manifest = Manifest(
            run_id="run_123",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:32:05Z",
            commit_sha="abc123",
            status="PASS",
            commands_executed=[
                CommandResult(
                    name="test", command="npm test", exit_code=0, duration_ms=1000
                )
            ],
            platform=PlatformInfo(os="linux", arch="x64", container_image="node:20"),
        )

        data = manifest.to_dict()

        assert data["run_id"] == "run_123"
        assert len(data["commands_executed"]) == 1
        assert data["platform"]["os"] == "linux"
