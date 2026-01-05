"""Tests for run ID generation and management."""

import re
from datetime import UTC, datetime
from pathlib import Path

from act.artifacts.run_id import (
    create_run_dir,
    generate_run_id,
    get_run_dir,
    is_valid_run_id,
    parse_run_id_timestamp,
)


class TestGenerateRunId:
    """Tests for generate_run_id function."""

    def test_format_matches_pattern(self) -> None:
        """Run ID matches expected format."""
        run_id = generate_run_id()

        # Format: run_{YYYYMMDD}_{HHMMSS}_{random6}
        pattern = r"^run_\d{8}_\d{6}_[a-z0-9]{6}$"
        assert re.match(pattern, run_id), f"Run ID {run_id} doesn't match pattern"

    def test_uniqueness_rapid_generation(self) -> None:
        """100 rapid generations produce all unique IDs."""
        run_ids = [generate_run_id() for _ in range(100)]

        assert len(run_ids) == len(set(run_ids)), "Duplicate run IDs generated"

    def test_timestamp_is_utc(self) -> None:
        """Run ID timestamp reflects UTC time."""
        before = datetime.now(UTC).replace(microsecond=0)
        run_id = generate_run_id()
        after = datetime.now(UTC).replace(microsecond=0)

        timestamp = parse_run_id_timestamp(run_id)
        assert timestamp is not None
        assert timestamp.tzinfo == UTC

        # Timestamp should be between before and after (both truncated to seconds)
        # Allow 1 second tolerance for edge cases at second boundaries
        from datetime import timedelta

        assert before - timedelta(seconds=1) <= timestamp <= after + timedelta(seconds=1)

    def test_starts_with_run_prefix(self) -> None:
        """Run ID starts with 'run_' prefix."""
        run_id = generate_run_id()
        assert run_id.startswith("run_")

    def test_random_suffix_is_lowercase_alphanumeric(self) -> None:
        """Random suffix contains only lowercase letters and digits."""
        run_id = generate_run_id()
        random_part = run_id.split("_")[3]

        assert len(random_part) == 6
        assert random_part.isalnum()
        assert random_part.islower() or random_part.isdigit()


class TestCreateRunDir:
    """Tests for create_run_dir function."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates run directory at expected path."""
        artifact_dir = tmp_path / "artifacts"

        run_id, run_dir = create_run_dir(artifact_dir)

        assert run_dir.is_dir()
        assert run_dir == artifact_dir / "runs" / run_id

    def test_creates_artifact_structure(self, tmp_path: Path) -> None:
        """Ensures artifact directory structure exists."""
        artifact_dir = tmp_path / "artifacts"

        create_run_dir(artifact_dir)

        assert (artifact_dir / "runs").is_dir()
        assert (artifact_dir / "cache").is_dir()

    def test_returns_valid_run_id(self, tmp_path: Path) -> None:
        """Returns a valid run ID."""
        artifact_dir = tmp_path / "artifacts"

        run_id, _ = create_run_dir(artifact_dir)

        assert is_valid_run_id(run_id)

    def test_multiple_runs_create_separate_dirs(self, tmp_path: Path) -> None:
        """Multiple runs create separate directories."""
        artifact_dir = tmp_path / "artifacts"

        run_id1, run_dir1 = create_run_dir(artifact_dir)
        run_id2, run_dir2 = create_run_dir(artifact_dir)

        assert run_id1 != run_id2
        assert run_dir1 != run_dir2
        assert run_dir1.is_dir()
        assert run_dir2.is_dir()


class TestGetRunDir:
    """Tests for get_run_dir function."""

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Returns correct path for run ID."""
        artifact_dir = tmp_path / "artifacts"
        run_id = "run_20240115_143200_abc123"

        run_dir = get_run_dir(run_id, artifact_dir)

        assert run_dir == artifact_dir / "runs" / run_id

    def test_does_not_create_directory(self, tmp_path: Path) -> None:
        """get_run_dir does not create the directory."""
        artifact_dir = tmp_path / "artifacts"
        run_id = "run_20240115_143200_abc123"

        run_dir = get_run_dir(run_id, artifact_dir)

        assert not run_dir.exists()


class TestParseRunIdTimestamp:
    """Tests for parse_run_id_timestamp function."""

    def test_parses_valid_run_id(self) -> None:
        """Parses timestamp from valid run ID."""
        run_id = "run_20240115_143200_abc123"

        timestamp = parse_run_id_timestamp(run_id)

        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15
        assert timestamp.hour == 14
        assert timestamp.minute == 32
        assert timestamp.second == 0
        assert timestamp.tzinfo == UTC

    def test_returns_none_for_invalid_format(self) -> None:
        """Returns None for invalid formats."""
        invalid_ids = [
            "invalid",
            "run_123",
            "run_20240115_143200",  # Missing random suffix
            "run_2024_143200_abc123",  # Short date
            "run_20240115_14320_abc123",  # Short time
            "test_20240115_143200_abc123",  # Wrong prefix
        ]

        for invalid_id in invalid_ids:
            assert parse_run_id_timestamp(invalid_id) is None

    def test_returns_none_for_invalid_date(self) -> None:
        """Returns None for invalid date values."""
        run_id = "run_20241332_143200_abc123"  # Month 13, Day 32

        assert parse_run_id_timestamp(run_id) is None


class TestIsValidRunId:
    """Tests for is_valid_run_id function."""

    def test_valid_run_id(self) -> None:
        """Returns True for valid run IDs."""
        valid_ids = [
            "run_20240115_143200_abc123",
            "run_20231231_235959_z9a8b7",
            "run_20240101_000000_000000",
        ]

        for run_id in valid_ids:
            assert is_valid_run_id(run_id), f"Should be valid: {run_id}"

    def test_invalid_run_id(self) -> None:
        """Returns False for invalid run IDs."""
        invalid_ids = [
            "invalid",
            "run_123",
            "run_20240115_143200",
            "run_2024_143200_abc123",
            "run_20240115_14320_abc123",
            "test_20240115_143200_abc123",
            "run_20240115_143200_ABC123",  # Uppercase
            "run_20240115_143200_abc12",  # Short suffix
            "run_20240115_143200_abc1234",  # Long suffix
            "run_20241332_143200_abc123",  # Invalid date
        ]

        for run_id in invalid_ids:
            assert not is_valid_run_id(run_id), f"Should be invalid: {run_id}"

    def test_generated_run_id_is_valid(self) -> None:
        """Generated run IDs are always valid."""
        for _ in range(10):
            run_id = generate_run_id()
            assert is_valid_run_id(run_id)
