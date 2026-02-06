"""Security module for file system tools.

This module provides path validation and workspace boundary enforcement
to prevent path traversal attacks and unauthorized file access.

CRITICAL: All file operations MUST use this module for path validation.

Three Layers of Security:
    1. PATH VALIDATION (this module): Resolve symlinks, normalize paths,
       check workspace boundaries, block sensitive patterns.
    2. PERMISSION CHECK (optional): User-configurable allow/deny/ask rules.
    3. OS-LEVEL SANDBOX (optional): bubblewrap, seatbelt, Docker.

Key Features:
    - Symlink attack prevention (resolves ALL symlinks before validation)
    - Path traversal prevention (detects ../ escape attempts)
    - Sensitive file protection (blocks .env, credentials, keys)
    - Read-before-edit tracking (prevents blind overwrites)
    - Resource limits (file size, path depth)

Example:
    >>> ctx = SecurityContext(workspace="/home/user/project")
    >>> set_security_context(ctx)
    >>>
    >>> # Safe path inside workspace
    >>> path = validate_path("/home/user/project/src/main.py")
    >>> print(path)  # PosixPath('/home/user/project/src/main.py')
    >>>
    >>> # Blocked: outside workspace
    >>> validate_path("/etc/passwd")
    WorkspaceSecurityError: Access denied: /etc/passwd is outside workspace
    >>>
    >>> # Blocked: symlink attack
    >>> # If ./leak -> /etc/passwd
    >>> validate_path("/home/user/project/leak")
    WorkspaceSecurityError: Access denied: ./leak resolves to /etc/passwd
    which is outside workspace /home/user/project
"""

from __future__ import annotations

import contextvars
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rawagents.tools.builtin.fs._utils import (
    detect_binary as _utils_detect_binary,
)
from rawagents.tools.builtin.fs._utils import (
    is_media_file as _utils_is_media_file,
)


__all__ = [
    "WorkspaceSecurityError",
    "SecurityContextNotSetError",
    "SecurityContext",
    "set_security_context",
    "get_security_context",
    "validate_path",
]


class WorkspaceSecurityError(PermissionError):
    """Raised when a path access violates security constraints.

    Attributes:
        path: The original path that was requested.
        resolved_path: The actual path after symlink resolution (if available).
        pattern: The denied pattern that matched (if applicable).
    """

    def __init__(
        self,
        message: str,
        path: str,
        resolved_path: Optional[str] = None,
        pattern: Optional[str] = None,
    ):
        super().__init__(message)
        self.path = path
        self.resolved_path = resolved_path
        self.pattern = pattern


class SecurityContextNotSetError(RuntimeError):
    """Raised when no security context has been configured.

    This error indicates that file operations were attempted without
    first calling set_security_context() with a properly configured
    SecurityContext.

    Example:
        >>> # This will raise SecurityContextNotSetError
        >>> from rawagents.tools.builtin.fs import read
        >>> await read("/some/path")  # No context set!
        SecurityContextNotSetError: No SecurityContext has been configured...

        >>> # Correct usage:
        >>> from rawagents.tools.builtin.fs import (
        ...     SecurityContext, set_security_context, read
        ... )
        >>> ctx = SecurityContext(workspace="/home/user/project")
        >>> set_security_context(ctx)
        >>> await read("/home/user/project/file.py")  # Works!
    """

    pass


# Default denied patterns for sensitive files
_DEFAULT_DENIED_PATTERNS: list[str] = [
    # Environment and secrets
    "*.env",
    "*.env.*",
    ".env",
    ".env.*",
    "*/.env",
    "*/.env.*",
    # Credentials
    "*credentials*",
    "*secret*",
    "*password*",
    "*token*",
    # Cryptographic keys
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*id_rsa*",
    "*id_ed25519*",
    "*id_dsa*",
    "*id_ecdsa*",
    "*.keystore",
    # AWS
    "*.aws/credentials",
    "*.aws/config",
    # SSH
    "*.ssh/config",
    "*.ssh/known_hosts",
    # Git credentials
    "*.git-credentials",
    "*.gitconfig",
    "*.netrc",
]

# Default binary extensions to reject
_DEFAULT_BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Executables
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".com",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        # Python bytecode
        ".pyc",
        ".pyo",
        ".pyd",
        # Java
        ".class",
        ".jar",
        ".war",
        ".ear",
        # .NET
        ".msi",
        # WebAssembly
        ".wasm",
        # Database
        ".db",
        ".sqlite",
        ".sqlite3",
        # Images (handled separately via MIME)
        ".ico",
        # Other binary
        ".o",
        ".a",
        ".lib",
        ".obj",
    }
)


