"""Security tests for file system tools.

These tests verify that the security module properly prevents:
1. Path traversal attacks via ../
2. Symlink escape attacks
3. Access to sensitive files
4. Operations outside workspace
5. Resource limit enforcement
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from rawagents.tools.builtin.fs._security import (
    SecurityContext,
    WorkspaceSecurityError,
    get_security_context,
    set_security_context,
    validate_path,
)


class TestPathTraversal:
    """Test protection against ../ path traversal."""

    def test_blocks_parent_directory_escape(self, temp_workspace: Path) -> None:
        """Attempting to escape workspace with ../ should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(temp_workspace / ".." / "etc" / "passwd"))

        assert "outside workspace" in str(exc.value)

    def test_blocks_absolute_path_outside(self, temp_workspace: Path) -> None:
        """Absolute paths outside workspace should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError):
            validate_path("/etc/passwd")

    def test_blocks_double_dot_in_middle(self, temp_workspace: Path) -> None:
        """../ in the middle of path should be blocked if it escapes."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create a subdir
        subdir = temp_workspace / "subdir"
        subdir.mkdir(exist_ok=True)

        # This path would escape: subdir/../../etc/passwd
        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(subdir / ".." / ".." / "etc" / "passwd"))

    def test_allows_safe_dotdot_within_workspace(self, temp_workspace: Path) -> None:
        """../ that stays within workspace should be allowed."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create nested structure
        subdir = temp_workspace / "subdir"
        subdir.mkdir(exist_ok=True)

        # test.py is in temp_workspace
        # subdir/../test.py resolves to temp_workspace/test.py (still inside)
        result = validate_path(str(subdir / ".." / "test.py"))
        assert result.name == "test.py"


class TestSymlinkEscape:
    """Test protection against symlink attacks."""

    def test_blocks_symlink_pointing_outside(
        self, temp_workspace: Path, symlink_outside: Path | None
    ) -> None:
        """Symlinks pointing outside workspace should be blocked."""
        if symlink_outside is None:
            pytest.skip("Symlinks not supported on this system")

        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(symlink_outside))

        assert "outside workspace" in str(exc.value)
        # Should show the resolved path in error
        assert "/etc/passwd" in str(exc.value) or "resolves to" in str(exc.value)

    def test_blocks_chained_symlinks(self, temp_workspace: Path) -> None:
        """Chained symlinks that eventually escape should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create chain: link1 -> link2 -> /etc/passwd
        with tempfile.TemporaryDirectory() as outside:
            try:
                outside_link = Path(outside) / "link2"
                outside_link.symlink_to("/etc/passwd")

                inside_link = temp_workspace / "link1"
                inside_link.symlink_to(outside_link)

                with pytest.raises(WorkspaceSecurityError):
                    validate_path(str(inside_link))
            except (OSError, NotImplementedError):
                pytest.skip("Symlinks not supported on this system")

    def test_allows_symlink_within_workspace(self, temp_workspace: Path) -> None:
        """Symlinks that stay within workspace should be allowed."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        try:
            # Create symlink to a file within workspace
            link = temp_workspace / "link_to_test"
            target = temp_workspace / "test.py"
            link.symlink_to(target)

            result = validate_path(str(link))
            assert result.exists()
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this system")


class TestDeniedPatterns:
    """Test protection of sensitive files."""

    @pytest.mark.parametrize(
        "filename",
        [
            ".env",
            ".env.local",
            ".env.production",
            "credentials.json",
            "secrets.yaml",
            "id_rsa",
            "server.key",
            "password.txt",
            "tokens.json",
        ],
    )
    def test_blocks_sensitive_files(
        self, temp_workspace: Path, filename: str
    ) -> None:
        """Sensitive file patterns should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create the sensitive file
        sensitive_file = temp_workspace / filename
        sensitive_file.parent.mkdir(parents=True, exist_ok=True)
        sensitive_file.write_text("secret content")

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(sensitive_file))

        assert "blocked pattern" in str(exc.value)

    def test_blocks_nested_sensitive_files(self, temp_workspace: Path) -> None:
        """Sensitive files in subdirectories should also be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        # Create nested .env
        config_dir = temp_workspace / "config"
        config_dir.mkdir()
        env_file = config_dir / ".env"
        env_file.write_text("SECRET=value")

        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(env_file))

    def test_allowlist_overrides_denylist(self, temp_workspace: Path) -> None:
        """Explicitly allowed patterns should override denied patterns."""
        ctx = SecurityContext(
            workspace=str(temp_workspace),
            denied_patterns=["*.env", "*.env.*"],
            allowed_patterns=["*.env.example", ".env.example"],
        )
        set_security_context(ctx)

        example_file = temp_workspace / ".env.example"
        example_file.write_text("# Example config\nKEY=placeholder")

        # Should NOT raise
        result = validate_path(str(example_file))
        assert result == example_file.resolve()

    def test_custom_denied_patterns(self, temp_workspace: Path) -> None:
        """Custom denied patterns should work."""
        ctx = SecurityContext(
            workspace=str(temp_workspace),
            denied_patterns=["*.forbidden", "*secret*"],
        )
        set_security_context(ctx)

        forbidden_file = temp_workspace / "test.forbidden"
        forbidden_file.write_text("blocked")

        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(forbidden_file))


class TestResourceLimits:
    """Test resource limit enforcement."""

    def test_blocks_deeply_nested_paths(self, temp_workspace: Path) -> None:
        """Paths exceeding max depth should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace), max_path_depth=10)
        set_security_context(ctx)

        # Create deeply nested path
        deep_path = temp_workspace
        for i in range(20):
            deep_path = deep_path / f"dir{i}"
        deep_path.mkdir(parents=True, exist_ok=True)
        test_file = deep_path / "file.txt"
        test_file.write_text("test")

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path(str(test_file))

        assert "exceeds maximum depth" in str(exc.value)

    def test_allows_paths_within_depth_limit(self, temp_workspace: Path) -> None:
        """Paths within depth limit should be allowed."""
        ctx = SecurityContext(workspace=str(temp_workspace), max_path_depth=100)
        set_security_context(ctx)

        # test.py is only a few levels deep
        result = validate_path(str(temp_workspace / "test.py"))
        assert result.exists()

    def test_blocks_large_files(self, temp_workspace: Path) -> None:
        """Files exceeding size limit should be blocked."""
        ctx = SecurityContext(
            workspace=str(temp_workspace),
            max_file_size=1024,  # 1KB limit
        )
        set_security_context(ctx)

        large_file = temp_workspace / "large.bin"
        large_file.write_text("x" * 2048)  # 2KB

        resolved = ctx.validate_path(str(large_file))

        with pytest.raises(WorkspaceSecurityError) as exc:
            ctx.validate_file_size(resolved)

        assert "too large" in str(exc.value)

    def test_allows_files_within_size_limit(self, temp_workspace: Path) -> None:
        """Files within size limit should be allowed."""
        ctx = SecurityContext(
            workspace=str(temp_workspace),
            max_file_size=1024 * 1024,  # 1MB
        )
        set_security_context(ctx)

        small_file = temp_workspace / "small.txt"
        small_file.write_text("hello")

        resolved = ctx.validate_path(str(small_file))
        # Should not raise
        ctx.validate_file_size(resolved)


