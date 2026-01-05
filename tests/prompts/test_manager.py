"""Tests for PromptManager."""

from pathlib import Path

import pytest

from rawagents.prompts import (
    PromptManager,
    PromptRenderingError,
    TemplateConfigError,
    TemplateNotFoundError,
)


class TestPromptManagerInit:
    """Tests for PromptManager initialization."""

    def test_init_with_string_path(self, template_dir: Path) -> None:
        """PromptManager initializes with string path."""
        manager = PromptManager(str(template_dir))
        assert manager.template_dir == template_dir

    def test_init_with_path_object(self, template_dir: Path) -> None:
        """PromptManager initializes with Path object."""
        manager = PromptManager(template_dir)
        assert manager.template_dir == template_dir

    def test_nonexistent_directory_raises_config_error(self) -> None:
        """Non-existent directory raises TemplateConfigError at init."""
        with pytest.raises(TemplateConfigError, match="does not exist"):
            PromptManager("/nonexistent/path/to/templates")

    def test_file_as_directory_raises_config_error(self, tmp_path: Path) -> None:
        """File path (not directory) raises TemplateConfigError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        with pytest.raises(TemplateConfigError, match="not a directory"):
            PromptManager(file_path)

    def test_sandbox_enabled_by_default(self, template_dir: Path) -> None:
        """Sandbox is enabled by default."""
        manager = PromptManager(template_dir)
        assert manager._sandbox is True

    def test_sandbox_can_be_disabled(self, template_dir: Path) -> None:
        """Sandbox can be disabled explicitly."""
        manager = PromptManager(template_dir, sandbox=False)
        assert manager._sandbox is False

    def test_file_extension_stored(self, template_dir: Path) -> None:
        """File extension is stored."""
        manager = PromptManager(template_dir, file_extension=".jinja2")
        assert manager._file_extension == ".jinja2"


class TestPromptManagerRender:
    """Tests for template rendering."""

    def test_render_simple_template(self, manager: PromptManager) -> None:
        """Simple template renders correctly."""
        result = manager.render("simple.j2", name="World")
        assert result == "Hello, World!"

    def test_render_with_variables(self, manager: PromptManager) -> None:
        """Template with multiple variables renders correctly."""
        result = manager.render("multi_var.j2", name="Bob", age=30)
        assert result == "Hello Bob, you are 30 years old."

    def test_render_with_if_logic(self, manager: PromptManager) -> None:
        """Template with if logic renders correctly."""
        assert manager.render("with_logic.j2", show=True) == "Visible"
        assert manager.render("with_logic.j2", show=False) == "Hidden"

    def test_render_with_for_loop(self, manager: PromptManager) -> None:
        """Template with for loop renders correctly."""
        result = manager.render("with_loop.j2", items=["a", "b", "c"])
        assert result == "a, b, c"

    def test_render_with_include(self, manager: PromptManager) -> None:
        """Template with include renders correctly."""
        result = manager.render("with_include.j2")
        assert result == "Before Partial content After"

    def test_render_with_extends(self, manager: PromptManager) -> None:
        """Template with extends renders correctly."""
        result = manager.render("child.j2")
        assert result == "Base: Child"

    def test_render_preserves_trailing_newline(self, manager: PromptManager) -> None:
        """Trailing newlines are preserved."""
        result = manager.render("with_newline.j2")
        assert result.endswith("\n")

    def test_render_template_in_subdirectory(self, manager: PromptManager) -> None:
        """Templates in subdirectories render correctly."""
        result = manager.render("agents/coder.j2", tools=[{"name": "search"}])
        assert "You are a coder" in result
        assert "search" in result

    def test_render_nested_variable_access(
        self, manager: PromptManager, sample_user: "SampleUser"
    ) -> None:
        """Nested variable access works correctly."""
        result = manager.render("nested.j2", user=sample_user)
        assert "Alice" in result
        assert "(ID: 1)" in result


class TestPromptManagerErrors:
    """Tests for error conditions."""

    def test_template_not_found_raises_error(self, manager: PromptManager) -> None:
        """Missing template raises TemplateNotFoundError."""
        with pytest.raises(TemplateNotFoundError) as exc_info:
            manager.render("nonexistent.j2")
        assert exc_info.value.template_name == "nonexistent.j2"
        assert exc_info.value.template_dir is not None

    def test_missing_variable_raises_error(self, manager: PromptManager) -> None:
        """Missing variable raises PromptRenderingError."""
        with pytest.raises(PromptRenderingError, match="Missing variable"):
            manager.render("simple.j2")  # 'name' not provided

    def test_missing_variable_error_includes_provided_vars(
        self, manager: PromptManager
    ) -> None:
        """Error includes list of provided variables."""
        with pytest.raises(PromptRenderingError) as exc_info:
            manager.render("multi_var.j2", name="Bob")  # 'age' missing
        assert "provided_variables" in exc_info.value.context
        assert "name" in exc_info.value.context["provided_variables"]

    def test_empty_template_name_raises_error(self, manager: PromptManager) -> None:
        """Empty template name raises PromptRenderingError."""
        with pytest.raises(PromptRenderingError, match="cannot be empty"):
            manager.render("")

    def test_whitespace_only_template_name_raises_error(
        self, manager: PromptManager
    ) -> None:
        """Whitespace-only template name raises error."""
        with pytest.raises(PromptRenderingError, match="cannot be empty"):
            manager.render("   ")

    def test_original_error_preserved(self, manager: PromptManager) -> None:
        """Original Jinja2 error is preserved in exception."""
        with pytest.raises(TemplateNotFoundError) as exc_info:
            manager.render("nonexistent.j2")
        assert exc_info.value.original_error is not None


class TestPromptManagerFilters:
    """Tests for custom filter support."""

    def test_to_json_filter_available(self, manager: PromptManager) -> None:
        """to_json filter is available by default."""
        result = manager.render("with_filter.j2", data={"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_add_filter_at_runtime(
        self, manager: PromptManager, template_dir: Path
    ) -> None:
        """Custom filter can be added at runtime."""
        manager.add_filter("custom", lambda x: f"[{x}]")
        result = manager.render("custom_filter.j2", value="test")
        assert result == "Result: [test]"

    def test_custom_filter_overrides_default(self, manager: PromptManager) -> None:
        """Custom filter can override default filter."""

        def custom_to_json(value: object, indent: int | None = None) -> str:
            return "CUSTOM"

        manager.add_filter("to_json", custom_to_json)
        result = manager.render("with_filter.j2", data={"key": "value"})
        assert result == "Data: CUSTOM"


# Import for type hints
from tests.prompts.conftest import SampleUser