@dataclass
class SecurityContext:
    """Security context for file system operations.

    This class enforces:
    1. Workspace boundary restrictions
    2. Symlink attack prevention
    3. Sensitive file pattern blocking
    4. Read-before-edit tracking
    5. Resource limits

    The validation order is critical for security:
    1. Resolve ALL symlinks → get canonical path
    2. Check path depth < max_path_depth
    3. Check against denied patterns (unless in allowlist)
    4. Verify path is within workspace boundary

    Attributes:
        workspace: Root directory for allowed operations. If None, no boundary check.
        denied_patterns: Glob patterns for files that should never be accessed.
        allowed_patterns: Glob patterns that override denied_patterns (allowlist).
        max_file_size: Maximum file size in bytes (default: 10MB).
        max_path_depth: Maximum directory depth (default: 50).
        binary_extensions: Extensions to treat as binary.

    Example:
        >>> ctx = SecurityContext(workspace="/home/user/project")
        >>> ctx.validate_path("/home/user/project/src/main.py")
        PosixPath('/home/user/project/src/main.py')

        >>> ctx.validate_path("/etc/passwd")
        WorkspaceSecurityError: Access denied: /etc/passwd is outside workspace
    """

    workspace: Optional[str] = None
    """Root directory for allowed file operations. If None, no restriction."""

    denied_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_DENIED_PATTERNS))
    """Glob patterns for files that should never be accessed."""

    allowed_patterns: list[str] = field(default_factory=list)
    """Glob patterns that override denied_patterns (allowlist)."""

    max_file_size: int = 10 * 1024 * 1024  # 10MB
    """Maximum file size in bytes for read/write operations."""

    max_path_depth: int = 50
    """Maximum directory depth to prevent deeply nested attacks."""

    binary_extensions: frozenset[str] = field(
        default_factory=lambda: _DEFAULT_BINARY_EXTENSIONS
    )
    """Extensions to treat as binary files."""

    # Internal state
    _resolved_workspace: Optional[Path] = field(default=None, init=False, repr=False)
    _read_files: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        """Resolve workspace path on initialization."""
        if self.workspace:
            self._resolved_workspace = Path(self.workspace).resolve()

    def validate_path(self, path: str, check_exists: bool = True) -> Path:
        """Validate a file path against security constraints.

        This method performs the following checks IN ORDER:
        1. Resolve ALL symlinks to get the canonical path
        2. Check path depth limit
        3. Check against denied patterns (unless in allowlist)
        4. Verify path is within workspace boundary

        Args:
            path: The path to validate (can be relative or absolute).
            check_exists: If True, use strict resolution (file must exist).
                         If False, resolve parent for new files.

        Returns:
            The resolved, validated Path object.

        Raises:
            WorkspaceSecurityError: If the path violates any security constraint.
            FileNotFoundError: If check_exists=True and file doesn't exist.
        """
        original_path = path

        # Step 0: Block null bytes (can bypass C-level path operations)
        if "\x00" in path:
            raise WorkspaceSecurityError(
                f"Path contains null byte: {repr(path)}",
                path=path,
            )

        # Step 1: Resolve symlinks to get REAL path
        # This is CRITICAL for security - we must know the actual file location
        # We use non-strict resolution first to check workspace boundaries
        # even for paths that don't exist (potential traversal attacks)
        try:
            # Always resolve non-strictly first to check boundary
            resolved = Path(path).resolve(strict=False)
        except RuntimeError as e:
            # Circular symlink or too many levels
            raise WorkspaceSecurityError(
                f"Unable to resolve path (possible circular symlink): {path}",
                path=original_path,
            )

        # Check workspace boundary BEFORE checking existence
        # This prevents information leakage about path existence outside workspace
        if self._resolved_workspace is not None:
            try:
                resolved.relative_to(self._resolved_workspace)
            except ValueError:
                raise WorkspaceSecurityError(
                    f"Access denied: {path} (resolves to {resolved}) "
                    f"is outside workspace {self._resolved_workspace}",
                    path=original_path,
                    resolved_path=str(resolved),
                )

        # Now check if file exists (after confirming it's within workspace)
        if check_exists and not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Step 2: Check path depth
        if len(resolved.parts) > self.max_path_depth:
            raise WorkspaceSecurityError(
                f"Path exceeds maximum depth ({self.max_path_depth}): {path}",
                path=original_path,
                resolved_path=str(resolved),
            )

        # Step 3: Check denied patterns (unless in allowlist)
        resolved_str = str(resolved)
        filename = resolved.name

        # Check if explicitly allowed
        is_allowed = any(
            fnmatch.fnmatch(resolved_str, pattern)
            or fnmatch.fnmatch(filename, pattern)
            for pattern in self.allowed_patterns
        )

        if not is_allowed:
            for pattern in self.denied_patterns:
                if fnmatch.fnmatch(resolved_str, pattern) or fnmatch.fnmatch(
                    filename, pattern
                ):
                    raise WorkspaceSecurityError(
                        f"Access denied: {path} matches blocked pattern '{pattern}'",
                        path=original_path,
                        resolved_path=str(resolved),
                        pattern=pattern,
                    )

        # Step 4: Workspace boundary already checked above

        return resolved

    def validate_file_size(self, path: Path) -> None:
        """Validate file size is within limits.

        Args:
            path: Resolved path to check.

        Raises:
            WorkspaceSecurityError: If file exceeds size limit.
        """
        try:
            size = path.stat().st_size
            if size > self.max_file_size:
                size_mb = size / (1024 * 1024)
                max_mb = self.max_file_size / (1024 * 1024)
                raise WorkspaceSecurityError(
                    f"File too large: {path} is {size_mb:.1f}MB (max: {max_mb:.1f}MB)",
                    path=str(path),
                )
        except FileNotFoundError:
            pass  # File doesn't exist yet, skip size check

    def validate_content_size(self, content: str, operation: str = "write") -> None:
        """Validate that content is within size limits before writing.

        Args:
            content: The content to be written.
            operation: Description of the operation (for error messages).

        Raises:
            WorkspaceSecurityError: If content exceeds size limit.
        """
        size = len(content.encode("utf-8"))
        if size > self.max_file_size:
            size_mb = size / (1024 * 1024)
            max_mb = self.max_file_size / (1024 * 1024)
            raise WorkspaceSecurityError(
                f"Content too large for {operation}: {size_mb:.1f}MB "
                f"(max: {max_mb:.1f}MB)",
                path="<content>",
            )

    def is_binary_file(self, path: Path, sample_size: int = 8192) -> bool:
        """Check if a file appears to be binary.

        Detection uses two methods:
        1. Extension check (fast path)
        2. Content sampling via _utils.detect_binary()

        Args:
            path: Path to check.
            sample_size: Number of bytes to sample for content analysis.

        Returns:
            True if file appears to be binary.
        """
        # Fast path: check extension against our configured set
        suffix = path.suffix.lower()
        if suffix in self.binary_extensions:
            return True

        # Delegate content analysis to shared utility
        return _utils_detect_binary(path, sample_size)

    def is_media_file(self, path: Path) -> bool:
        """Check if file is an image or PDF.

        Media files can be read and returned as base64 attachments.
        Delegates to shared _utils.is_media_file() implementation.

        Args:
            path: Path to check.

        Returns:
            True if file is image/* (except SVG) or application/pdf.
        """
        return _utils_is_media_file(path)

    def mark_file_read(self, path: str | Path) -> None:
        """Mark a file as having been read in this session.

        This is used for read-before-edit tracking to prevent blind overwrites.

        Args:
            path: The resolved path that was read.
        """
        self._read_files.add(str(Path(path).resolve()))

    def check_read_before_edit(self, path: str | Path) -> bool:
        """Check if a file was read before attempting to edit.

        Args:
            path: The resolved path to check.

        Returns:
            True if the file was read in this session OR doesn't exist yet.
        """
        resolved = str(Path(path).resolve())
        # File was read, OR file doesn't exist (new file)
        return resolved in self._read_files or not Path(path).exists()

    def clear_read_tracking(self) -> None:
        """Clear the read-tracking set (e.g., for a new session)."""
        self._read_files.clear()


