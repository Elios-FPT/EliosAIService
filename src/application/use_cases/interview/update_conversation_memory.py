"""Update conversation memory use case.

Extracted from InterviewConversationWorkflow._update_memory_node (lines 703-759).
"""

import logging

from ...dto.interview.update_memory_dto import UpdateMemoryInput, UpdateMemoryOutput

logger = logging.getLogger(__name__)


class UpdateConversationMemoryUseCase:
    """Append Q&A to conversation memory with truncation.

    Adds question and answer to conversation history, truncates to last 10 messages.
    """

    def __init__(self) -> None:
        """Initialize use case (no dependencies required)."""
        pass

    async def execute(self, input_dto: UpdateMemoryInput) -> UpdateMemoryOutput:
        """Append Q&A to conversation memory and truncate.

        Args:
            input_dto: Contains messages, current_question, latest_answer, latest_evaluation

        Returns:
            UpdateMemoryOutput with truncated messages list
        """
        try:
            messages = list(input_dto.messages)

            # Validate inputs
            if not input_dto.current_question:
                logger.warning("No current question in input for memory update")
                return UpdateMemoryOutput(messages=messages, errors=["No current question"])

            if not input_dto.latest_answer:
                logger.warning("No latest answer in input for memory update")
                return UpdateMemoryOutput(messages=messages, errors=["No latest answer"])

            if not input_dto.latest_evaluation:
                logger.warning("No latest evaluation in input for memory update")
                return UpdateMemoryOutput(messages=messages, errors=["No latest evaluation"])

            # Add question (AI message)
            messages.append(
                {
                    "type": "ai",
                    "content": input_dto.current_question["text"],
                    "additional_kwargs": {
                        "question_id": input_dto.current_question_id,
                        "question_type": input_dto.current_question.get("question_type"),
                    },
                }
            )

            # Add answer (Human message)
            messages.append(
                {
                    "type": "human",
                    "content": input_dto.latest_answer["text"],
                    "additional_kwargs": {
                        "answer_id": input_dto.latest_answer["id"],
                        "score": input_dto.latest_evaluation["final_score"],
                    },
                }
            )

            # Truncate to last N messages
            max_messages = 10  # 5 Q&A pairs
            truncated = False
            if len(messages) > max_messages:
                logger.info(
                    f"Truncating conversation memory from {len(messages)} to {max_messages}"
                )
                messages = messages[-max_messages:]
                truncated = True

            return UpdateMemoryOutput(messages=messages, truncated=truncated)

        except Exception as exc:
            logger.error(f"update_memory failed: {exc}", exc_info=True)
            return UpdateMemoryOutput(
                messages=input_dto.messages,
                errors=[f"update_memory: {str(exc)}"],
            )
