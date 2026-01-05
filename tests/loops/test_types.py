"""Tests for loop types."""

import pytest
from pydantic import ValidationError

from rawagents.utils.types import ToolCall, ToolResult
from rawagents.loops import ApprovalDecision, LoopConfig, LoopStep


class TestLoopStep:
    """Tests for LoopStep."""

    def test_step_id_auto_generated(self) -> None:
        """step_id is auto-generated when not provided."""
        step = LoopStep(type="thought")
        assert step.step_id is not None
        assert len(step.step_id) > 0

    def test_step_id_unique(self) -> None:
        """Each step gets a unique step_id."""
        step1 = LoopStep(type="thought")
        step2 = LoopStep(type="thought")
        assert step1.step_id != step2.step_id

    def test_all_step_types_valid(self) -> None:
        """All defined step types are valid."""
        valid_types = [
            "thought",
            "tool_call",
            "tool_result",
            "approval_request",
            "error",
            "finish",
        ]
        for step_type in valid_types:
            step = LoopStep(type=step_type)  # type: ignore[arg-type]
            assert step.type == step_type

    def test_invalid_step_type_raises(self) -> None:
        """Invalid step type raises ValidationError."""
        with pytest.raises(ValidationError):
            LoopStep(type="invalid_type")  # type: ignore[arg-type]

    def test_metadata_defaults_to_empty_dict(self) -> None:
        """metadata defaults to empty dict."""
        step = LoopStep(type="thought")
        assert step.metadata == {}

    def test_metadata_can_be_set(self) -> None:
        """metadata can be provided."""
        step = LoopStep(
            type="thought",
            metadata={"step_number": 1, "cost": 0.001},
        )
        assert step.metadata["step_number"] == 1
        assert step.metadata["cost"] == 0.001

    def test_content_optional(self) -> None:
        """content is optional."""
        step = LoopStep(type="thought")
        assert step.content is None

    def test_content_can_be_set(self) -> None:
        """content can be provided."""
        step = LoopStep(type="thought", content="Thinking...")
        assert step.content == "Thinking..."

    def test_tool_calls_optional(self) -> None:
        """tool_calls is optional."""
        step = LoopStep(type="tool_call")
        assert step.tool_calls is None

    def test_tool_calls_can_be_set(self) -> None:
        """tool_calls can be provided."""
        tool_calls = [
            ToolCall(id="call_1", name="search", arguments={"query": "test"})
        ]
        step = LoopStep(type="tool_call", tool_calls=tool_calls)
        assert step.tool_calls is not None
        assert len(step.tool_calls) == 1
        assert step.tool_calls[0].name == "search"

    def test_tool_results_optional(self) -> None:
        """tool_results is optional."""
        step = LoopStep(type="tool_result")
        assert step.tool_results is None

    def test_tool_results_can_be_set(self) -> None:
        """tool_results can be provided."""
        tool_results = [
            ToolResult(
                tool_call_id="call_1",
                name="search",
                content='{"results": []}',
                is_error=False,
            )
        ]
        step = LoopStep(type="tool_result", tool_results=tool_results)
        assert step.tool_results is not None
        assert len(step.tool_results) == 1
        assert step.tool_results[0].name == "search"


class TestLoopConfig:
    """Tests for LoopConfig."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = LoopConfig()
        assert config.max_steps == 15
        assert config.tool_choice == "auto"
        assert config.temperature == 0.7
        assert config.stop_on_error is False

    def test_max_steps_minimum(self) -> None:
        """max_steps must be at least 1."""
        with pytest.raises(ValidationError):
            LoopConfig(max_steps=0)

    def test_max_steps_maximum(self) -> None:
        """max_steps must be at most 100."""
        with pytest.raises(ValidationError):
            LoopConfig(max_steps=101)

    def test_max_steps_at_bounds(self) -> None:
        """max_steps can be 1 or 100."""
        config_min = LoopConfig(max_steps=1)
        config_max = LoopConfig(max_steps=100)
        assert config_min.max_steps == 1
        assert config_max.max_steps == 100

    def test_custom_config(self) -> None:
        """Custom config values are applied."""
        config = LoopConfig(
            max_steps=10,
            tool_choice="required",
            temperature=0.5,
            stop_on_error=True,
        )
        assert config.max_steps == 10
        assert config.tool_choice == "required"
        assert config.temperature == 0.5
        assert config.stop_on_error is True


class TestApprovalDecision:
    """Tests for ApprovalDecision."""

    def test_approved_true(self) -> None:
        """Approved decision with no feedback."""
        decision = ApprovalDecision(approved=True)
        assert decision.approved is True
        assert decision.feedback is None

    def test_approved_false_no_feedback(self) -> None:
        """Denied decision with no feedback."""
        decision = ApprovalDecision(approved=False)
        assert decision.approved is False
        assert decision.feedback is None

    def test_approved_false_with_feedback(self) -> None:
        """Denied decision with feedback."""
        decision = ApprovalDecision(
            approved=False,
            feedback="Please use a different tool instead.",
        )
        assert decision.approved is False
        assert decision.feedback == "Please use a different tool instead."

    def test_approved_required(self) -> None:
        """approved field is required."""
        with pytest.raises(ValidationError):
            ApprovalDecision()  # type: ignore[call-arg]
