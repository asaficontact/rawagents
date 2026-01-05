"""Custom exceptions for the Loops component."""

from __future__ import annotations

__all__ = [
    "LoopError",
    "MaxStepsExceededError",
    "LoopCancelledError",
]


class LoopError(Exception):
    """Base exception for loop-related errors."""

    pass


class MaxStepsExceededError(LoopError):
    """Raised when max_steps limit is reached.

    Attributes:
        max_steps: The configured limit that was exceeded.
        steps_taken: Number of steps completed.
    """

    def __init__(
        self,
        max_steps: int,
        steps_taken: int,
    ) -> None:
        self.max_steps = max_steps
        self.steps_taken = steps_taken
        super().__init__(
            f"Loop exceeded maximum steps ({max_steps}). "
            f"Completed {steps_taken} steps. Increase max_steps or "
            f"check for infinite loops."
        )


class LoopCancelledError(LoopError):
    """Raised when loop is cancelled by user denial in interactive mode."""

    def __init__(self, message: str = "Loop cancelled by user") -> None:
        super().__init__(message)
