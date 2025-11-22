"""Domain models package."""

from .answer import Answer, AnswerEvaluation
from .candidate import Candidate
from .cv_analysis import CVAnalysis
from .cv_skill import CVSkill, ProficiencyLevel
from .error_codes import WebSocketErrorCode
from .follow_up_question import FollowUpQuestion
from .interview import Interview, InterviewStatus
from .interview_question import InterviewQuestion
from .prompt_execution import PromptExecution
from .prompt_metadata_change import PromptMetadataChange
from .prompt_template import PromptTemplate
from .question import Difficulty, DifficultyLevel, Question, QuestionType

__all__ = [
    # Existing models
    "Candidate",
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
    # ENUMs
    "ProficiencyLevel",
    "QuestionType",
    "Difficulty",
    "DifficultyLevel",  # Alias for backward compatibility
]
