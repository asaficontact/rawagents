"""Tests for edit replacement strategies."""

from __future__ import annotations

from rawagents.tools.builtin.fs._replacers import (
    BlockAnchorReplacer,
    FuzzyReplacer,
    IndentationFlexibleReplacer,
    LineTrimmedReplacer,
    SimpleReplacer,
    WhitespaceNormalizedReplacer,
    find_and_replace,
)


class TestSimpleReplacer:
    """Test exact string matching."""

    def test_exact_match(self) -> None:
        """Exact strings should match."""
        replacer = SimpleReplacer()
        content = "def hello():\n    pass"
        old = "def hello():\n    pass"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1
        assert matches[0].matched_text == old

    def test_no_match(self) -> None:
        """Non-matching strings should return empty."""
        replacer = SimpleReplacer()
        content = "def hello():\n    pass"
        old = "def goodbye():"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 0

    def test_multiple_matches(self) -> None:
        """Multiple occurrences should all be found."""
        replacer = SimpleReplacer()
        content = "foo bar foo baz foo"
        old = "foo"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 3

    def test_replacement(self) -> None:
        """Replacement should work correctly."""
        replacer = SimpleReplacer()
        content = "hello world"
        result = replacer.replace(content, "world", "universe")

        assert result.success
        assert result.content == "hello universe"
        assert result.strategy == "simple"


class TestLineTrimmedReplacer:
    """Test line-trimmed matching."""

    def test_ignores_leading_whitespace(self) -> None:
        """Leading whitespace per line should be ignored."""
        replacer = LineTrimmedReplacer()
        content = "    def hello():\n        pass"
        old = "def hello():\n    pass"  # Different indentation

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_ignores_trailing_whitespace(self) -> None:
        """Trailing whitespace should be ignored."""
        replacer = LineTrimmedReplacer()
        content = "def hello():   \n    pass   "
        old = "def hello():\n    pass"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_exact_also_matches(self) -> None:
        """Exact matches should also work."""
        replacer = LineTrimmedReplacer()
        content = "def hello():\n    pass"
        old = "def hello():\n    pass"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1


class TestBlockAnchorReplacer:
    """Test first/last line anchor matching."""

    def test_anchor_match(self) -> None:
        """First and last lines as anchors should work when middle mostly matches."""
        replacer = BlockAnchorReplacer()
        content = "def hello():\n    x = 1\n    y = 2\n    return x"
        old = "def hello():\n    x = 1\n    z = 99\n    return x"

        # First and last lines match, 1/2 middle lines match (50%) — accepted
        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_requires_two_lines(self) -> None:
        """Single line strings should not use anchor matching."""
        replacer = BlockAnchorReplacer()
        content = "def hello():"
        old = "def hello():"

        # Should return empty - anchoring needs 2+ lines
        matches = replacer.find_matches(content, old)
        assert len(matches) == 0

    def test_preserves_actual_content(self) -> None:
        """Matched text should be the actual content, not search pattern."""
        replacer = BlockAnchorReplacer()
        content = "start:\n    line_a\n    actual_middle\nend"
        old = "start:\n    line_a\n    different\nend"

        # 1/2 middle lines match (50%) — accepted
        matches = replacer.find_matches(content, old)
        assert len(matches) == 1
        assert "actual_middle" in matches[0].matched_text


class TestBlockAnchorMiddleContent:
    """Test that BlockAnchorReplacer verifies middle content."""

    def test_rejects_totally_different_middle(self) -> None:
        """Should reject when middle content is completely different."""
        replacer = BlockAnchorReplacer()
        content = "def start():\n    actual_line_1\n    actual_line_2\n    actual_line_3\nend"
        old = "def start():\n    completely_wrong_1\n    completely_wrong_2\n    completely_wrong_3\nend"

        # Middle lines are completely different — should reject
        matches = replacer.find_matches(content, old)
        assert len(matches) == 0

    def test_accepts_mostly_matching_middle(self) -> None:
        """Should accept when most middle lines match."""
        replacer = BlockAnchorReplacer()
        content = "def start():\n    line_a\n    line_b\n    line_c\nend"
        old = "def start():\n    line_a\n    line_b\n    different\nend"

        # 2/3 middle lines match (67%) — should accept
        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_two_line_blocks_skip_middle_check(self) -> None:
        """Two-line blocks have no middle — should work as before."""
        replacer = BlockAnchorReplacer()
        content = "start\nend"
        old = "start\nend"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_three_line_block_requires_middle_match(self) -> None:
        """Three-line block: the single middle line must match for 50% threshold."""
        replacer = BlockAnchorReplacer()
        content = "start\n    middle_actual\nend"
        old = "start\n    middle_wrong\nend"

        # 0/1 middle lines match (0%) — should reject
        matches = replacer.find_matches(content, old)
        assert len(matches) == 0


