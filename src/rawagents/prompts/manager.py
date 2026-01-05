"""PromptManager for loading and rendering Jinja2 prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
from jinja2.exceptions import SecurityError, TemplateSyntaxError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from rawagents.prompts.exceptions import (
    PromptRenderingError,
    TemplateConfigError,
    TemplateNotFoundError,
)
from rawagents.prompts.filters import get_default_filters

__all__ = ["PromptManager"]


class PromptManager:
    """Manages loading and rendering of Jinja2 prompt templates.

    A lightweight, stateless rendering engine that transforms templates
    and runtime data into strings for the LLM. Uses SandboxedEnvironment
    by default for security.

    Features:
        - Jinja2 templating with logic (if, for), macros, inheritance
        - Strict validation (missing variables raise errors)
        - Custom filters (to_json for Pydantic models)
        - Sandboxed execution (blocks arbitrary code)
        - Path traversal protection

    Example:
        >>> manager = PromptManager("./prompts")
        >>> prompt = manager.render(
        ...     "agent.j2",
        ...     tools=executor.get_schemas(),
        ...     user=user_obj,
        ... )

    Template example (prompts/agent.j2):
        You are an expert assistant.

        ## Available Tools
        {{ tools | to_json(indent=2) }}

        ## User Context
        User ID: {{ user.id }}
        {% if user.preferences %}
        Preferences: {{ user.preferences | to_json }}
        {% endif %}
    """

    def __init__(
        self,
        template_dir: str | Path,
        file_extension: str = ".j2",
        *,
        sandbox: bool = True,
    ) -> None:
        """Initialize the PromptManager.

        Args:
            template_dir: Root directory for templates.
            file_extension: Default file extension (for documentation).
            sandbox: If True (default), use SandboxedEnvironment to block
                arbitrary code execution. Set to False only if you fully
                trust all templates.

        Raises:
            TemplateConfigError: If template_dir doesn't exist or isn't a directory.
        """
        # Convert and resolve path
        self._template_dir = Path(template_dir).resolve()
        self._file_extension = file_extension
        self._sandbox = sandbox

        # Fail-fast validation
        if not self._template_dir.exists():
            raise TemplateConfigError(
                f"Template directory does not exist: {self._template_dir}"
            )

        if not self._template_dir.is_dir():
            raise TemplateConfigError(
                f"Template path is not a directory: {self._template_dir}"
            )

        # Create Jinja2 environment
        env_class: type[Environment] = SandboxedEnvironment if sandbox else Environment
        self._env = env_class(
            loader=FileSystemLoader(self._template_dir),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

        # Register default filters
        self._env.filters.update(get_default_filters())

    def render(self, template_name: str, **kwargs: Any) -> str:
        """Render a template with the given variables.

        Args:
            template_name: Relative path to template (e.g., "agents/coder.j2").
            **kwargs: Variables to inject into the template.

        Returns:
            Rendered string.

        Raises:
            TemplateNotFoundError: If template file doesn't exist.
            PromptRenderingError: If rendering fails (missing variable,
                syntax error, security violation).
        """
        # Validate template name
        if not template_name or not template_name.strip():
            raise PromptRenderingError(
                "Template name cannot be empty",
                template_name=template_name,
            )

        # Path traversal protection
        self._validate_template_path(template_name)

        # Load template
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as e:
            raise TemplateNotFoundError(
                template_name=template_name,
                template_dir=self._template_dir,
                original_error=e,
            ) from e

        # Render template
        try:
            return template.render(**kwargs)
        except UndefinedError as e:
            raise PromptRenderingError(
                f"Missing variable in template '{template_name}': {e}",
                template_name=template_name,
                original_error=e,
                context={"provided_variables": list(kwargs.keys())},
            ) from e
        except TemplateSyntaxError as e:
            raise PromptRenderingError(
                f"Syntax error in template '{template_name}' at line {e.lineno}: {e.message}",
                template_name=template_name,
                original_error=e,
            ) from e
        except SecurityError as e:
            raise PromptRenderingError(
                f"Security violation in template '{template_name}': {e}. "
                f"If intentional, use sandbox=False.",
                template_name=template_name,
                original_error=e,
            ) from e
        except Exception as e:
            raise PromptRenderingError(
                f"Error rendering template '{template_name}': {e}",
                template_name=template_name,
                original_error=e,
            ) from e

    def add_filter(self, name: str, func: Callable[..., Any]) -> None:
        """Register a custom filter at runtime.

        Args:
            name: Filter name for use in templates.
            func: Filter function (first arg is the value being filtered).

        Example:
            >>> manager.add_filter("upper", str.upper)
            >>> # In template: {{ name | upper }}
        """
        self._env.filters[name] = func

    def _validate_template_path(self, template_name: str) -> None:
        """Validate template name doesn't escape template directory.

        Raises:
            PromptRenderingError: If path traversal is detected.
        """
        # Normalize both forward slashes and backslashes for cross-platform safety
        normalized = template_name.replace("\\", "/")

        # Check for path traversal patterns
        if ".." in normalized.split("/"):
            raise PromptRenderingError(
                f"Path traversal detected in template name: '{template_name}'",
                template_name=template_name,
            )

        # Check for absolute paths (Unix-style or Windows-style)
        if Path(template_name).is_absolute() or (
            len(template_name) > 1 and template_name[1] == ":"
        ):
            raise PromptRenderingError(
                f"Absolute paths not allowed: '{template_name}'",
                template_name=template_name,
            )

    @property
    def template_dir(self) -> Path:
        """Get the template directory path."""
        return self._template_dir
