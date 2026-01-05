"""File exclusion filter for Scout analysis.

Scouts exclude binary files and secret files from analysis.
"""

import fnmatch
import os
from pathlib import Path

# Binary file extensions to exclude
BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
        # Compiled binaries
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".a",
        ".o",
        ".obj",
        ".pyc",
        ".pyo",
        ".class",
        ".wasm",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".jar",
        ".war",
        ".ear",
        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        # Media
        ".mp3",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wav",
        ".flac",
        ".ogg",
        # Documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Databases
        ".db",
        ".sqlite",
        ".sqlite3",
        # Other
        ".bin",
        ".dat",
        ".pickle",
        ".pkl",
        ".npy",
        ".npz",
        ".parquet",
        ".feather",
    }
)

# Secret file patterns to exclude (using fnmatch glob patterns)
SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "*credentials*",
    "*secrets*",
    "*secret*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_rsa.*",
    "id_dsa",
    "id_dsa.*",
    "id_ed25519",
    "id_ed25519.*",
    ".htpasswd",
    ".netrc",
    ".npmrc",
    ".pypirc",
)

# Directories that should always be excluded
EXCLUDED_DIRECTORIES: frozenset[str] = frozenset(
    {
        # Version control
        ".git",
        ".svn",
        ".hg",
        # Dependencies
        "node_modules",
        "__pycache__",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        ".env",
        "virtualenv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".coverage",
        "htmlcov",
        # Build outputs
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        "out",
        # IDE
        ".idea",
        ".vscode",
        # OS
        ".DS_Store",
        "Thumbs.db",
    }
)


def is_binary_file(file_path: str | Path) -> bool:
    """Check if a file is a binary file based on extension.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file appears to be binary.
    """
    path = Path(file_path)
    return path.suffix.lower() in BINARY_EXTENSIONS


def is_secret_file(file_path: str | Path) -> bool:
    """Check if a file matches secret file patterns.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file matches a secret pattern.
    """
    path = Path(file_path)
    filename = path.name.lower()

    for pattern in SECRET_PATTERNS:
        if fnmatch.fnmatch(filename, pattern.lower()):
            return True
    return False


def is_excluded_directory(dir_name: str) -> bool:
    """Check if a directory name should be excluded.

    Args:
        dir_name: Name of the directory (not full path).

    Returns:
        True if the directory should be excluded.
    """
    return dir_name in EXCLUDED_DIRECTORIES


def should_exclude_file(file_path: str | Path) -> bool:
    """Check if a file should be excluded from Scout analysis.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file should be excluded.
    """
    return is_binary_file(file_path) or is_secret_file(file_path)


def should_exclude_path(file_path: str | Path, repo_root: str | Path) -> bool:
    """Check if a path should be excluded, including directory checks.

    Args:
        file_path: Path to the file (absolute or relative).
        repo_root: Root directory of the repository.

    Returns:
        True if the path should be excluded.
    """
    # Convert to Path objects
    path = Path(file_path)
    root = Path(repo_root)

    # Make path relative to repo root if it's absolute
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError:
            # Path is not under repo_root
            return True

    # Check each component of the path for excluded directories
    for part in path.parts[:-1]:  # Exclude the filename itself
        if is_excluded_directory(part):
            return True

    # Check the file itself
    return should_exclude_file(path)


def filter_files(
    files: list[str],
    repo_root: str | Path,
) -> list[str]:
    """Filter a list of files, excluding binaries and secrets.

    Args:
        files: List of file paths (absolute or relative to repo_root).
        repo_root: Root directory of the repository.

    Returns:
        List of files that should be included in analysis.
    """
    return [f for f in files if not should_exclude_path(f, repo_root)]


def discover_files(
    repo_root: str | Path,
    max_files: int | None = None,
) -> list[str]:
    """Discover all analyzable files in a repository.

    Args:
        repo_root: Root directory of the repository.
        max_files: Maximum number of files to return (None for unlimited).

    Returns:
        List of relative file paths that are suitable for analysis.
    """
    root = Path(repo_root)
    files: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out excluded directories (modifying in place for efficiency)
        dirnames[:] = [d for d in dirnames if not is_excluded_directory(d)]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            rel_path = file_path.relative_to(root)

            if not should_exclude_file(rel_path):
                files.append(str(rel_path))

                if max_files is not None and len(files) >= max_files:
                    return files

    return files
