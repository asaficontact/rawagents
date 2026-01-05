"""Security and edge case tests for PromptManager."""

from pathlib import Path

import pytest

from rawagents.prompts import PromptManager, PromptRenderingError


class TestPromptManagerSecurity:
    """Security-focused tests."""

    def test_path_traversal_blocked(self, manager: PromptManager) -> None:
        """Path traversal attempts are blocked."""
        with pytest.raises(PromptRenderingError, match="Path traversal"):
            manager.render("../../../etc/passwd")

    def test_path_traversal_middle_blocked(self, manager: PromptManager) -> None:
        """Path traversal in middle of path is blocked."""
        with pytest.raises(PromptRenderingError, match="Path traversal"):
            manager.render("agents/../../../etc/passwd")

    def test_path_traversal_windows_style_blocked(self, manager: PromptManager) -> None:
        """Windows-style path traversal is blocked."""
        with pytest.raises(PromptRenderingError, match="Path traversal"):
            manager.render("..\\..\\secrets.j2")

    def test_absolute_path_unix_blocked(self, manager: PromptManager) -> None:
        """Unix absolute paths are blocked."""
        with pytest.raises(PromptRenderingError, match="Absolute paths"):
            manager.render("/etc/passwd")

    def test_sandbox_blocks_dunder_class(self, tmp_path: Path) -> None:
        """Sandbox blocks __class__ access."""
        (tmp_path / "evil.j2").write_text("{{ ''.__class__ }}")
        manager = PromptManager(tmp_path)
        with pytest.raises(PromptRenderingError, match="Security violation"):
            manager.render("evil.j2")

    def test_sandbox_blocks_dunder_mro(self, tmp_path: Path) -> None:
        """Sandbox blocks __mro__ access."""
        (tmp_path / "evil.j2").write_text("{{ ''.__class__.__mro__ }}")
        manager = PromptManager(tmp_path)
        with pytest.raises(PromptRenderingError, match="Security violation"):
            manager.render("evil.j2")

    def test_sandbox_blocks_getattr(self, tmp_path: Path) -> None:
        """Sandbox blocks potentially dangerous getattr patterns."""
        # This tries to access internal attributes
        (tmp_path / "evil.j2").write_text("{{ ''.__class__.__bases__ }}")
        manager = PromptManager(tmp_path)
        with pytest.raises(PromptRenderingError, match="Security violation"):
            manager.render("evil.j2")

    def test_non_sandboxed_mode_allows_dunder_access(self, tmp_path: Path) -> None:
        """Non-sandboxed mode allows dunder access (use with caution)."""
        (tmp_path / "meta.j2").write_text("{{ ''.__class__.__name__ }}")
        manager = PromptManager(tmp_path, sandbox=False)
        result = manager.render("meta.j2")
        assert "str" in result

    def test_sandbox_hint_in_security_error(self, tmp_path: Path) -> None:
        """Security error message includes hint about sandbox=False."""
        (tmp_path / "evil.j2").write_text("{{ ''.__class__ }}")
        manager = PromptManager(tmp_path)
        with pytest.raises(PromptRenderingError, match="sandbox=False"):
            manager.render("evil.j2")


