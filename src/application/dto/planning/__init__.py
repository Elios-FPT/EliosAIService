"""Planning workflow DTOs.

Input/Output DTOs for planning use cases extracted from workflow nodes.
"""

from .load_cv_analysis_dto import LoadCVAnalysisInput, LoadCVAnalysisOutput
from .calculate_question_count_dto import (
    CalculateQuestionCountInput,
    CalculateQuestionCountOutput,
)
from .prepare_question_specs_dto import (
    PrepareQuestionSpecsInput,
    PrepareQuestionSpecsOutput,
    QuestionSpec,
)
from .generate_questions_batch_dto import (
    GenerateQuestionsBatchInput,
    GenerateQuestionsBatchOutput,
)
from .store_questions_dto import StoreQuestionsInput, StoreQuestionsOutput
from .create_interview_dto import CreateInterviewInput, CreateInterviewOutput

__all__ = [
    # Load CV analysis
    "LoadCVAnalysisInput",
    "LoadCVAnalysisOutput",
    # Calculate question count
    "CalculateQuestionCountInput",
    "CalculateQuestionCountOutput",
    # Prepare question specs
    "PrepareQuestionSpecsInput",
    "PrepareQuestionSpecsOutput",
    "QuestionSpec",
    # Generate questions batch
    "GenerateQuestionsBatchInput",
    "GenerateQuestionsBatchOutput",
    # Store questions
    "StoreQuestionsInput",
    "StoreQuestionsOutput",
    # Create interview
    "CreateInterviewInput",
    "CreateInterviewOutput",
]
