"""Edit replacement strategies for the edit tool.

This module implements the 5 replacement strategies from OpenCode that help
reduce brittle exact-match failures from LLM-generated oldString values.

The strategies are tried in order:
1. SimpleReplacer - Exact string match (fastest, most precise)
2. LineTrimmedReplacer - Ignores leading/trailing whitespace per line
3. BlockAnchorReplacer - Uses first/last line as anchors
4. WhitespaceNormalizedReplacer - Collapses all whitespace differences
5. IndentationFlexibleReplacer - Allows different indentation levels

Each strategy implements a common interface for finding matches and
performing replacements.
"""

from __future__ import annotations

import difflib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


__all__ = [
    "BlockAnchorReplacer",
    "FuzzyReplacer",
    "IndentationFlexibleReplacer",
    "LineTrimmedReplacer",
    "ReplacementResult",
    "Replacer",
    "SimpleReplacer",
    "WhitespaceNormalizedReplacer",
    "find_and_replace",
]


@dataclass
class ReplacementResult:
    """Result of a replacement operation.

    Attributes:
        success: Whether the replacement was successful.
        content: The new content after replacement (if successful).
        match_count: Number of matches found.
        strategy: Name of the strategy that succeeded.
        error: Error message if unsuccessful.
    """

    success: bool
    content: str | None = None
    match_count: int = 0
    strategy: str | None = None
    error: str | None = None


@dataclass
class Match:
    """A match location in the content.

    Attributes:
        start: Start index in the content.
        end: End index in the content.
        matched_text: The actual text that matched.
    """

    start: int
    end: int
    matched_text: str


