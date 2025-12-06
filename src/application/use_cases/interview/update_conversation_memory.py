"""Update conversation memory use case.

Extracted from InterviewConversationWorkflow._update_memory_node.
Appends Q&A to conversation memory with truncation.
"""

import logging

from ..dto.interview.update_memory_dto import UpdateMemoryInput, UpdateMemoryOutput

logger = logging.getLogger(__name__)


class UpdateConversationMemoryUseCase:
    """Append Q&A to conversation memory with truncation.

    Adds question and answer to conversation history, truncates to last 10 messages.
    Extracted from InterviewConversationWorkflow._update_memory_node.
    """

    async def execute(self, input: UpdateMemoryInput) -> UpdateMemoryOutput:
        """Execute memory update.

        Args:
            input: Update memory input data

        Returns:
            UpdateMemoryOutput with updated (truncated) messages list
        """
        messages = input.messages.copy()

        # Add question (AI message)
        current_question_dict = input.current_question
        if not current_question_dict:
            logger.warning("No current question in input for memory update")
            return UpdateMemoryOutput(
                messages=input.messages,
                truncated=False,
                errors=["No current question"],
            )

        messages.append(
            {
                "type": "ai",
                "content": current_question_dict.get("text", ""),
                "additional_kwargs": {
                    "question_id": input.current_question_id,
                    "question_type": current_question_dict.get("question_type"),
                },
            }
        )

        # Add answer (Human message)
        latest_answer = input.latest_answer
        if not latest_answer:
            logger.warning("No latest answer in input for memory update")
            return UpdateMemoryOutput(
                messages=input.messages,
                truncated=False,
                errors=["No latest answer"],
            )

        latest_evaluation = input.latest_evaluation or {}
        messages.append(
            {
                "type": "human",
                "content": latest_answer.get("text", ""),
                "additional_kwargs": {
                    "answer_id": latest_answer.get("id"),
                    "score": latest_evaluation.get("final_score", 0.0),
                },
            }
        )

        # Truncate to last N messages (from Phase 0 benchmark)
        max_messages = 10  # 5 Q&A pairs
        truncated = False
        if len(messages) > max_messages:
            logger.info(f"Truncating conversation memory from {len(messages)} to {max_messages}")
            messages = messages[-max_messages:]
            truncated = True

        return UpdateMemoryOutput(
            messages=messages,
            truncated=truncated,
            errors=[],
        )

