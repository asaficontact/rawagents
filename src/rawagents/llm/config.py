"""Configuration for the LLM client."""

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for LLMClient.

    Attributes:
        model: Default model to use if not specified per-call.
            Format: "provider/model-name" (e.g., "openai/gpt-4o").
        retries: Default number of LiteLLM API retries.
            These retry on transient errors (429, 503, 500, 408).
        structured_validation_retries: Default number of Instructor validation retries.
            These retry when Pydantic validation fails.
        timeout: Request timeout in seconds.
        fallbacks: List of fallback models to try if the primary fails.
            Format: ["provider/model", ...].

    Example:
        >>> config = LLMConfig(
        ...     model="openai/gpt-4o",
        ...     retries=3,
        ...     fallbacks=["anthropic/claude-3-5-sonnet-latest"],
        ... )
        >>> client = LLMClient(config=config)
    """

    model: str = Field(
        default="openai/gpt-4o-mini",
        description="Default model to use if not specified per-call",
    )
    retries: int = Field(
        default=3,
        ge=0,
        description="Default number of LiteLLM API retries",
    )
    structured_validation_retries: int = Field(
        default=3,
        ge=0,
        description="Default number of Instructor validation retries",
    )
    timeout: int = Field(
        default=60,
        gt=0,
        description="Request timeout in seconds",
    )
    fallbacks: list[str] = Field(
        default_factory=list,
        description="List of fallback models to try if the primary fails",
    )
