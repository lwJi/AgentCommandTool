"""Schema definitions for Scout A and Scout B responses.

Both Scouts return structured JSON with fixed, versioned schemas.
Schema version: 1
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from act.scouts.exceptions import SchemaError

# Current schema version
SCHEMA_VERSION = "1"


class Relevance(Enum):
    """File relevance levels for Scout A."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONTEXT = "context"


class RiskLevel(Enum):
    """Risk level assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Complexity(Enum):
    """Complexity assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Severity(Enum):
    """Issue severity for Scout B."""

    BLOCKING = "blocking"
    WARNING = "warning"


class BuildSystem(Enum):
    """Detected build systems for Scout B."""

    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    MAKE = "make"
    CARGO = "cargo"
    GO = "go"
    GRADLE = "gradle"
    MAVEN = "maven"
    CUSTOM = "custom"


class TestFramework(Enum):
    """Detected test frameworks for Scout B."""

    JEST = "jest"
    PYTEST = "pytest"
    GO_TEST = "go test"
    CARGO_TEST = "cargo test"
    JUNIT = "junit"
    MOCHA = "mocha"
    VITEST = "vitest"
    CUSTOM = "custom"


# ==============================================================================
# Scout A Schemas
# ==============================================================================


@dataclass
class RelevantFile:
    """A file relevant to the current task."""

    path: str
    purpose: str
    relevance: Relevance

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelevantFile":
        """Create from dictionary.

        Args:
            data: Dictionary with file data.

        Returns:
            RelevantFile instance.

        Raises:
            SchemaError: If required fields are missing or invalid.
        """
        try:
            return cls(
                path=data["path"],
                purpose=data["purpose"],
                relevance=Relevance(data["relevance"]),
            )
        except (KeyError, ValueError) as e:
            raise SchemaError(f"Invalid RelevantFile: {e}", data) from e


@dataclass
class RepoMap:
    """Repository structure mapping from Scout A."""

    relevant_files: list[RelevantFile] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    dependency_graph: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoMap":
        """Create from dictionary.

        Args:
            data: Dictionary with repo map data.

        Returns:
            RepoMap instance.
        """
        relevant_files = [
            RelevantFile.from_dict(f) for f in data.get("relevant_files", [])
        ]
        return cls(
            relevant_files=relevant_files,
            entry_points=data.get("entry_points", []),
            dependency_graph=data.get("dependency_graph", {}),
        )


@dataclass
class RiskZone:
    """A risk zone identified by Scout A."""

    file: str
    start_line: int
    end_line: int
    risk_level: RiskLevel
    complexity: Complexity
    dependencies: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    rationale: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskZone":
        """Create from dictionary.

        Args:
            data: Dictionary with risk zone data.

        Returns:
            RiskZone instance.

        Raises:
            SchemaError: If required fields are missing or invalid.
        """
        try:
            return cls(
                file=data["file"],
                start_line=data["start_line"],
                end_line=data["end_line"],
                risk_level=RiskLevel(data["risk_level"]),
                complexity=Complexity(data["complexity"]),
                dependencies=data.get("dependencies", []),
                invariants=data.get("invariants", []),
                rationale=data.get("rationale", ""),
            )
        except (KeyError, ValueError) as e:
            raise SchemaError(f"Invalid RiskZone: {e}", data) from e


@dataclass
class SafeSlice:
    """A safe slice of changes defined by Scout A."""

    id: str
    files: list[str]
    description: str
    complexity: Complexity
    order: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafeSlice":
        """Create from dictionary.

        Args:
            data: Dictionary with safe slice data.

        Returns:
            SafeSlice instance.

        Raises:
            SchemaError: If required fields are missing or invalid.
        """
        try:
            return cls(
                id=data["id"],
                files=data["files"],
                description=data["description"],
                complexity=Complexity(data["complexity"]),
                order=data.get("order"),
            )
        except (KeyError, ValueError) as e:
            raise SchemaError(f"Invalid SafeSlice: {e}", data) from e


