"""Domain models package."""

from .answer import Answer, AnswerEvaluation
from .cv_analysis import CVAnalysis
from .cv_skill import CVSkill, ProficiencyLevel
from .error_codes import WebSocketErrorCode
from .feedback_request import FeedbackRequest
from .feedback_response import FeedbackResponse
from .feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackResult,
    FeedbackStatus,
    InputType,
    InterviewFeedbackResult,
)
from .follow_up_question import FollowUpQuestion
from .interview import Interview, InterviewStatus
from .interview_question import InterviewQuestion
from .prompt_execution import PromptExecution
from .prompt_metadata_change import PromptMetadataChange
from .prompt_template import PromptTemplate
from .exemplar_models import ExemplarFilters, ExemplarResult
from .question import Difficulty, DifficultyLevel, Question, QuestionType

__all__ = [
    # Existing models
    "CVAnalysis",
    "Interview",
    "InterviewStatus",
    "Question",
    "Answer",
    "AnswerEvaluation",
    "FollowUpQuestion",
    "WebSocketErrorCode",
    "PromptTemplate",
    "PromptMetadataChange",
    "PromptExecution",
    # New models
    "CVSkill",
    "InterviewQuestion",
    # Feedback models
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackResult",
    "InterviewFeedbackResult",
    "CodeReviewFeedbackResult",
    "CVFeedbackResult",
    # ENUMs
    "ProficiencyLevel",
    "QuestionType",
    "Difficulty",
    "DifficultyLevel",  # Alias for backward compatibility
    "InputType",
    "FeedbackStatus",
    "ExemplarFilters",
    "ExemplarResult",
]