class TestPromptManagerEdgeCases:
    """Edge case tests."""

    def test_unicode_in_template_name(self, tmp_path: Path) -> None:
        """Unicode characters in template names work."""
        (tmp_path / "grüß_gott.j2").write_text("Grüß Gott, {{ name }}!")
        manager = PromptManager(tmp_path)
        result = manager.render("grüß_gott.j2", name="Welt")
        assert "Grüß Gott, Welt!" in result

    def test_unicode_in_variables(self, manager: PromptManager) -> None:
        """Unicode characters in variables render correctly."""
        result = manager.render("simple.j2", name="世界")
        assert result == "Hello, 世界!"

    def test_emoji_in_variables(self, manager: PromptManager) -> None:
        """Emoji in variables render correctly."""
        result = manager.render("simple.j2", name="🌍")
        assert result == "Hello, 🌍!"

    def test_large_context_renders(self, manager: PromptManager) -> None:
        """Large context dictionaries render successfully."""
        large_data = {f"key_{i}": f"value_{i}" for i in range(10000)}
        result = manager.render("with_filter.j2", data=large_data)
        assert "key_9999" in result

    def test_deeply_nested_includes(self, tmp_path: Path) -> None:
        """Deeply nested includes work without stack overflow."""
        (tmp_path / "a.j2").write_text("A{% include 'b.j2' %}")
        (tmp_path / "b.j2").write_text("B{% include 'c.j2' %}")
        (tmp_path / "c.j2").write_text("C{% include 'd.j2' %}")
        (tmp_path / "d.j2").write_text("D")
        manager = PromptManager(tmp_path)
        result = manager.render("a.j2")
        assert result == "ABCD"

    def test_empty_template_renders(self, tmp_path: Path) -> None:
        """Empty template renders to empty string."""
        (tmp_path / "empty.j2").write_text("")
        manager = PromptManager(tmp_path)
        result = manager.render("empty.j2")
        assert result == ""

    def test_template_with_only_whitespace(self, tmp_path: Path) -> None:
        """Template with only whitespace renders whitespace."""
        (tmp_path / "whitespace.j2").write_text("   \n\t  ")
        manager = PromptManager(tmp_path)
        result = manager.render("whitespace.j2")
        assert result == "   \n\t  "

    def test_template_with_special_characters(self, tmp_path: Path) -> None:
        """Template with special characters renders correctly."""
        (tmp_path / "special.j2").write_text('Special: {{ text | e }}')
        manager = PromptManager(tmp_path)
        result = manager.render("special.j2", text="<script>alert('xss')</script>")
        # Note: autoescape is False, so HTML is NOT escaped by default
        # The | e filter explicitly escapes
        assert "&lt;script&gt;" in result

    def test_multiline_template(self, tmp_path: Path) -> None:
        """Multiline template renders correctly."""
        template = """Line 1: {{ var1 }}
Line 2: {{ var2 }}
Line 3: {{ var3 }}
"""
        (tmp_path / "multiline.j2").write_text(template)
        manager = PromptManager(tmp_path)
        result = manager.render("multiline.j2", var1="a", var2="b", var3="c")
        assert "Line 1: a" in result
        assert "Line 2: b" in result
        assert "Line 3: c" in result

    def test_template_with_comments(self, tmp_path: Path) -> None:
        """Jinja2 comments are properly handled."""
        (tmp_path / "comments.j2").write_text(
            "{# This is a comment #}Hello{{ name }}"
        )
        manager = PromptManager(tmp_path)
        result = manager.render("comments.j2", name="World")
        assert result == "HelloWorld"
        assert "comment" not in result

    def test_template_dir_property(self, manager: PromptManager) -> None:
        """template_dir property returns correct path."""
        assert manager.template_dir.is_dir()
        assert manager.template_dir.exists()


class TestPromptManagerExceptionAttributes:
    """Tests for exception attributes."""

    def test_template_not_found_has_template_name(
        self, manager: PromptManager
    ) -> None:
        """TemplateNotFoundError has template_name attribute."""
        with pytest.raises(Exception) as exc_info:
            manager.render("missing.j2")
        from rawagents.prompts import TemplateNotFoundError

        assert isinstance(exc_info.value, TemplateNotFoundError)
        assert exc_info.value.template_name == "missing.j2"

    def test_template_not_found_has_template_dir(
        self, manager: PromptManager
    ) -> None:
        """TemplateNotFoundError has template_dir attribute."""
        with pytest.raises(Exception) as exc_info:
            manager.render("missing.j2")
        from rawagents.prompts import TemplateNotFoundError

        assert isinstance(exc_info.value, TemplateNotFoundError)
        assert exc_info.value.template_dir == manager.template_dir

    def test_rendering_error_has_template_name(self, manager: PromptManager) -> None:
        """PromptRenderingError has template_name attribute."""
        with pytest.raises(PromptRenderingError) as exc_info:
            manager.render("simple.j2")  # Missing 'name'
        assert exc_info.value.template_name == "simple.j2"

    def test_rendering_error_has_context(self, manager: PromptManager) -> None:
        """PromptRenderingError has context attribute."""
        with pytest.raises(PromptRenderingError) as exc_info:
            manager.render("multi_var.j2", name="Bob")  # Missing 'age'
        assert "provided_variables" in exc_info.value.context

    def test_rendering_error_has_original_error(self, manager: PromptManager) -> None:
        """PromptRenderingError has original_error attribute."""
        with pytest.raises(PromptRenderingError) as exc_info:
            manager.render("simple.j2")  # Missing 'name'
        assert exc_info.value.original_error is not None