@dataclass
class ChangeBoundaries:
    """Change boundaries with safe slices."""

    safe_slices: list[SafeSlice] = field(default_factory=list)
    ordering_constraints: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangeBoundaries":
        """Create from dictionary.

        Args:
            data: Dictionary with change boundaries data.

        Returns:
            ChangeBoundaries instance.
        """
        safe_slices = [SafeSlice.from_dict(s) for s in data.get("safe_slices", [])]
        return cls(
            safe_slices=safe_slices,
            ordering_constraints=data.get("ordering_constraints", []),
        )


@dataclass
class Conventions:
    """Code conventions detected by Scout A."""

    naming: str = ""
    patterns: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conventions":
        """Create from dictionary.

        Args:
            data: Dictionary with conventions data.

        Returns:
            Conventions instance.
        """
        return cls(
            naming=data.get("naming", ""),
            patterns=data.get("patterns", []),
            anti_patterns=data.get("anti_patterns", []),
        )


@dataclass
class PriorArt:
    """Prior art reference from Scout A."""

    file: str
    description: str
    relevance: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriorArt":
        """Create from dictionary.

        Args:
            data: Dictionary with prior art data.

        Returns:
            PriorArt instance.

        Raises:
            SchemaError: If required fields are missing.
        """
        try:
            return cls(
                file=data["file"],
                description=data["description"],
                relevance=data["relevance"],
            )
        except KeyError as e:
            raise SchemaError(f"Invalid PriorArt: {e}", data) from e


