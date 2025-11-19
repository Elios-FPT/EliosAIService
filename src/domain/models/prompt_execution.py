"""Prompt execution domain model."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PromptExecution(BaseModel):
    """Analytics record for prompt execution.

    Tracks every LLM call for cost tracking,
    performance monitoring, and debugging.
    """

    id: UUID = Field(default_factory=uuid4)
    prompt_template_id: UUID = Field(..., description="Which version executed")
    interview_id: UUID | None = Field(default=None, description="Interview context")
    candidate_id: UUID | None = Field(default=None, description="Candidate context")
    input_variables: dict = Field(..., description="Variables passed to prompt")
    output_text: str | None = Field(default=None, description="LLM response")
    tokens_used: int | None = Field(default=None, ge=0, description="Total tokens")
    prompt_tokens: int | None = Field(default=None, ge=0, description="Prompt tokens")
    completion_tokens: int | None = Field(default=None, ge=0, description="Completion tokens")
    latency_ms: int = Field(..., ge=0, description="Execution time (ms)")
    model_name: str | None = Field(default=None, max_length=50, description="LLM model")
    success: bool = Field(..., description="Execution success")
    error_message: str | None = Field(default=None, description="Error details")
    executed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "prompt_template_id": "123e4567-e89b-12d3-a456-426614174000",
                "input_variables": {"skill": "Python", "difficulty": "medium"},
                "output_text": "Explain the concept of decorators in Python...",
                "prompt_tokens": 150,
                "completion_tokens": 300,
                "latency_ms": 1500,
                "model_name": "gpt-4",
                "success": True
            }
        }

    def calculate_estimated_cost(self) -> float:
        """Calculate estimated cost in USD.

        Uses OpenAI gpt-4 pricing:
        - Prompt: $0.03/1k tokens
        - Completion: $0.06/1k tokens

        Returns:
            Estimated cost in USD
        """
        if not self.prompt_tokens or not self.completion_tokens:
            return 0.0

        prompt_cost = (self.prompt_tokens / 1000.0) * 0.03
        completion_cost = (self.completion_tokens / 1000.0) * 0.06

        return prompt_cost + completion_cost
