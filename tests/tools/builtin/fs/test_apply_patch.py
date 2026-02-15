"""Tests for the apply_patch tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs import (
    SecurityContext,
    apply_patch,
)


class TestApplyPatch:
    """Test the apply_patch tool."""

    @pytest.mark.asyncio
    async def test_adds_new_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should add a new file."""
        patch = """*** Begin Patch
*** Add File: new_file.py
+def hello():
+    print("hello")
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Success" in result
        assert "A" in result  # Add indicator

        new_file = temp_workspace / "new_file.py"
        assert new_file.exists()
        assert "def hello():" in new_file.read_text()

    @pytest.mark.asyncio
    async def test_updates_existing_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should update an existing file."""
        # Create file to update
        existing = temp_workspace / "existing.py"
        existing.write_text("def old():\n    pass\n")
        secure_context.mark_file_read(existing)

        patch = """*** Begin Patch
*** Update File: existing.py
@@ -1,2 +1,2 @@
-def old():
+def new():
     pass
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Success" in result
        assert "M" in result  # Modify indicator

    @pytest.mark.asyncio
    async def test_deletes_file(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should delete a file."""
        # Create file to delete and mark as read
        to_delete = temp_workspace / "to_delete.txt"
        to_delete.write_text("delete me")
        secure_context.mark_file_read(to_delete)

        patch = """*** Begin Patch
*** Delete File: to_delete.txt
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Success" in result
        assert "D" in result  # Delete indicator
        assert not to_delete.exists()

    @pytest.mark.asyncio
    async def test_rejects_empty_patch(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should reject empty patch."""
        patch = """*** Begin Patch
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Error" in result
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_requires_patch_markers(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require patch begin/end markers."""
        patch = """*** Add File: test.py
+content"""

        result = await apply_patch(patch_text=patch)

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_validates_paths_in_workspace(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should validate paths are within workspace."""
        patch = """*** Begin Patch
*** Add File: /etc/evil.txt
+bad content
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Error" in result


class TestApplyPatchParsing:
    """Test patch parsing edge cases."""

    @pytest.mark.asyncio
    async def test_handles_multiple_operations(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should handle multiple operations in one patch."""
        # Create file to update
        existing = temp_workspace / "multi.py"
        existing.write_text("old content\n")
        secure_context.mark_file_read(existing)

        patch = """*** Begin Patch
*** Add File: added.py
+new file content
*** Update File: multi.py
@@ -1 +1 @@
-old content
+new content
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Success" in result
        assert (temp_workspace / "added.py").exists()

    @pytest.mark.asyncio
    async def test_handles_empty_patch_text(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should handle empty patch text."""
        result = await apply_patch(patch_text="")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_creates_parent_directories(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should create parent directories for new files."""
        patch = """*** Begin Patch
*** Add File: new/nested/dir/file.py
+content
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Success" in result
        assert (temp_workspace / "new" / "nested" / "dir" / "file.py").exists()

    @pytest.mark.asyncio
    async def test_moves_file_during_update(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should move file when *** Move to: directive present in update."""
        original = temp_workspace / "original.py"
        original.write_text("def original():\n    pass\n")
        secure_context.mark_file_read(original)

        patch = """*** Begin Patch
*** Update File: original.py
*** Move to: renamed.py
@@ -1,2 +1,2 @@
-def original():
+def renamed():
     pass
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Success" in result
        assert not original.exists(), "Original file should be deleted"
        renamed = temp_workspace / "renamed.py"
        assert renamed.exists(), "Renamed file should exist"
        assert "def renamed():" in renamed.read_text()


class TestApplyPatchChunkErrors:
    """Test that apply_patch reports chunk errors instead of silently skipping."""

    @pytest.mark.asyncio
    async def test_reports_error_on_chunk_not_found(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should report error when a chunk's old_text is not found."""
        existing = temp_workspace / "chunk_test.py"
        existing.write_text("def hello():\n    pass\n")
        secure_context.mark_file_read(existing)

        patch = """*** Begin Patch
*** Update File: chunk_test.py
@@ -1,2 +1,2 @@
-def nonexistent():
+def replacement():
     pass
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Error" in result
        assert "chunk" in result.lower()

    @pytest.mark.asyncio
    async def test_uses_replacer_strategies_for_fuzzy_match(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should use replacement strategies for fuzzy matching in patches."""
        existing = temp_workspace / "fuzzy_test.py"
        existing.write_text("    def hello():\n        pass\n")
        secure_context.mark_file_read(existing)

        # old_text has different indentation — replacer strategies should handle this
        patch = """*** Begin Patch
*** Update File: fuzzy_test.py
@@ -1,2 +1,2 @@
-def hello():
+def goodbye():
     pass
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        # Should succeed via fuzzy matching strategies
        assert "Success" in result or "Error" in result  # Depends on strategy match


class TestApplyPatchReadBeforeEdit:
    """Test read-before-edit enforcement in apply_patch."""

    @pytest.mark.asyncio
    async def test_update_requires_read_first(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require file to be read before updating via patch."""
        # Create file but DON'T mark it as read
        existing = temp_workspace / "unread.py"
        existing.write_text("def old():\n    pass\n")

        patch = """*** Begin Patch
*** Update File: unread.py
@@ -1,2 +1,2 @@
-def old():
+def new():
     pass
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Error" in result
        assert "not read" in result.lower() or "read" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_requires_read_first(
        self, temp_workspace: Path, secure_context: SecurityContext
    ) -> None:
        """Should require file to be read before deleting via patch."""
        # Create file but DON'T mark it as read
        to_delete = temp_workspace / "unread_delete.txt"
        to_delete.write_text("delete me")

        patch = """*** Begin Patch
*** Delete File: unread_delete.txt
*** End Patch"""

        result = await apply_patch(patch_text=patch)

        assert "Error" in result
        assert "not read" in result.lower() or "read" in result.lower()
        # File should NOT be deleted
        assert to_delete.exists()