@dataclass
class ScoutAResponse:
    """Full response from Scout A (Codebase Mapper).

    Schema version: 1
    """

    schema_version: str
    repo_map: RepoMap
    risk_zones: list[RiskZone] = field(default_factory=list)
    change_boundaries: ChangeBoundaries = field(default_factory=ChangeBoundaries)
    conventions: Conventions = field(default_factory=Conventions)
    prior_art: list[PriorArt] = field(default_factory=list)
    verification_tips: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoutAResponse":
        """Create from dictionary.

        Args:
            data: Dictionary with Scout A response data.

        Returns:
            ScoutAResponse instance.

        Raises:
            SchemaError: If schema version is invalid or required fields missing.
        """
        schema_version = data.get("schema_version", "")
        if schema_version != SCHEMA_VERSION:
            msg = f"Unsupported schema version: {schema_version}, "
            msg += f"expected {SCHEMA_VERSION}"
            raise SchemaError(msg, data)

        repo_map = RepoMap.from_dict(data.get("repo_map", {}))
        risk_zones = [RiskZone.from_dict(z) for z in data.get("risk_zones", [])]
        change_boundaries = ChangeBoundaries.from_dict(
            data.get("change_boundaries", {})
        )
        conventions = Conventions.from_dict(data.get("conventions", {}))
        prior_art = [PriorArt.from_dict(p) for p in data.get("prior_art", [])]

        return cls(
            schema_version=schema_version,
            repo_map=repo_map,
            risk_zones=risk_zones,
            change_boundaries=change_boundaries,
            conventions=conventions,
            prior_art=prior_art,
            verification_tips=data.get("verification_tips", []),
            hypotheses=data.get("hypotheses", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "schema_version": self.schema_version,
            "repo_map": {
                "relevant_files": [
                    {
                        "path": f.path,
                        "purpose": f.purpose,
                        "relevance": f.relevance.value,
                    }
                    for f in self.repo_map.relevant_files
                ],
                "entry_points": self.repo_map.entry_points,
                "dependency_graph": self.repo_map.dependency_graph,
            },
            "risk_zones": [
                {
                    "file": z.file,
                    "start_line": z.start_line,
                    "end_line": z.end_line,
                    "risk_level": z.risk_level.value,
                    "complexity": z.complexity.value,
                    "dependencies": z.dependencies,
                    "invariants": z.invariants,
                    "rationale": z.rationale,
                }
                for z in self.risk_zones
            ],
            "change_boundaries": {
                "safe_slices": [
                    {
                        "id": s.id,
                        "files": s.files,
                        "description": s.description,
                        "complexity": s.complexity.value,
                        "order": s.order,
                    }
                    for s in self.change_boundaries.safe_slices
                ],
                "ordering_constraints": self.change_boundaries.ordering_constraints,
            },
            "conventions": {
                "naming": self.conventions.naming,
                "patterns": self.conventions.patterns,
                "anti_patterns": self.conventions.anti_patterns,
            },
            "prior_art": [
                {
                    "file": p.file,
                    "description": p.description,
                    "relevance": p.relevance,
                }
                for p in self.prior_art
            ],
            "verification_tips": self.verification_tips,
            "hypotheses": self.hypotheses,
        }


# ==============================================================================
# Scout B Schemas
# ==============================================================================


@dataclass
class BuildCommands:
    """Build commands discovered by Scout B."""

    install: str | None = None
    build: str = ""
    clean: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildCommands":
        """Create from dictionary.

        Args:
            data: Dictionary with build commands data.

        Returns:
            BuildCommands instance.
        """
        return cls(
            install=data.get("install"),
            build=data.get("build", ""),
            clean=data.get("clean"),
        )


@dataclass
class BuildInfo:
    """Build system information from Scout B."""

    detected_system: BuildSystem
    commands: BuildCommands
    prerequisites: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildInfo":
        """Create from dictionary.

        Args:
            data: Dictionary with build info data.

        Returns:
            BuildInfo instance.

        Raises:
            SchemaError: If required fields are missing or invalid.
        """
        try:
            return cls(
                detected_system=BuildSystem(data["detected_system"]),
                commands=BuildCommands.from_dict(data.get("commands", {})),
                prerequisites=data.get("prerequisites", []),
                notes=data.get("notes", ""),
            )
        except (KeyError, ValueError) as e:
            raise SchemaError(f"Invalid BuildInfo: {e}", data) from e


@dataclass
class TestCommands:
    """Test commands discovered by Scout B."""

    all: str = ""
    unit: str | None = None
    integration: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCommands":
        """Create from dictionary.

        Args:
            data: Dictionary with test commands data.

        Returns:
            TestCommands instance.
        """
        return cls(
            all=data.get("all", ""),
            unit=data.get("unit"),
            integration=data.get("integration"),
        )


@dataclass
class TestInfo:
    """Test system information from Scout B."""

    detected_framework: TestFramework
    commands: TestCommands
    coverage_command: str | None = None
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestInfo":
        """Create from dictionary.

        Args:
            data: Dictionary with test info data.

        Returns:
            TestInfo instance.

        Raises:
            SchemaError: If required fields are missing or invalid.
        """
        try:
            return cls(
                detected_framework=TestFramework(data["detected_framework"]),
                commands=TestCommands.from_dict(data.get("commands", {})),
                coverage_command=data.get("coverage_command"),
                notes=data.get("notes", ""),
            )
        except (KeyError, ValueError) as e:
            raise SchemaError(f"Invalid TestInfo: {e}", data) from e


@dataclass
class FailureAnalysis:
    """Failure analysis from Scout B."""

    root_cause: str = ""
    affected_files: list[str] = field(default_factory=list)
    suggested_investigation: list[str] = field(default_factory=list)
    is_flaky: bool = False
    flaky_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureAnalysis":
        """Create from dictionary.

        Args:
            data: Dictionary with failure analysis data.

        Returns:
            FailureAnalysis instance.
        """
        return cls(
            root_cause=data.get("root_cause", ""),
            affected_files=data.get("affected_files", []),
            suggested_investigation=data.get("suggested_investigation", []),
            is_flaky=data.get("is_flaky", False),
            flaky_reason=data.get("flaky_reason"),
        )


@dataclass
class EnvironmentIssue:
    """An environment issue detected by Scout B."""

    issue: str
    severity: Severity
    suggested_fix: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentIssue":
        """Create from dictionary.

        Args:
            data: Dictionary with environment issue data.

        Returns:
            EnvironmentIssue instance.

        Raises:
            SchemaError: If required fields are missing or invalid.
        """
        try:
            return cls(
                issue=data["issue"],
                severity=Severity(data["severity"]),
                suggested_fix=data["suggested_fix"],
            )
        except (KeyError, ValueError) as e:
            raise SchemaError(f"Invalid EnvironmentIssue: {e}", data) from e


@dataclass
class ScoutBResponse:
    """Full response from Scout B (Build/Test Detective).

    Schema version: 1
    """

    schema_version: str
    build: BuildInfo | None = None
    test: TestInfo | None = None
    failure_analysis: FailureAnalysis = field(default_factory=FailureAnalysis)
    environment_issues: list[EnvironmentIssue] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoutBResponse":
        """Create from dictionary.

        Args:
            data: Dictionary with Scout B response data.

        Returns:
            ScoutBResponse instance.

        Raises:
            SchemaError: If schema version is invalid.
        """
        schema_version = data.get("schema_version", "")
        if schema_version != SCHEMA_VERSION:
            msg = f"Unsupported schema version: {schema_version}, "
            msg += f"expected {SCHEMA_VERSION}"
            raise SchemaError(msg, data)

        build = None
        if "build" in data and data["build"]:
            build = BuildInfo.from_dict(data["build"])

        test = None
        if "test" in data and data["test"]:
            test = TestInfo.from_dict(data["test"])

        failure_analysis = FailureAnalysis.from_dict(
            data.get("failure_analysis", {})
        )
        environment_issues = [
            EnvironmentIssue.from_dict(i)
            for i in data.get("environment_issues", [])
        ]

        return cls(
            schema_version=schema_version,
            build=build,
            test=test,
            failure_analysis=failure_analysis,
            environment_issues=environment_issues,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "failure_analysis": {
                "root_cause": self.failure_analysis.root_cause,
                "affected_files": self.failure_analysis.affected_files,
                "suggested_investigation": (
                    self.failure_analysis.suggested_investigation
                ),
                "is_flaky": self.failure_analysis.is_flaky,
                "flaky_reason": self.failure_analysis.flaky_reason,
            },
            "environment_issues": [
                {
                    "issue": i.issue,
                    "severity": i.severity.value,
                    "suggested_fix": i.suggested_fix,
                }
                for i in self.environment_issues
            ],
        }

        if self.build:
            result["build"] = {
                "detected_system": self.build.detected_system.value,
                "commands": {
                    "install": self.build.commands.install,
                    "build": self.build.commands.build,
                    "clean": self.build.commands.clean,
                },
                "prerequisites": self.build.prerequisites,
                "notes": self.build.notes,
            }

        if self.test:
            result["test"] = {
                "detected_framework": self.test.detected_framework.value,
                "commands": {
                    "all": self.test.commands.all,
                    "unit": self.test.commands.unit,
                    "integration": self.test.commands.integration,
                },
                "coverage_command": self.test.coverage_command,
                "notes": self.test.notes,
            }

        return result


def validate_scout_a_response(data: dict[str, Any]) -> ScoutAResponse:
    """Validate and parse a Scout A response.

    Args:
        data: Raw response data.

    Returns:
        Validated ScoutAResponse.

    Raises:
        SchemaError: If validation fails.
    """
    return ScoutAResponse.from_dict(data)


def validate_scout_b_response(data: dict[str, Any]) -> ScoutBResponse:
    """Validate and parse a Scout B response.

    Args:
        data: Raw response data.

    Returns:
        Validated ScoutBResponse.

    Raises:
        SchemaError: If validation fails.
    """
    return ScoutBResponse.from_dict(data)
