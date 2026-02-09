"""Error handling and audit logging for shell commands.

Provides:
- Structured error information (ShellError, ErrorSeverity)
- Error suggestions for common failures
- Audit logging for command execution and security events
- Retry logic with execute_with_recovery()
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


__all__ = [
    "ErrorSeverity",
    "ShellAuditLogger",
    "ShellError",
    "configure_audit_logging",
    "execute_with_recovery",
    "get_audit_logger",
    "suggest_fix",
]

logger = logging.getLogger("rawagents.shell")


class ErrorSeverity(Enum):
    """Severity levels for shell errors."""

    INFO = "info"  # Non-critical, command ran but had warnings
    WARNING = "warning"  # Command failed but recoverable
    ERROR = "error"  # Command failed, not recoverable
    SECURITY = "security"  # Security violation detected


@dataclass
class ShellError:
    """Structured error information from shell commands."""

    severity: ErrorSeverity
    message: str
    command: str
    exit_code: int | None = None
    stderr: str | None = None
    suggestion: str | None = None

    def to_user_message(self) -> str:
        """Format error for display to user/LLM."""
        parts = [f"Error: {self.message}"]

        if self.exit_code is not None:
            parts.append(f"Exit code: {self.exit_code}")

        if self.stderr:
            parts.append(f"Details: {self.stderr[:500]}")  # Truncate

        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")

        return "\n".join(parts)


# Error suggestions for common failures
ERROR_SUGGESTIONS: dict[str, str] = {
    "command not found": "Check if the command is installed and in PATH",
    "permission denied": "Check file permissions or try a different directory",
    "no such file or directory": "Verify the path exists",
    "disk quota exceeded": "Free up disk space",
    "cannot allocate memory": "Close other applications or increase memory",
    "connection refused": "Check if the service is running",
    "timeout": "Try increasing the timeout or running in background",
}


def suggest_fix(stderr: str) -> str | None:
    """Suggest a fix based on error output."""
    stderr_lower = stderr.lower()
    for pattern, suggestion in ERROR_SUGGESTIONS.items():
        if pattern in stderr_lower:
            return suggestion
    return None


class ShellAuditLogger:
    """Audit logger for shell command execution.

    Logs all command executions with:
    - Timestamp
    - Command executed
    - Working directory
    - Exit code and result summary
    - Security events (blocked commands)
    """

    def __init__(
        self,
        log_file: Path | None = None,
        log_level: int = logging.INFO,
    ):
        self.logger = logging.getLogger("rawagents.shell.audit")
        self.logger.setLevel(log_level)

        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(handler)

    def log_execution(
        self,
        command: str,
        working_dir: str,
        exit_code: int | None,
        duration_ms: float,
        truncated: bool = False,
    ) -> None:
        """Log a command execution."""
        entry = {
            "event": "command_executed",
            "timestamp": datetime.now().isoformat(),
            "command": command[:200],
            "working_dir": working_dir,
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "truncated": truncated,
        }
        self.logger.info(json.dumps(entry))

    def log_security_event(
        self,
        command: str,
        reason: str,
        pattern: str | None = None,
    ) -> None:
        """Log a security event (blocked command, etc.)."""
        entry = {
            "event": "security_blocked",
            "timestamp": datetime.now().isoformat(),
            "command": command[:200],
            "reason": reason,
            "pattern": pattern,
        }
        self.logger.warning(json.dumps(entry))

    def log_background_process(
        self,
        pid: str,
        command: str,
        action: str,  # "started", "output_read", "killed"
    ) -> None:
        """Log background process lifecycle events."""
        entry = {
            "event": f"background_{action}",
            "timestamp": datetime.now().isoformat(),
            "pid": pid,
            "command": command[:200],
        }
        self.logger.info(json.dumps(entry))


# Global audit logger instance
_audit_logger: ShellAuditLogger | None = None


def configure_audit_logging(
    log_file: Path | None = None,
    log_level: int = logging.INFO,
) -> None:
    """Configure the global audit logger.

    Example:
        >>> configure_audit_logging(
        ...     log_file=Path("~/.rawagents/shell_audit.log").expanduser(),
        ...     log_level=logging.DEBUG,
        ... )
    """
    global _audit_logger  # noqa: PLW0603
    _audit_logger = ShellAuditLogger(log_file, log_level)


def get_audit_logger() -> ShellAuditLogger | None:
    """Get the global audit logger."""
    return _audit_logger


async def execute_with_recovery(
    command: str,
    max_retries: int = 0,
    retry_delay: float = 1.0,
) -> tuple[str, ShellError | None]:
    """Execute command with optional retry logic.

    Args:
        command: The shell command to execute.
        max_retries: Maximum retry attempts (0 = no retry).
        retry_delay: Delay between retries in seconds.

    Returns:
        Tuple of (output, error). Error is None on success.

    Example:
        >>> output, error = await execute_with_recovery(
        ...     "git fetch origin",
        ...     max_retries=2,
        ... )
        >>> if error:
        ...     print(error.to_user_message())
    """
    # Lazy import to avoid circular import (bash imports from _errors via audit)
    from rawagents.tools.builtin.shell.bash import bash  # noqa: PLC0415

    last_error: ShellError | None = None

    for attempt in range(max_retries + 1):
        try:
            result = await bash(command)

            if not result.startswith("Error:"):
                return result, None

            last_error = ShellError(
                severity=ErrorSeverity.ERROR,
                message=result,
                command=command,
                suggestion=suggest_fix(result),
            )

            # Some errors are not retryable
            if "permission denied" in result.lower():
                break
            if "command not found" in result.lower():
                break

        except Exception as e:
            last_error = ShellError(
                severity=ErrorSeverity.ERROR,
                message=str(e),
                command=command,
            )

        if attempt < max_retries:
            logger.info(f"Retrying command (attempt {attempt + 2}): {command}")
            await asyncio.sleep(retry_delay)

    return "", last_error
