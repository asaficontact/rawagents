"""Custom exceptions for the PromptManager component."""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "PromptError",
    "TemplateConfigError",
    "TemplateNotFoundError",
    "PromptRenderingError",
]


class PromptError(Exception):
    """Base exception for all prompt-related errors."""

    pass


class TemplateConfigError(PromptError):
    """Raised when PromptManager is incorrectly configured.

    This is a developer error caught at initialization time (fail fast).
    Examples: template directory doesn't exist, invalid file extension.
    """

    pass


class TemplateNotFoundError(PromptError):
    """Raised when a template file cannot be found.

    Attributes:
        template_name: The requested template name.
        template_dir: The directory that was searched.
        original_error: The original Jinja2 exception if available.
    """

    def __init__(
        self,
        template_name: str,
        template_dir: Path | str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        self.template_name = template_name
        self.template_dir = template_dir
        self.original_error = original_error
        message = f"Template '{template_name}' not found"
        if template_dir:
            message += f" in '{template_dir}'"
        super().__init__(message)


class PromptRenderingError(PromptError):
    """Raised when template rendering fails.

    Catches missing variables, syntax errors, security violations, etc.

    Attributes:
        template_name: Name of the template that failed.
        original_error: The original exception if available.
        context: Additional context for debugging.
    """

    def __init__(
        self,
        message: str,
        template_name: str | None = None,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.template_name = template_name
        self.original_error = original_error
        self.context = context or {}
