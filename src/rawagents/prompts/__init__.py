"""PromptManager - The presentation layer for agents.

The PromptManager is a lightweight, stateless rendering engine that transforms
Jinja2 templates and runtime data into the strings required by the LLMClient.

Features:
    - Jinja2-based templating with logic, macros, and inheritance
    - Strict validation (fail fast on missing variables)
    - Custom filters for common LLM needs (to_json for Pydantic models)
    - Sandboxed execution for security (blocks arbitrary code)

Example:
    >>> from rawagents.prompts import PromptManager
    >>>
    >>> manager = PromptManager("./prompts")
    >>> prompt = manager.render(
    ...     "agent.j2",
    ...     tools=executor.get_schemas(),
    ...     user=user_obj,
    ... )

Template Example (prompts/agent.j2):
    You are an expert assistant.

    ## Available Tools
    {{ tools | to_json(indent=2) }}

    ## Task
    {{ task_description }}
"""

from rawagents.prompts.exceptions import (
    PromptError,
    PromptRenderingError,
    TemplateConfigError,
    TemplateNotFoundError,
)
from rawagents.prompts.filters import to_json
from rawagents.prompts.manager import PromptManager

__all__ = [
    "PromptManager",
    "PromptError",
    "TemplateConfigError",
    "TemplateNotFoundError",
    "PromptRenderingError",
    "to_json",
]