class Replacer(ABC):
    """Abstract base class for replacement strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of this replacement strategy."""
        pass

    @abstractmethod
    def find_matches(self, content: str, old_string: str) -> list[Match]:
        """Find all matches of old_string in content.

        Args:
            content: The file content to search.
            old_string: The string to find.

        Returns:
            List of Match objects for all found locations.
        """
        pass

    def replace(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> ReplacementResult:
        """Replace old_string with new_string in content.

        Args:
            content: The file content.
            old_string: The string to find and replace.
            new_string: The replacement string.
            replace_all: If True, replace all occurrences.

        Returns:
            ReplacementResult with the outcome.
        """
        matches = self.find_matches(content, old_string)

        if not matches:
            return ReplacementResult(
                success=False,
                match_count=0,
                strategy=self.name,
                error="old_string not found in content",
            )

        if len(matches) > 1 and not replace_all:
            return ReplacementResult(
                success=False,
                match_count=len(matches),
                strategy=self.name,
                error=(
                    f"Found {len(matches)} matches for old_string. "
                    "Provide more surrounding lines in old_string to identify "
                    "the correct match, or use replace_all=True."
                ),
            )

        # Perform replacement(s) from end to start to preserve indices
        result_content = content
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            result_content = (
                result_content[: match.start] + new_string + result_content[match.end :]
            )

        return ReplacementResult(
            success=True,
            content=result_content,
            match_count=len(matches),
            strategy=self.name,
        )


class SimpleReplacer(Replacer):
    """Exact string match replacement.

    This is the fastest and most precise strategy. It performs a simple
    substring search for an exact match.
    """

    @property
    def name(self) -> str:
        return "simple"

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        matches: list[Match] = []
        start = 0

        while True:
            idx = content.find(old_string, start)
            if idx == -1:
                break
            matches.append(Match(start=idx, end=idx + len(old_string), matched_text=old_string))
            start = idx + 1

        return matches


class LineTrimmedReplacer(Replacer):
    """Replacement ignoring leading/trailing whitespace per line.

    This helps when the LLM generates oldString with slightly different
    indentation or trailing spaces per line.
    """

    @property
    def name(self) -> str:
        return "line_trimmed"

    def _normalize(self, text: str) -> tuple[str, list[str]]:
        """Normalize text by trimming each line."""
        lines = text.split("\n")
        trimmed = [line.strip() for line in lines]
        return "\n".join(trimmed), lines

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        # Split both into lines
        content_lines = content.split("\n")
        old_lines = old_string.split("\n")
        old_trimmed = [line.strip() for line in old_lines]

        if not old_trimmed or all(not line for line in old_trimmed):
            return []

        matches: list[Match] = []
        num_old_lines = len(old_lines)

        # Slide window over content lines
        for i in range(len(content_lines) - num_old_lines + 1):
            window = content_lines[i : i + num_old_lines]
            window_trimmed = [line.strip() for line in window]

            if window_trimmed == old_trimmed:
                # Calculate character positions
                # Start: sum of previous lines + newlines
                start = sum(len(content_lines[j]) + 1 for j in range(i))
                # End: start + matched lines length
                matched_text = "\n".join(window)
                end = start + len(matched_text)
                matches.append(Match(start=start, end=end, matched_text=matched_text))

        return matches


class BlockAnchorReplacer(Replacer):
    """Replacement using first/last lines as anchors.

    Useful when the middle content may have minor variations but the
    first and last lines are reliable anchors.
    """

    @property
    def name(self) -> str:
        return "block_anchor"

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        old_lines = old_string.split("\n")
        if len(old_lines) < 2:
            # Need at least 2 lines for anchor matching
            return []

        first_line = old_lines[0]
        last_line = old_lines[-1]
        num_lines = len(old_lines)

        content_lines = content.split("\n")
        matches: list[Match] = []

        for i in range(len(content_lines) - num_lines + 1):
            # Check if first and last lines match
            if (
                content_lines[i].strip() == first_line.strip()
                and content_lines[i + num_lines - 1].strip() == last_line.strip()
            ):
                # Verify middle content to prevent wrong block matches
                if num_lines > 2:
                    matching_middle = sum(
                        1
                        for j in range(1, num_lines - 1)
                        if content_lines[i + j].strip() == old_lines[j].strip()
                    )
                    if matching_middle / (num_lines - 2) < 0.5:
                        continue  # Not enough middle lines match

                # Calculate positions
                start = sum(len(content_lines[j]) + 1 for j in range(i))
                matched_text = "\n".join(content_lines[i : i + num_lines])
                end = start + len(matched_text)
                matches.append(Match(start=start, end=end, matched_text=matched_text))

        return matches


class WhitespaceNormalizedReplacer(Replacer):
    """Replacement with all whitespace differences normalized.

    Collapses multiple whitespace characters into single spaces and
    performs comparison on the normalized form.
    """

    @property
    def name(self) -> str:
        return "whitespace_normalized"

    def _normalize(self, text: str) -> str:
        """Normalize whitespace: collapse multiple spaces, strip."""
        # Replace all whitespace sequences with single space
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_line(self, line: str) -> str:
        """Normalize a single line's whitespace."""
        return re.sub(r"\s+", " ", line).strip()

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        normalized_old = self._normalize(old_string)
        if not normalized_old:
            return []

        matches: list[Match] = []

        # Strategy: use line-based sliding window but normalize for comparison
        content_lines = content.split("\n")
        old_lines = old_string.split("\n")
        num_old_lines = len(old_lines)

        # Pre-normalize all content lines ONCE for O(n) instead of O(n*k)
        # Filter out empty strings after normalization to handle blank lines
        normalized_content_lines = [self._normalize_line(line) for line in content_lines]
        # Join non-empty normalized old lines and collapse any double spaces
        normalized_old_parts = [self._normalize_line(line) for line in old_lines if self._normalize_line(line)]
        normalized_old_joined = " ".join(normalized_old_parts)

        # Pre-compute cumulative lengths for position calculation
        cumulative_lengths = [0]
        for line in content_lines:
            cumulative_lengths.append(cumulative_lengths[-1] + len(line) + 1)

        # Try different window sizes - whitespace differences can result in
        # different line counts, so try a wider range
        min_window = max(1, num_old_lines - 2)
        max_window = min(len(content_lines), num_old_lines + 3)

        seen_positions: set[tuple[int, int]] = set()

        for window_size in range(min_window, max_window + 1):
            for i in range(len(content_lines) - window_size + 1):
                # Use pre-normalized lines - filter out empty ones for proper comparison
                window_parts = [n for n in normalized_content_lines[i : i + window_size] if n]
                normalized_window = " ".join(window_parts)

                if normalized_window == normalized_old_joined:
                    # Only compute actual positions on match
                    start = cumulative_lengths[i]
                    window_text = "\n".join(content_lines[i : i + window_size])
                    end = start + len(window_text)

                    # Avoid duplicate matches using set for O(1) lookup
                    pos_key = (start, end)
                    if pos_key not in seen_positions:
                        seen_positions.add(pos_key)
                        matches.append(Match(start=start, end=end, matched_text=window_text))

        return matches


class IndentationFlexibleReplacer(Replacer):
    """Replacement allowing different indentation levels.

    Preserves relative indentation structure but allows the base
    indentation level to differ.
    """

    @property
    def name(self) -> str:
        return "indentation_flexible"

    def _get_indent(self, line: str) -> int:
        """Get the indentation level (number of leading spaces/tabs)."""
        stripped = line.lstrip()
        return len(line) - len(stripped)

    def _get_relative_indents(self, lines: list[str]) -> list[int]:
        """Get relative indentation for each line (relative to first non-empty)."""
        # Find base indent (first non-empty line)
        base_indent = 0
        for line in lines:
            if line.strip():
                base_indent = self._get_indent(line)
                break

        return [self._get_indent(line) - base_indent for line in lines]

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        old_lines = old_string.split("\n")
        content_lines = content.split("\n")
        num_old_lines = len(old_lines)

        if not old_lines:
            return []

        # Get structure of old_string
        old_relative_indents = self._get_relative_indents(old_lines)
        old_stripped = [line.strip() for line in old_lines]

        matches: list[Match] = []

        for i in range(len(content_lines) - num_old_lines + 1):
            window = content_lines[i : i + num_old_lines]
            window_stripped = [line.strip() for line in window]
            window_relative_indents = self._get_relative_indents(window)

            # Check if stripped content and relative indentation match
            if (
                window_stripped == old_stripped
                and window_relative_indents == old_relative_indents
            ):
                start = sum(len(content_lines[j]) + 1 for j in range(i))
                matched_text = "\n".join(window)
                end = start + len(matched_text)
                matches.append(Match(start=start, end=end, matched_text=matched_text))

        return matches


class FuzzyReplacer(Replacer):
    """Fuzzy matching using difflib.SequenceMatcher as a last resort.

    Finds the most similar contiguous block in the file content and
    matches it if similarity exceeds the threshold. This catches common
    LLM transcription errors (wrong variable name, missing comma, etc.).

    Safety guards:
    - Skipped for large files (>5000 lines) with short patterns (<5 lines)
      to avoid O(n*k) performance issues and false positives.
    - Threshold of 0.7 is stricter than Aider's 0.6 to prevent false matches.
    """

    threshold: float = 0.7
    short_pattern_threshold: float = 0.85
    short_pattern_max_lines: int = 3
    max_file_lines_for_short_pattern: int = 5000
    min_pattern_lines: int = 5

    @property
    def name(self) -> str:
        return "fuzzy"

    def find_matches(self, content: str, old_string: str) -> list[Match]:
        if not old_string or not content:
            return []

        old_lines = old_string.split("\n")
        content_lines = content.split("\n")
        window_size = len(old_lines)

        if window_size == 0 or len(content_lines) == 0:
            return []

        # Safety: skip large files with short patterns to avoid false positives
        if (
            len(content_lines) > self.max_file_lines_for_short_pattern
            and window_size < self.min_pattern_lines
        ):
            return []

        best_ratio = 0.0
        best_start_line = -1
        best_window_size = window_size

        # Allow window size variation of +/- 20%
        min_window = max(1, int(window_size * 0.8))
        max_window = min(len(content_lines), int(window_size * 1.2))

        for ws in range(min_window, max_window + 1):
            for i in range(len(content_lines) - ws + 1):
                candidate_text = "\n".join(content_lines[i : i + ws])
                ratio = difflib.SequenceMatcher(
                    None, old_string, candidate_text
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_start_line = i
                    best_window_size = ws

        # Use higher threshold for short patterns to prevent false positives
        effective_threshold = (
            self.short_pattern_threshold
            if window_size < self.short_pattern_max_lines
            else self.threshold
        )

        if best_ratio >= effective_threshold and best_start_line >= 0:
            # Calculate character positions
            start = sum(len(content_lines[j]) + 1 for j in range(best_start_line))
            matched_text = "\n".join(
                content_lines[best_start_line : best_start_line + best_window_size]
            )
            end = start + len(matched_text)
            return [Match(start=start, end=end, matched_text=matched_text)]

        return []


# Default strategy order
_STRATEGIES: list[Replacer] = [
    SimpleReplacer(),
    LineTrimmedReplacer(),
    BlockAnchorReplacer(),
    WhitespaceNormalizedReplacer(),
    IndentationFlexibleReplacer(),
    FuzzyReplacer(),
]


def find_and_replace(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> ReplacementResult:
    """Find and replace using all strategies in order.

    Tries each replacement strategy until one succeeds. This reduces
    brittle failures from minor formatting differences in LLM output.

    Args:
        content: The file content.
        old_string: The string to find and replace.
        new_string: The replacement string.
        replace_all: If True, replace all occurrences.

    Returns:
        ReplacementResult from the first successful strategy,
        or an error result if all strategies fail.

    Example:
        >>> result = find_and_replace(
        ...     content="def hello():\\n    pass",
        ...     old_string="def hello():\\n    pass",
        ...     new_string="def goodbye():\\n    pass",
        ... )
        >>> result.success
        True
        >>> result.strategy
        'simple'
    """
    if old_string == new_string:
        return ReplacementResult(
            success=False,
            error="old_string and new_string are identical",
        )

    # Special case: empty old_string means "write new content"
    if not old_string:
        return ReplacementResult(
            success=True,
            content=new_string,
            match_count=0,
            strategy="create",
        )

    last_error: str | None = None
    total_matches = 0

    for strategy in _STRATEGIES:
        result = strategy.replace(content, old_string, new_string, replace_all)

        if result.success:
            return result

        # Track the error with the most matches (most specific)
        if result.match_count > total_matches:
            total_matches = result.match_count
            last_error = result.error
        elif result.match_count == 0 and last_error is None:
            last_error = result.error

    # All strategies failed
    return ReplacementResult(
        success=False,
        match_count=total_matches,
        error=last_error or "old_string not found in content",
    )
