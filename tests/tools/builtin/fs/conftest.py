"""Shared test fixtures for file system tools."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from rawagents.tools.builtin.fs._security import SecurityContext, set_security_context


@pytest.fixture
def temp_workspace() -> Generator[Path]:
    """Create a temporary workspace directory.

    Yields:
        Path to the temporary workspace with test files:
        - test.py: Simple Python file
        - subdir/nested.py: Nested Python file
        - large.txt: File with 100 lines
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create test files
        (workspace / "test.py").write_text("def hello():\n    print('Hello')\n")
        (workspace / "subdir").mkdir()
        (workspace / "subdir" / "nested.py").write_text("# nested file\nclass Nested:\n    pass\n")

        # Create a file with multiple lines
        lines = [f"Line {i}" for i in range(1, 101)]
        (workspace / "large.txt").write_text("\n".join(lines) + "\n")

        yield workspace


@pytest.fixture
def secure_context(temp_workspace: Path) -> Generator[SecurityContext]:
    """Create a workspace with security context configured.

    This fixture sets up security context that restricts operations
    to the temp_workspace directory.

    Yields:
        The configured SecurityContext.
    """
    ctx = SecurityContext(workspace=str(temp_workspace))
    set_security_context(ctx)
    yield ctx


@pytest.fixture
def permissive_context() -> Generator[SecurityContext]:
    """Create a permissive security context with no workspace restriction.

    Yields:
        A SecurityContext with no workspace boundary.
    """
    ctx = SecurityContext()  # No workspace restriction
    set_security_context(ctx)
    yield ctx


@pytest.fixture
def mock_large_file(temp_workspace: Path) -> Path:
    """Create a large test file with 10,000 lines.

    Args:
        temp_workspace: The temp workspace fixture.

    Returns:
        Path to the large file.
    """
    content = "\n".join(f"Line {i}: {'x' * 50}" for i in range(10000))
    large_file = temp_workspace / "very_large.txt"
    large_file.write_text(content)
    return large_file


@pytest.fixture
def mock_binary_file(temp_workspace: Path) -> Path:
    """Create a binary file with null bytes.

    Args:
        temp_workspace: The temp workspace fixture.

    Returns:
        Path to the binary file.
    """
    binary_file = temp_workspace / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")
    return binary_file


@pytest.fixture
def sensitive_files(temp_workspace: Path) -> dict[str, Path]:
    """Create various sensitive files for testing pattern blocking.

    Args:
        temp_workspace: The temp workspace fixture.

    Returns:
        Dict mapping description to file path.
    """
    files: dict[str, Path] = {}

    # Environment files
    env_file = temp_workspace / ".env"
    env_file.write_text("SECRET_KEY=abc123\n")
    files["env"] = env_file

    env_local = temp_workspace / ".env.local"
    env_local.write_text("DB_PASSWORD=secret\n")
    files["env_local"] = env_local

    # Credentials
    creds = temp_workspace / "credentials.json"
    creds.write_text('{"api_key": "secret"}\n')
    files["credentials"] = creds

    # SSH key
    ssh_key = temp_workspace / "id_rsa"
    ssh_key.write_text("-----BEGIN RSA PRIVATE KEY-----\nfake\n")
    files["ssh_key"] = ssh_key

    # Password file
    passwords = temp_workspace / "passwords.txt"
    passwords.write_text("user:password123\n")
    files["passwords"] = passwords

    return files


@pytest.fixture
def symlink_outside(temp_workspace: Path) -> Path | None:
    """Create a symlink pointing outside the workspace.

    Note: This may fail on Windows or systems without symlink support.

    Args:
        temp_workspace: The temp workspace fixture.

    Returns:
        Path to the symlink, or None if symlinks not supported.
    """
    symlink = temp_workspace / "evil_link"
    try:
        symlink.symlink_to("/etc/passwd")
        return symlink
    except (OSError, NotImplementedError):
        # Symlinks not supported (Windows without admin, etc.)
        return None


@pytest.fixture
def nested_dirs(temp_workspace: Path) -> Path:
    """Create a deeply nested directory structure.

    Args:
        temp_workspace: The temp workspace fixture.

    Returns:
        Path to the deepest file.
    """
    deep_path = temp_workspace
    for i in range(60):  # Deep nesting
        deep_path = deep_path / f"dir{i}"

    deep_path.mkdir(parents=True)
    deep_file = deep_path / "deep.txt"
    deep_file.write_text("very deep file\n")
    return deep_file


@pytest.fixture
def unicode_files(temp_workspace: Path) -> dict[str, Path]:
    """Create files with unicode content and names.

    Args:
        temp_workspace: The temp workspace fixture.

    Returns:
        Dict mapping description to file path.
    """
    files: dict[str, Path] = {}

    # File with unicode content
    unicode_content = temp_workspace / "unicode_content.txt"
    unicode_content.write_text("Hello 世界 🌍\nПривет мир\nこんにちは\n", encoding="utf-8")
    files["unicode_content"] = unicode_content

    # File with unicode filename
    try:
        unicode_name = temp_workspace / "файл.txt"
        unicode_name.write_text("Russian filename\n")
        files["unicode_name"] = unicode_name
    except OSError:
        pass  # Some systems don't support unicode filenames

    return files
