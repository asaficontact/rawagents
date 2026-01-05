"""Shared fixtures for prompt tests."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from rawagents.prompts import PromptManager


class SampleUser(BaseModel):
    """Sample Pydantic model for testing."""

    id: int
    name: str


class SampleConfig(BaseModel):
    """Nested Pydantic model for testing."""

    user: SampleUser
    settings: dict[str, str]


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    """Create a temporary template directory with test templates."""
    # Create subdirectory for organization tests
    (tmp_path / "agents").mkdir()

    # Simple template
    (tmp_path / "simple.j2").write_text("Hello, {{ name }}!")

    # Template with logic
    (tmp_path / "with_logic.j2").write_text(
        "{% if show %}Visible{% else %}Hidden{% endif %}"
    )

    # Template with loop
    (tmp_path / "with_loop.j2").write_text(
        "{% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}"
    )

    # Template with to_json filter
    (tmp_path / "with_filter.j2").write_text("Data: {{ data | to_json }}")

    # Template with indented to_json filter
    (tmp_path / "with_indent.j2").write_text("Data:\n{{ data | to_json(indent=2) }}")

    # Template for include testing
    (tmp_path / "partial.j2").write_text("Partial content")
    (tmp_path / "with_include.j2").write_text(
        "Before {% include 'partial.j2' %} After"
    )

    # Template for extends testing
    (tmp_path / "base.j2").write_text("Base: {% block content %}{% endblock %}")
    (tmp_path / "child.j2").write_text(
        "{% extends 'base.j2' %}{% block content %}Child{% endblock %}"
    )

    # Agent template in subdirectory
    (tmp_path / "agents" / "coder.j2").write_text(
        "You are a coder. Tools: {{ tools | to_json }}"
    )

    # Template with trailing newline
    (tmp_path / "with_newline.j2").write_text("Content\n")

    # Template with multiple variables
    (tmp_path / "multi_var.j2").write_text(
        "Hello {{ name }}, you are {{ age }} years old."
    )

    # Template with nested variable access
    (tmp_path / "nested.j2").write_text("User: {{ user.name }} (ID: {{ user.id }})")

    # Template that uses custom filter
    (tmp_path / "custom_filter.j2").write_text("Result: {{ value | custom }}")

    return tmp_path


@pytest.fixture
def manager(template_dir: Path) -> PromptManager:
    """Create a PromptManager instance."""
    return PromptManager(template_dir)


@pytest.fixture
def sample_user() -> SampleUser:
    """Create a sample Pydantic model for testing."""
    return SampleUser(id=1, name="Alice")


@pytest.fixture
def sample_config(sample_user: SampleUser) -> SampleConfig:
    """Create a nested Pydantic model for testing."""
    return SampleConfig(user=sample_user, settings={"theme": "dark", "lang": "en"})
