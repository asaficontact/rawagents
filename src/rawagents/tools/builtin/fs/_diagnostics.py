"""Diagnostics provider protocol for post-edit feedback.

Defines a pluggable protocol that users can implement to integrate
their preferred diagnostics source (LSP client, linter subprocess, etc.)
into the file editing workflow.

The ``DiagnosticsProvider`` protocol and ``Diagnostic`` dataclass are
intentionally minimal — they define the interface without coupling
to any specific LSP library or linter.

Example:
    >>> class RuffProvider:
    ...     async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
    ...         # Run ruff, parse JSON output, return Diagnostic objects
    ...         ...
    >>>
    >>> ctx = SecurityContext(diagnostics_provider=RuffProvider())
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "DiagnosticsProvider",
]


class DiagnosticSeverity(Enum):
    """Severity levels for diagnostics, matching LSP conventions."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass
class Diagnostic:
    """A single diagnostic message (error, warning, etc.).

    Attributes:
        file_path: Absolute path to the file.
        line: 1-based line number.
        column: 1-based column number.
        severity: The severity level.
        message: Human-readable diagnostic message.
        source: The tool that produced this diagnostic (e.g., "pyright", "ruff").
        code: Optional error/warning code (e.g., "E501", "F841").
    """

    file_path: str
    line: int
    column: int
    severity: DiagnosticSeverity
    message: str
    source: str
    code: str = ""


@runtime_checkable
class DiagnosticsProvider(Protocol):
    """Protocol for pluggable diagnostics backends.

    Users implement this Protocol to integrate their preferred
    diagnostics source (LSP client, linter subprocess, etc.).

    The provider is stored on ``SecurityContext.diagnostics_provider``
    and can be queried by agent loops after edit/write operations.
    The tools themselves do NOT auto-invoke the provider — this is
    an agent-loop concern.

    Example:
        >>> class RuffDiagnosticsProvider:
        ...     async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        ...         import asyncio, json
        ...         proc = await asyncio.create_subprocess_exec(
        ...             "ruff", "check", "--output-format=json", file_path,
        ...             stdout=asyncio.subprocess.PIPE,
        ...         )
        ...         stdout, _ = await proc.communicate()
        ...         if not stdout:
        ...             return []
        ...         return [
        ...             Diagnostic(
        ...                 file_path=file_path,
        ...                 line=item["location"]["row"],
        ...                 column=item["location"]["column"],
        ...                 severity=DiagnosticSeverity.WARNING,
        ...                 message=item["message"],
        ...                 source="ruff",
        ...                 code=item.get("code", ""),
        ...             )
        ...             for item in json.loads(stdout)
        ...         ]
    """

    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Get diagnostics for a file.

        Args:
            file_path: Absolute path to the file.

        Returns:
            List of diagnostics (errors, warnings, etc.).
        """
        ...