class TestWhitespaceNormalizedReplacer:
    """Test whitespace-normalized matching."""

    def test_collapses_whitespace(self) -> None:
        """Multiple consecutive whitespace should be collapsed."""
        replacer = WhitespaceNormalizedReplacer()
        # Multiple spaces between words
        content = "def    hello():\n        pass"  # Extra spaces
        old = "def hello():\n    pass"  # Normal spacing

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_normalizes_newlines_and_spaces(self) -> None:
        """Extra blank lines should be normalized away."""
        replacer = WhitespaceNormalizedReplacer()
        content = "a\n\n\nb\nc"  # Extra blank lines
        old = "a\nb\nc"  # Normal

        matches = replacer.find_matches(content, old)
        # Both normalize to "a b c"
        assert len(matches) >= 1


class TestIndentationFlexibleReplacer:
    """Test indentation-flexible matching."""

    def test_different_base_indent(self) -> None:
        """Different base indentation should match."""
        replacer = IndentationFlexibleReplacer()
        content = "    def hello():\n        pass"  # 4-space indent
        old = "def hello():\n    pass"  # No base indent

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_preserves_relative_structure(self) -> None:
        """Relative indentation structure should be preserved."""
        replacer = IndentationFlexibleReplacer()
        # Same relative structure (0, +4)
        content = "        if True:\n            pass"  # 8, 12
        old = "    if True:\n        pass"  # 4, 8

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_different_structure_no_match(self) -> None:
        """Different relative structure should not match."""
        replacer = IndentationFlexibleReplacer()
        content = "def hello():\npass"  # Structure: 0, 0
        old = "def hello():\n    pass"  # Structure: 0, 4

        matches = replacer.find_matches(content, old)
        assert len(matches) == 0


class TestFuzzyReplacer:
    """Test fuzzy matching using SequenceMatcher."""

    def test_matches_minor_typo(self) -> None:
        """Should match content with minor differences (e.g., missing comma)."""
        replacer = FuzzyReplacer()
        content = "def hello():\n    print('Hello, world!')\n    return True"
        old = "def hello():\n    print('Hello world!')\n    return True"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_no_match_below_threshold(self) -> None:
        """Completely different content should not match."""
        replacer = FuzzyReplacer()
        content = "class Foo:\n    value = 42\n    name = 'bar'"
        old = "import os\nimport sys\nprint('hello')"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 0

    def test_skips_large_file_short_pattern(self) -> None:
        """Large file + short pattern should be skipped to prevent false positives."""
        replacer = FuzzyReplacer()
        content = "\n".join(f"line {i}" for i in range(6000))
        old = "line 100\nline 101\nline 102"  # 3 lines (< min_pattern_lines)

        matches = replacer.find_matches(content, old)
        assert len(matches) == 0

    def test_allows_large_file_long_pattern(self) -> None:
        """Large file + long pattern should still work."""
        replacer = FuzzyReplacer()
        content = "\n".join(f"line {i}" for i in range(6000))
        old = "\n".join(f"line {i}" for i in range(100, 110))  # 10 lines

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_matches_renamed_variable(self) -> None:
        """Should match when a variable name differs."""
        replacer = FuzzyReplacer()
        content = "def calc():\n    foo_bar = 1\n    result = foo_bar + 2\n    return result"
        old = "def calc():\n    foo_baz = 1\n    result = foo_baz + 2\n    return result"

        matches = replacer.find_matches(content, old)
        assert len(matches) == 1

    def test_empty_old_string(self) -> None:
        """Empty old_string should return no matches."""
        replacer = FuzzyReplacer()
        matches = replacer.find_matches("some content", "")
        assert len(matches) == 0

    def test_empty_content(self) -> None:
        """Empty content should return no matches."""
        replacer = FuzzyReplacer()
        matches = replacer.find_matches("", "some pattern")
        assert len(matches) == 0

    def test_multiple_similar_blocks(self) -> None:
        """With multiple similar blocks, should return the best one."""
        replacer = FuzzyReplacer()
        content = "def a():\n    pass\n\ndef b():\n    pass"
        old = "def a():\n    return"  # Close to first block

        matches = replacer.find_matches(content, old)
        # Should find at most 1 (the best match)
        assert len(matches) <= 1