class TestBinaryDetection:
    """Test binary file detection."""

    def test_detects_binary_by_null_bytes(
        self, temp_workspace: Path, mock_binary_file: Path
    ) -> None:
        """Files with null bytes should be detected as binary."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        assert ctx.is_binary_file(mock_binary_file) is True

    def test_detects_binary_by_extension(self, temp_workspace: Path) -> None:
        """Files with binary extensions should be detected."""
        ctx = SecurityContext(workspace=str(temp_workspace))

        exe_file = temp_workspace / "program.exe"
        exe_file.write_bytes(b"not really an exe")

        assert ctx.is_binary_file(exe_file) is True

    def test_text_files_not_detected_as_binary(self, temp_workspace: Path) -> None:
        """Normal text files should not be detected as binary."""
        ctx = SecurityContext(workspace=str(temp_workspace))

        text_file = temp_workspace / "test.py"
        assert ctx.is_binary_file(text_file) is False


class TestReadBeforeEdit:
    """Test read-before-edit tracking."""

    def test_check_fails_for_unread_file(self, temp_workspace: Path) -> None:
        """Unread existing files should fail the check."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        existing_file = temp_workspace / "test.py"
        assert ctx.check_read_before_edit(existing_file) is False

    def test_check_passes_after_marking_read(self, temp_workspace: Path) -> None:
        """Files marked as read should pass the check."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        existing_file = temp_workspace / "test.py"
        ctx.mark_file_read(existing_file)
        assert ctx.check_read_before_edit(existing_file) is True

    def test_check_passes_for_new_file(self, temp_workspace: Path) -> None:
        """Non-existent files should pass the check (they're new)."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        new_file = temp_workspace / "new_file.py"
        assert not new_file.exists()
        assert ctx.check_read_before_edit(new_file) is True

    def test_clear_tracking_resets_state(self, temp_workspace: Path) -> None:
        """Clearing tracking should reset the read state."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        existing_file = temp_workspace / "test.py"
        ctx.mark_file_read(existing_file)
        assert ctx.check_read_before_edit(existing_file) is True

        ctx.clear_read_tracking()
        assert ctx.check_read_before_edit(existing_file) is False


class TestMediaDetection:
    """Test media file detection."""

    def test_detects_image_files(self, temp_workspace: Path) -> None:
        """Image files should be detected as media."""
        ctx = SecurityContext(workspace=str(temp_workspace))

        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            img = temp_workspace / f"image{ext}"
            img.write_bytes(b"fake image data")
            assert ctx.is_media_file(img) is True

    def test_detects_pdf_files(self, temp_workspace: Path) -> None:
        """PDF files should be detected as media."""
        ctx = SecurityContext(workspace=str(temp_workspace))

        pdf = temp_workspace / "document.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake pdf")
        assert ctx.is_media_file(pdf) is True

    def test_svg_not_detected_as_media(self, temp_workspace: Path) -> None:
        """SVG files should NOT be detected as media (they're text)."""
        ctx = SecurityContext(workspace=str(temp_workspace))

        svg = temp_workspace / "image.svg"
        svg.write_text("<svg></svg>")
        assert ctx.is_media_file(svg) is False

    def test_text_not_detected_as_media(self, temp_workspace: Path) -> None:
        """Text files should not be detected as media."""
        ctx = SecurityContext(workspace=str(temp_workspace))

        txt = temp_workspace / "readme.txt"
        txt.write_text("hello world")
        assert ctx.is_media_file(txt) is False


class TestPermissiveContext:
    """Test behavior with no workspace restriction."""

    def test_allows_any_path_without_workspace(
        self, permissive_context: SecurityContext, temp_workspace: Path
    ) -> None:
        """Without workspace restriction, paths should be allowed."""
        # This test uses temp_workspace just to have a valid existing file
        result = validate_path(str(temp_workspace / "test.py"))
        assert result.exists()

    def test_still_blocks_denied_patterns(
        self, temp_workspace: Path
    ) -> None:
        """Denied patterns should still be blocked even without workspace."""
        ctx = SecurityContext()  # No workspace
        set_security_context(ctx)

        env_file = temp_workspace / ".env"
        env_file.write_text("SECRET=value")

        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(env_file))


class TestNullByteProtection:
    """Test protection against null bytes in paths."""

    def test_blocks_null_byte_at_start(self, temp_workspace: Path) -> None:
        """Null byte at start of path should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError) as exc:
            validate_path("\x00" + str(temp_workspace / "test.py"))

        assert "null byte" in str(exc.value).lower()

    def test_blocks_null_byte_in_middle(self, temp_workspace: Path) -> None:
        """Null byte in middle of path should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(temp_workspace) + "/test\x00.py")

    def test_blocks_null_byte_at_end(self, temp_workspace: Path) -> None:
        """Null byte at end of path should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(temp_workspace / "test.py") + "\x00")

    def test_blocks_null_byte_traversal_attack(self, temp_workspace: Path) -> None:
        """Null byte combined with traversal should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(WorkspaceSecurityError):
            validate_path(str(temp_workspace) + "/../../etc/passwd\x00.txt")