# Context variable for thread-safe global context
_security_context_var: contextvars.ContextVar[Optional[SecurityContext]] = (
    contextvars.ContextVar("security_context", default=None)
)


def set_security_context(ctx: SecurityContext) -> None:
    """Set the security context for the current async context.

    This uses contextvars for proper async/thread isolation.

    Args:
        ctx: The security context to use for all file operations.
    """
    _security_context_var.set(ctx)


def get_security_context(allow_permissive: bool = True) -> SecurityContext:
    """Get the current security context.

    Args:
        allow_permissive: If True (default), creates a permissive default context
            when none is set. If False, raises SecurityContextNotSetError.

            **Deprecation Warning**: The default value of True is deprecated.
            In a future version, this will default to False, requiring explicit
            context configuration. Set allow_permissive=True explicitly if you
            need the permissive behavior.

    Returns:
        The current security context.

    Raises:
        SecurityContextNotSetError: If no context is set and allow_permissive=False.

    Example:
        >>> # Strict mode - recommended for production
        >>> ctx = get_security_context(allow_permissive=False)
        SecurityContextNotSetError: No SecurityContext has been configured...

        >>> # Set up context first
        >>> set_security_context(SecurityContext(workspace="/project"))
        >>> ctx = get_security_context()  # Now works
    """
    ctx = _security_context_var.get()
    if ctx is None:
        if allow_permissive:
            import warnings

            warnings.warn(
                "No SecurityContext configured. Creating permissive default with no "
                "workspace restriction. This behavior is deprecated and will be removed "
                "in a future version. Please call set_security_context() with a workspace "
                "before using file tools.",
                DeprecationWarning,
                stacklevel=2,
            )
            ctx = SecurityContext()
            _security_context_var.set(ctx)
        else:
            raise SecurityContextNotSetError(
                "No SecurityContext has been configured. "
                "Call set_security_context() with a workspace before using file tools. "
                "Example: set_security_context(SecurityContext(workspace='/path/to/project'))"
            )
    return ctx


def validate_path(path: str, check_exists: bool = True) -> Path:
    """Convenience function to validate a path using the global context.

    Args:
        path: The path to validate.
        check_exists: Whether the file must exist.

    Returns:
        The resolved, validated Path.
    """
    return get_security_context().validate_path(path, check_exists)