class TestFindAndReplace:
    """Test the main find_and_replace function."""

    def test_uses_simple_first(self) -> None:
        """Simple exact match should be used first."""
        result = find_and_replace(
            content="hello world",
            old_string="hello",
            new_string="goodbye",
        )

        assert result.success
        assert result.content == "goodbye world"
        assert result.strategy == "simple"

    def test_falls_back_to_other_strategies(self) -> None:
        """Should try other strategies when simple fails."""
        result = find_and_replace(
            content="    def hello():\n        pass",
            old_string="def hello():\n    pass",  # Different indent
            new_string="def goodbye():\n    return",
        )

        assert result.success
        assert "goodbye" in result.content
        # Should use line_trimmed or indentation_flexible
        assert result.strategy in ("line_trimmed", "indentation_flexible")

    def test_handles_empty_old_string(self) -> None:
        """Empty old_string should create new content."""
        result = find_and_replace(
            content="existing",
            old_string="",
            new_string="new content",
        )

        assert result.success
        assert result.content == "new content"
        assert result.strategy == "create"

    def test_fails_for_identical_strings(self) -> None:
        """Same old and new should fail."""
        result = find_and_replace(
            content="hello",
            old_string="hello",
            new_string="hello",
        )

        assert not result.success
        assert "identical" in result.error

    def test_fails_for_no_match(self) -> None:
        """No match should fail with appropriate error."""
        result = find_and_replace(
            content="hello world",
            old_string="xyz",
            new_string="abc",
        )

        assert not result.success
        assert "not found" in result.error

    def test_fails_for_multiple_matches_without_replace_all(self) -> None:
        """Multiple matches should fail without replace_all."""
        result = find_and_replace(
            content="foo bar foo",
            old_string="foo",
            new_string="baz",
            replace_all=False,
        )

        assert not result.success
        assert "multiple" in result.error.lower() or "2" in result.error

    def test_replace_all_works(self) -> None:
        """replace_all=True should replace all occurrences."""
        result = find_and_replace(
            content="foo bar foo baz foo",
            old_string="foo",
            new_string="qux",
            replace_all=True,
        )

        assert result.success
        assert result.content == "qux bar qux baz qux"
        assert result.match_count == 3


class TestReplacementPreservesContent:
    """Test that replacements preserve surrounding content."""

    def test_preserves_before_and_after(self) -> None:
        """Content before and after match should be preserved."""
        result = find_and_replace(
            content="# Comment\ndef hello():\n    pass\n# End",
            old_string="def hello():\n    pass",
            new_string="def goodbye():\n    return",
        )

        assert result.success
        assert "# Comment\n" in result.content
        assert "\n# End" in result.content

    def test_preserves_indentation_in_replacement(self) -> None:
        """When using flex replacer, indentation should be adjusted."""
        # This tests that the matched text (with actual indent) is replaced,
        # not the search pattern
        content = "class Foo:\n    def hello():\n        pass"
        result = find_and_replace(
            content=content,
            old_string="def hello():\n    pass",  # 0, 4 indent
            new_string="def goodbye():\n    return",
        )

        assert result.success
        # The replacement should maintain structure
        assert "goodbye" in result.content
