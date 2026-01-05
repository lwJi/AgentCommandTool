"""Unit tests for Scout schema definitions."""

import pytest

from act.scouts.exceptions import SchemaError
from act.scouts.schemas import (
    SCHEMA_VERSION,
    BuildCommands,
    BuildInfo,
    BuildSystem,
    Complexity,
    EnvironmentIssue,
    FailureAnalysis,
    Relevance,
    RelevantFile,
    RepoMap,
    RiskLevel,
    RiskZone,
    SafeSlice,
    ScoutAResponse,
    ScoutBResponse,
    Severity,
    TestFramework,
    TestInfo,
    validate_scout_a_response,
    validate_scout_b_response,
)


class TestEnums:
    """Tests for schema enums."""

    def test_relevance_values(self) -> None:
        """Test Relevance enum values."""
        assert Relevance.PRIMARY.value == "primary"
        assert Relevance.SECONDARY.value == "secondary"
        assert Relevance.CONTEXT.value == "context"

    def test_risk_level_values(self) -> None:
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"

    def test_complexity_values(self) -> None:
        """Test Complexity enum values."""
        assert Complexity.LOW.value == "low"
        assert Complexity.MEDIUM.value == "medium"
        assert Complexity.HIGH.value == "high"

    def test_severity_values(self) -> None:
        """Test Severity enum values."""
        assert Severity.BLOCKING.value == "blocking"
        assert Severity.WARNING.value == "warning"

    def test_build_system_values(self) -> None:
        """Test BuildSystem enum values."""
        expected = ["npm", "yarn", "pnpm", "make", "cargo", "go", "gradle", "maven", "custom"]
        for val in expected:
            assert BuildSystem(val).value == val

    def test_test_framework_values(self) -> None:
        """Test TestFramework enum values."""
        expected = ["jest", "pytest", "go test", "cargo test", "junit", "mocha", "vitest", "custom"]
        for val in expected:
            assert TestFramework(val).value == val


class TestRelevantFile:
    """Tests for RelevantFile dataclass."""

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "path": "src/main.py",
            "purpose": "Main entry point",
            "relevance": "primary",
        }
        file = RelevantFile.from_dict(data)
        assert file.path == "src/main.py"
        assert file.purpose == "Main entry point"
        assert file.relevance == Relevance.PRIMARY

    def test_from_dict_missing_field(self) -> None:
        """Test error on missing field."""
        data = {"path": "src/main.py", "purpose": "Main entry point"}
        with pytest.raises(SchemaError):
            RelevantFile.from_dict(data)

    def test_from_dict_invalid_relevance(self) -> None:
        """Test error on invalid relevance value."""
        data = {
            "path": "src/main.py",
            "purpose": "Main entry point",
            "relevance": "invalid",
        }
        with pytest.raises(SchemaError):
            RelevantFile.from_dict(data)


class TestRepoMap:
    """Tests for RepoMap dataclass."""

    def test_from_dict_full(self) -> None:
        """Test creating from full dictionary."""
        data = {
            "relevant_files": [
                {"path": "a.py", "purpose": "File A", "relevance": "primary"},
                {"path": "b.py", "purpose": "File B", "relevance": "secondary"},
            ],
            "entry_points": ["main.py"],
            "dependency_graph": {"a.py": ["b.py"]},
        }
        repo_map = RepoMap.from_dict(data)
        assert len(repo_map.relevant_files) == 2
        assert repo_map.entry_points == ["main.py"]
        assert repo_map.dependency_graph == {"a.py": ["b.py"]}

    def test_from_dict_empty(self) -> None:
        """Test creating from empty dictionary."""
        repo_map = RepoMap.from_dict({})
        assert repo_map.relevant_files == []
        assert repo_map.entry_points == []
        assert repo_map.dependency_graph == {}


class TestRiskZone:
    """Tests for RiskZone dataclass."""

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "file": "src/auth.py",
            "start_line": 10,
            "end_line": 50,
            "risk_level": "high",
            "complexity": "medium",
            "dependencies": ["db.py"],
            "invariants": ["must validate token"],
            "rationale": "Critical security code",
        }
        zone = RiskZone.from_dict(data)
        assert zone.file == "src/auth.py"
        assert zone.start_line == 10
        assert zone.end_line == 50
        assert zone.risk_level == RiskLevel.HIGH
        assert zone.complexity == Complexity.MEDIUM
        assert zone.dependencies == ["db.py"]
        assert zone.invariants == ["must validate token"]
        assert zone.rationale == "Critical security code"

    def test_from_dict_minimal(self) -> None:
        """Test creating with minimal required fields."""
        data = {
            "file": "src/auth.py",
            "start_line": 10,
            "end_line": 50,
            "risk_level": "low",
            "complexity": "low",
        }
        zone = RiskZone.from_dict(data)
        assert zone.dependencies == []
        assert zone.invariants == []
        assert zone.rationale == ""