class TestContentSizeValidation:
    """Test content size validation for writes."""

    def test_allows_small_content(self, temp_workspace: Path) -> None:
        """Content within limits should pass."""
        ctx = SecurityContext(workspace=str(temp_workspace), max_file_size=1024 * 1024)
        ctx.validate_content_size("Hello, world!")

    def test_blocks_oversized_content(self, temp_workspace: Path) -> None:
        """Content exceeding limits should be blocked."""
        ctx = SecurityContext(workspace=str(temp_workspace), max_file_size=100)

        with pytest.raises(WorkspaceSecurityError) as exc:
            ctx.validate_content_size("x" * 200, operation="write")

        assert "too large" in str(exc.value).lower()
        assert "write" in str(exc.value)

    def test_content_size_uses_utf8_encoding(self, temp_workspace: Path) -> None:
        """Content size should be measured in UTF-8 bytes."""
        ctx = SecurityContext(workspace=str(temp_workspace), max_file_size=10)

        # Multi-byte UTF-8 characters
        with pytest.raises(WorkspaceSecurityError):
            ctx.validate_content_size("Hello 世界")  # > 10 bytes in UTF-8


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_handles_nonexistent_file(self, temp_workspace: Path) -> None:
        """Nonexistent files should raise FileNotFoundError."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        with pytest.raises(FileNotFoundError):
            validate_path(str(temp_workspace / "does_not_exist.txt"))

    def test_allows_new_file_creation(self, temp_workspace: Path) -> None:
        """New files should be validatable with check_exists=False."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        new_file = temp_workspace / "will_be_created.txt"
        result = validate_path(str(new_file), check_exists=False)
        # Should not raise, returns resolved path
        assert result.parent == temp_workspace.resolve()

    def test_handles_unicode_paths(
        self, temp_workspace: Path, unicode_files: dict[str, Path]
    ) -> None:
        """Unicode file paths should work correctly."""
        ctx = SecurityContext(workspace=str(temp_workspace))
        set_security_context(ctx)

        if "unicode_content" in unicode_files:
            result = validate_path(str(unicode_files["unicode_content"]))
            assert result.exists()

    def test_context_isolation(self, temp_workspace: Path) -> None:
        """Different contexts should be isolated."""
        ctx1 = SecurityContext(workspace=str(temp_workspace))
        ctx2 = SecurityContext(workspace="/different/path")

        set_security_context(ctx1)
        current = get_security_context()
        assert current.workspace == str(temp_workspace)

        set_security_context(ctx2)
        current = get_security_context()
        assert current.workspace == "/different/path"
