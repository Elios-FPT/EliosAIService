"""DTOs for EvaluateAnswerUseCase.

Maps state access from InterviewConversationWorkflow._evaluate_answer_unified.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluateAnswerInput(BaseModel):
    """Input for EvaluateAnswerUseCase.

    Contains all data needed to evaluate a candidate's answer.
    """

    interview_id: UUID = Field(description="Interview UUID")
    candidate_id: UUID = Field(description="Candidate UUID")
    question: dict[str, Any] = Field(description="Current question (Question.model_dump)")
    answer_text: str = Field(description="Candidate's answer text")
    is_voice: bool = Field(default=False, description="Whether answer was voice input")
    voice_metrics: dict[str, Any] | None = Field(
        default=None, description="Voice metrics if voice answer"
    )
    parent_question_id: UUID | None = Field(
        default=None, description="Parent question ID if this is a follow-up"
    )
    followup_count: int = Field(default=0, description="Current follow-up count")
    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Accumulated concept gaps"
    )
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list, description="Previous Q&A messages"
    )
    evaluations: list[dict[str, Any]] = Field(
        default_factory=list, description="Previous evaluations for context"
    )
    cached_interview: dict[str, Any] | None = Field(
        default=None, description="Cached interview for performance"
    )

    model_config = {"extra": "forbid"}


class EvaluateAnswerOutput(BaseModel):
    """Output from EvaluateAnswerUseCase.

    Contains saved answer, evaluation, and optional follow-up suggestion.
    """

    answer: dict[str, Any] = Field(description="Saved answer (Answer.model_dump)")
    evaluation: dict[str, Any] = Field(
        description="Saved evaluation (Evaluation.model_dump)"
    )
    followup_suggestion: dict[str, Any] | None = Field(
        default=None, description="Cached follow-up suggestion from unified analysis"
    )
    cache_updates: dict[str, Any] = Field(
        default_factory=dict, description="Interview cache updates to merge into state"
    )

    model_config = {"extra": "forbid"}
