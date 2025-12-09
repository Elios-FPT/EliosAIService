"""Interview workflow DTOs.

Input/Output DTOs for interview use cases extracted from workflow nodes.
"""

from .start_session_dto import StartSessionInput, StartSessionOutput
from .evaluate_answer_dto import EvaluateAnswerInput, EvaluateAnswerOutput
from .validate_gaps_dto import ValidateGapsInput, ValidateGapsOutput
from .update_memory_dto import UpdateMemoryInput, UpdateMemoryOutput
from .decide_followup_dto import DecideFollowupInput, DecideFollowupOutput
from .generate_followup_dto import GenerateFollowupInput, GenerateFollowupOutput
from .load_next_question_dto import LoadNextQuestionInput, LoadNextQuestionOutput

__all__ = [
    # Start session
    "StartSessionInput",
    "StartSessionOutput",
    # Evaluate answer
    "EvaluateAnswerInput",
    "EvaluateAnswerOutput",
    # Validate gaps
    "ValidateGapsInput",
    "ValidateGapsOutput",
    # Update memory
    "UpdateMemoryInput",
    "UpdateMemoryOutput",
    # Decide followup
    "DecideFollowupInput",
    "DecideFollowupOutput",
    # Generate followup
    "GenerateFollowupInput",
    "GenerateFollowupOutput",
    # Load next question
    "LoadNextQuestionInput",
    "LoadNextQuestionOutput",
]