class TestSafeSlice:
    """Tests for SafeSlice dataclass."""

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "id": "slice-1",
            "files": ["a.py", "b.py"],
            "description": "Update authentication",
            "complexity": "medium",
            "order": 1,
        }
        slice_obj = SafeSlice.from_dict(data)
        assert slice_obj.id == "slice-1"
        assert slice_obj.files == ["a.py", "b.py"]
        assert slice_obj.description == "Update authentication"
        assert slice_obj.complexity == Complexity.MEDIUM
        assert slice_obj.order == 1

    def test_from_dict_null_order(self) -> None:
        """Test creating with null order."""
        data = {
            "id": "slice-1",
            "files": ["a.py"],
            "description": "Change",
            "complexity": "low",
        }
        slice_obj = SafeSlice.from_dict(data)
        assert slice_obj.order is None


class TestScoutAResponse:
    """Tests for ScoutAResponse dataclass."""

    def test_from_dict_full(self) -> None:
        """Test creating from full dictionary."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {
                "relevant_files": [
                    {"path": "main.py", "purpose": "Entry", "relevance": "primary"}
                ],
                "entry_points": ["main.py"],
                "dependency_graph": {},
            },
            "risk_zones": [
                {
                    "file": "auth.py",
                    "start_line": 1,
                    "end_line": 100,
                    "risk_level": "high",
                    "complexity": "high",
                }
            ],
            "change_boundaries": {
                "safe_slices": [
                    {
                        "id": "s1",
                        "files": ["auth.py"],
                        "description": "Auth changes",
                        "complexity": "medium",
                    }
                ],
                "ordering_constraints": ["s1 before s2"],
            },
            "conventions": {
                "naming": "snake_case",
                "patterns": ["factory"],
                "anti_patterns": ["singleton"],
            },
            "prior_art": [
                {"file": "old_auth.py", "description": "Old impl", "relevance": "reference"}
            ],
            "verification_tips": ["Run auth tests"],
            "hypotheses": ["Auth refactor needed"],
        }
        response = ScoutAResponse.from_dict(data)
        assert response.schema_version == SCHEMA_VERSION
        assert len(response.repo_map.relevant_files) == 1
        assert len(response.risk_zones) == 1
        assert len(response.change_boundaries.safe_slices) == 1
        assert response.conventions.naming == "snake_case"

    def test_from_dict_wrong_version(self) -> None:
        """Test error on wrong schema version."""
        data = {
            "schema_version": "99",
            "repo_map": {},
        }
        with pytest.raises(SchemaError) as exc_info:
            ScoutAResponse.from_dict(data)
        assert "schema version" in exc_info.value.message.lower()

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        response = ScoutAResponse(
            schema_version=SCHEMA_VERSION,
            repo_map=RepoMap(
                relevant_files=[
                    RelevantFile(
                        path="main.py",
                        purpose="Entry",
                        relevance=Relevance.PRIMARY,
                    )
                ],
                entry_points=["main.py"],
            ),
        )
        data = response.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert len(data["repo_map"]["relevant_files"]) == 1
        assert data["repo_map"]["relevant_files"][0]["relevance"] == "primary"


class TestBuildInfo:
    """Tests for BuildInfo dataclass."""

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "detected_system": "npm",
            "commands": {
                "install": "npm install",
                "build": "npm run build",
                "clean": "npm run clean",
            },
            "prerequisites": ["node >= 18"],
            "notes": "Uses TypeScript",
        }
        info = BuildInfo.from_dict(data)
        assert info.detected_system == BuildSystem.NPM
        assert info.commands.install == "npm install"
        assert info.commands.build == "npm run build"
        assert info.prerequisites == ["node >= 18"]


class TestTestInfo:
    """Tests for TestInfo dataclass."""

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "detected_framework": "pytest",
            "commands": {
                "all": "pytest",
                "unit": "pytest tests/unit",
                "integration": "pytest tests/integration",
            },
            "coverage_command": "pytest --cov",
            "notes": "Uses pytest-asyncio",
        }
        info = TestInfo.from_dict(data)
        assert info.detected_framework == TestFramework.PYTEST
        assert info.commands.all == "pytest"
        assert info.coverage_command == "pytest --cov"


class TestFailureAnalysis:
    """Tests for FailureAnalysis dataclass."""

    def test_from_dict_full(self) -> None:
        """Test creating from full dictionary."""
        data = {
            "root_cause": "Type mismatch in function call",
            "affected_files": ["src/api.py", "src/types.py"],
            "suggested_investigation": ["Check type annotations"],
            "is_flaky": True,
            "flaky_reason": "Network-dependent",
        }
        analysis = FailureAnalysis.from_dict(data)
        assert analysis.root_cause == "Type mismatch in function call"
        assert len(analysis.affected_files) == 2
        assert analysis.is_flaky is True
        assert analysis.flaky_reason == "Network-dependent"

    def test_from_dict_defaults(self) -> None:
        """Test creating with default values."""
        analysis = FailureAnalysis.from_dict({})
        assert analysis.root_cause == ""
        assert analysis.affected_files == []
        assert analysis.is_flaky is False
        assert analysis.flaky_reason is None


class TestEnvironmentIssue:
    """Tests for EnvironmentIssue dataclass."""

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "issue": "Node.js not installed",
            "severity": "blocking",
            "suggested_fix": "Install Node.js 18+",
        }
        issue = EnvironmentIssue.from_dict(data)
        assert issue.issue == "Node.js not installed"
        assert issue.severity == Severity.BLOCKING
        assert issue.suggested_fix == "Install Node.js 18+"


class TestScoutBResponse:
    """Tests for ScoutBResponse dataclass."""

    def test_from_dict_full(self) -> None:
        """Test creating from full dictionary."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "build": {
                "detected_system": "npm",
                "commands": {"build": "npm run build"},
            },
            "test": {
                "detected_framework": "jest",
                "commands": {"all": "npm test"},
            },
            "failure_analysis": {
                "root_cause": "Test timeout",
                "affected_files": ["test.js"],
            },
            "environment_issues": [
                {
                    "issue": "Missing dep",
                    "severity": "warning",
                    "suggested_fix": "npm install",
                }
            ],
        }
        response = ScoutBResponse.from_dict(data)
        assert response.schema_version == SCHEMA_VERSION
        assert response.build is not None
        assert response.build.detected_system == BuildSystem.NPM
        assert response.test is not None
        assert response.test.detected_framework == TestFramework.JEST

    def test_from_dict_minimal(self) -> None:
        """Test creating with minimal fields."""
        data = {"schema_version": SCHEMA_VERSION}
        response = ScoutBResponse.from_dict(data)
        assert response.build is None
        assert response.test is None

    def test_from_dict_wrong_version(self) -> None:
        """Test error on wrong schema version."""
        data = {"schema_version": "99"}
        with pytest.raises(SchemaError):
            ScoutBResponse.from_dict(data)

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        response = ScoutBResponse(
            schema_version=SCHEMA_VERSION,
            build=BuildInfo(
                detected_system=BuildSystem.NPM,
                commands=BuildCommands(build="npm run build"),
            ),
        )
        data = response.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["build"]["detected_system"] == "npm"


class TestValidateFunctions:
    """Tests for validation helper functions."""

    def test_validate_scout_a_response_valid(self) -> None:
        """Test validating valid Scout A response."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {},
        }
        response = validate_scout_a_response(data)
        assert isinstance(response, ScoutAResponse)

    def test_validate_scout_a_response_invalid(self) -> None:
        """Test validating invalid Scout A response."""
        with pytest.raises(SchemaError):
            validate_scout_a_response({"schema_version": "invalid"})

    def test_validate_scout_b_response_valid(self) -> None:
        """Test validating valid Scout B response."""
        data = {"schema_version": SCHEMA_VERSION}
        response = validate_scout_b_response(data)
        assert isinstance(response, ScoutBResponse)

    def test_validate_scout_b_response_invalid(self) -> None:
        """Test validating invalid Scout B response."""
        with pytest.raises(SchemaError):
            validate_scout_b_response({"schema_version": "invalid"})
