"""Interview session orchestrator - stateless coordinator for interview flow.

REFACTORED: Removed dual state machines (SessionState + InterviewStatus).
Now relies solely on domain Interview entity for state management.
Orchestrator loads fresh state from DB before each operation.
"""

import base64
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.use_cases.complete_interview import CompleteInterviewUseCase
from ....application.use_cases.follow_up_decision import FollowUpDecisionUseCase
from ....application.use_cases.get_next_question import GetNextQuestionUseCase
from ....application.use_cases.process_answer_adaptive import (
    ProcessAnswerAdaptiveUseCase,
)
from ....domain.models.answer import Answer
from ....domain.models.evaluation import Evaluation
from ....domain.models.follow_up_question import FollowUpQuestion
from ....domain.ports.answer_repository_port import AnswerRepositoryPort
from ....domain.ports.follow_up_question_repository_port import (
    FollowUpQuestionRepositoryPort,
)
from ....domain.ports.interview_repository_port import InterviewRepositoryPort
from ....domain.ports.question_repository_port import QuestionRepositoryPort
from ....domain.ports.evaluation_repository_port import EvaluationRepositoryPort
from ....infrastructure.database.session import get_async_session

logger = logging.getLogger(__name__)


class InterviewSessionOrchestrator:
    """Stateless orchestrator for interview session flow.

    This orchestrator coordinates interview flow by delegating state management
    to the domain Interview entity:
    - Loads fresh interview state from DB before operations
    - Uses domain methods for state transitions (start, ask_followup, proceed_to_next_question)
    - No in-memory state tracking (stateless)
    - WebSocket message coordination and TTS generation

    The domain Interview entity is the single source of truth for all state.
    """

    def __init__(
        self,
        interview_id: UUID,
        websocket: WebSocket,
        container: Any,
    ):
        """Initialize session orchestrator.

        Args:
            interview_id: Interview UUID
            websocket: WebSocket connection
            container: Dependency injection container
        """
        self.interview_id = interview_id
        self.websocket = websocket
        self.container = container
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

        logger.info(
            f"Session orchestrator created for interview {interview_id}",
            extra={"interview_id": str(interview_id)},
        )

    async def start_session(self) -> None:
        """Start interview session by sending first question.

        Delegates state management to domain Interview entity.

        Raises:
            ValueError: If interview not found, already started, or no questions
        """
        async for session in get_async_session():
            interview_repo = self.container.interview_repository_port(session)
            question_repo = self.container.question_repository_port(session)
            tts = self.container.text_to_speech_port()

            # Load fresh interview state from DB
            interview = await interview_repo.get_by_id(self.interview_id)
            if not interview:
                logger.error(f"Interview {self.interview_id} not found")
                await self._send_error("INTERVIEW_NOT_FOUND", "Interview not found")
                raise ValueError(f"Interview {self.interview_id} not found")

            # Get first question
            use_case = GetNextQuestionUseCase(
                interview_repository=interview_repo,
                question_repository=question_repo,
            )
            question = await use_case.execute(self.interview_id)

            if not question:
                logger.error(f"No questions available for interview {self.interview_id}")
                await self._send_error("NO_QUESTIONS", "No questions available")
                raise ValueError(f"No questions available for interview {self.interview_id}")

            # Use domain method for state transition (IDLE → QUESTIONING)
            interview.start()
            await interview_repo.update(interview)

            # Generate TTS audio
            audio_bytes = await tts.synthesize_speech(question.text)
            audio_data = base64.b64encode(audio_bytes).decode("utf-8")

            # Send question message
            await self._send_message(
                {
                    "type": "question",
                    "question_id": str(question.id),
                    "text": question.text,
                    "question_type": question.question_type,
                    "difficulty": question.difficulty,
                    "index": interview.current_question_index,
                    "total": len(interview.question_ids),
                    "audio_data": audio_data,
                }
            )

            logger.info(
                f"Started interview, sent first question: {question.id}",
                extra={
                    "interview_id": str(self.interview_id),
                    "question_id": str(question.id),
                    "status": interview.status.value,
                },
            )
            break

    async def handle_answer(self, answer_text: str) -> None:
        """Handle answer based on interview state from DB.

        Loads fresh interview state to determine if answering main question or follow-up.

        Args:
            answer_text: Candidate's answer text

        Raises:
            ValueError: If called in invalid state
        """
        async for session in get_async_session():
            interview_repo = self.container.interview_repository_port(session)

            # Load fresh state from DB
            interview = await self._get_interview_or_raise(interview_repo)

            # Route based on domain status
            from ....domain.models.interview import InterviewStatus

            if interview.status == InterviewStatus.QUESTIONING:
                await self._handle_main_question_answer(answer_text)
            elif interview.status == InterviewStatus.FOLLOW_UP:
                await self._handle_followup_answer(answer_text)
            else:
                raise ValueError(
                    f"Cannot handle answer in status {interview.status}. "
                    f"Expected QUESTIONING or FOLLOW_UP"
                )
            break

    async def handle_voice_answer(
        self,
        audio_bytes: bytes,
        question_id: UUID,
        transcription: str,
        voice_metrics: dict[str, float],
    ) -> None:
        """Handle voice answer with STT transcription and voice metrics.

        Similar to handle_answer but specifically for voice answers with metrics.

        Args:
            audio_bytes: Raw audio data (for future storage if needed)
            question_id: Question ID being answered
            transcription: STT transcription of audio
            voice_metrics: Voice quality metrics (intonation, fluency, confidence, WPM)

        Raises:
            ValueError: If called in invalid state
        """
        async for session in get_async_session():
            interview_repo = self.container.interview_repository_port(session)

            # Load fresh state from DB
            interview = await self._get_interview_or_raise(interview_repo)

            # Route based on domain status
            from ....domain.models.interview import InterviewStatus

            if interview.status == InterviewStatus.QUESTIONING:
                await self._handle_main_question_answer(
                    answer_text=transcription,
                    voice_metrics=voice_metrics,
                )
            elif interview.status == InterviewStatus.FOLLOW_UP:
                await self._handle_followup_answer(
                    answer_text=transcription,
                    voice_metrics=voice_metrics,
                )
            else:
                raise ValueError(
                    f"Cannot handle voice answer in status {interview.status}. "
                    f"Expected QUESTIONING or FOLLOW_UP"
                )
            break

    async def _handle_main_question_answer(
        self,
        answer_text: str,
        voice_metrics: dict[str, float] | None = None,
    ) -> None:
        """Handle answer to main question.

        Flow (Phase 3A - Workflow):
        - Use AdaptiveEvalSimpleWorkflow if feature flag enabled
        - Workflow evaluates answer + decides follow-up + generates question
        - Send results back to client

        Flow (Legacy):
        1. Load interview state, get current question ID
        2. Process answer (triggers QUESTIONING → EVALUATING via domain)
        3. Make follow-up decision
        4. Either send follow-up OR next main question OR complete

        Args:
            answer_text: Candidate's answer text
            voice_metrics: Optional voice quality metrics
        """
        from ....infrastructure.config.settings import get_settings
        settings = get_settings()

        async for session in get_async_session():
            interview_repo = self.container.interview_repository_port(session)
            question_repo = self.container.question_repository_port(session)
            answer_repo = self.container.answer_repository_port(session)
            follow_up_repo = self.container.follow_up_question_repository(session)
            evaluation_repo = self.container.evaluation_repository_port(session)

            # Load fresh interview state
            interview = await self._get_interview_or_raise(interview_repo)
            interview.mark_evaluating()
            await interview_repo.update(interview)

            # Get current question ID from interview
            current_question_id = interview.get_current_question_id()
            if not current_question_id:
                raise ValueError("No current question in interview")

            # Phase 3B: Use interrupt workflow if enabled (takes precedence)
            if settings.use_langgraph_adaptive_interrupt:
                await self._handle_with_interrupt_workflow(
                    answer_text=answer_text,
                    voice_metrics=voice_metrics,
                    current_question_id=current_question_id,
                    session=session,
                )
                break

            # Phase 3A: Use simple workflow if feature flag enabled
            if settings.use_langgraph_adaptive_simple:
                await self._handle_with_workflow(
                    answer_text=answer_text,
                    voice_metrics=voice_metrics,
                    current_question_id=current_question_id,
                    session=session,
                )
                break

            # Legacy path: Use original use cases
            # Process answer with adaptive evaluation (triggers state transition inside use case)
            use_case = ProcessAnswerAdaptiveUseCase(
                answer_repository=answer_repo,
                evaluation_repository=evaluation_repo,
                interview_repository=interview_repo,
                question_repository=question_repo,
                follow_up_question_repository=follow_up_repo,
                llm=self.container.llm_port(),
                vector_search=self.container.vector_search_port(),
            )

            answer, evaluation, has_more = await use_case.execute(
                interview_id=self.interview_id,
                question_id=current_question_id,
                answer_text=answer_text,
                voice_metrics=voice_metrics,
            )

            # Send evaluation
            await self._send_evaluation(answer, evaluation)

            # Reload interview (state may have changed in use case)
            interview = await self._get_interview_or_raise(interview_repo)

            # Make follow-up decision
            decision_use_case = FollowUpDecisionUseCase(
                answer_repository=answer_repo,
                evaluation_repository=evaluation_repo,
                follow_up_question_repository=follow_up_repo,
            )

            decision = await decision_use_case.execute(
                interview_id=self.interview_id,
                parent_question_id=current_question_id,  # Current question is the parent
                latest_answer=answer,
                latest_evaluation=evaluation,
            )

            logger.info(
                f"Follow-up decision: needs={decision['needs_followup']}, "
                f"reason='{decision['reason']}', count={decision['follow_up_count']}"
            )

            # If follow-up needed, generate and send
            if decision["needs_followup"]:
                await self._generate_and_send_followup(
                    answer,
                    evaluation,
                    decision,
                    question_repo,
                    follow_up_repo,
                    interview_repo,
                    current_question_id,
                )
                break

            # No follow-up needed - send next main question or complete
            if has_more:
                await self._send_next_main_question(interview_repo, question_repo)
            else:
                await self._complete_interview(
                    interview_repo, answer_repo, question_repo, follow_up_repo, evaluation_repo
                )

            break

    async def _handle_followup_answer(
        self,
        answer_text: str,
        voice_metrics: dict[str, float] | None = None,
    ) -> None:
        """Handle answer to follow-up question.

        Flow:
        1. Load interview state, get parent question ID and last follow-up ID
        2. Process answer (triggers FOLLOW_UP → EVALUATING via domain)
        3. Make follow-up decision again (may generate another follow-up)
        4. Either send another follow-up OR next main question OR complete

        Args:
            answer_text: Candidate's answer text
            voice_metrics: Optional voice quality metrics for voice answers
        """
        async for session in get_async_session():
            interview_repo = self.container.interview_repository_port(session)
            question_repo = self.container.question_repository_port(session)
            answer_repo = self.container.answer_repository_port(session)
            follow_up_repo = self.container.follow_up_question_repository(session)
            evaluation_repo = self.container.evaluation_repository_port(session)

            # Load fresh interview state
            interview = await self._get_interview_or_raise(interview_repo)
            interview.mark_evaluating()
            await interview_repo.update(interview)

            # Get parent question ID and last follow-up ID from interview
            parent_question_id = interview.current_parent_question_id
            if not parent_question_id:
                raise ValueError("No parent question tracked in interview")

            # Last follow-up is the most recent in adaptive_follow_ups list
            if not interview.adaptive_follow_ups:
                raise ValueError("No follow-up questions tracked in interview")
            current_followup_id = interview.adaptive_follow_ups[-1]

            # Process answer (triggers state transition inside use case)
            use_case = ProcessAnswerAdaptiveUseCase(
                answer_repository=answer_repo,
                evaluation_repository=evaluation_repo,
                interview_repository=interview_repo,
                question_repository=question_repo,
                follow_up_question_repository=follow_up_repo,
                llm=self.container.llm_port(),
                vector_search=self.container.vector_search_port(),
            )

            answer, evaluation, has_more = await use_case.execute(
                interview_id=self.interview_id,
                question_id=current_followup_id,
                answer_text=answer_text,
                voice_metrics=voice_metrics,
            )

            # Send evaluation
            await self._send_evaluation(answer, evaluation)

            # Reload interview
            interview = await self._get_interview_or_raise(interview_repo)

            # Make follow-up decision (using parent question ID)
            decision_use_case = FollowUpDecisionUseCase(
                answer_repository=answer_repo,
                evaluation_repository=evaluation_repo,
                follow_up_question_repository=follow_up_repo,
            )

            decision = await decision_use_case.execute(
                interview_id=self.interview_id,
                parent_question_id=parent_question_id,
                latest_answer=answer,
                latest_evaluation=evaluation,
            )

            logger.info(
                f"Follow-up decision (after follow-up): needs={decision['needs_followup']}, "
                f"reason='{decision['reason']}', count={decision['follow_up_count']}"
            )

            # If another follow-up needed, generate and send
            if decision["needs_followup"]:
                await self._generate_and_send_followup(
                    answer,
                    evaluation,
                    decision,
                    question_repo,
                    follow_up_repo,
                    interview_repo,
                    parent_question_id,
                )
                break

            # No more follow-ups - send next main question or complete
            if has_more:
                await self._send_next_main_question(interview_repo, question_repo)
            else:
                await self._complete_interview(
                    interview_repo, answer_repo, question_repo, follow_up_repo, evaluation_repo
                )

            break

    async def _generate_and_send_followup(
        self,
        answer: Answer,
        evaluation: Evaluation,
        decision: dict[str, Any],
        question_repo: QuestionRepositoryPort,
        follow_up_repo: FollowUpQuestionRepositoryPort,
        interview_repo: InterviewRepositoryPort,
        parent_question_id: UUID,
    ) -> None:
        """Generate and send follow-up question using domain methods.

        Args:
            answer: Latest answer entity
            evaluation: Latest evaluation entity
            decision: Follow-up decision dict
            question_repo: Question repository
            follow_up_repo: Follow-up question repository
            interview_repo: Interview repository
            parent_question_id: UUID of parent question
        """
        # Get parent question for context
        parent_question = await question_repo.get_by_id(parent_question_id)

        # Determine severity from evaluation gaps (use highest severity, default to moderate)
        severity = "moderate"
        if evaluation.gaps:
            # Find highest severity from unresolved gaps
            # Use string comparison to avoid import issues (GapSeverity is a str Enum)
            severity_order = {"major": 3, "moderate": 2, "minor": 1}
            unresolved_gaps = [gap for gap in evaluation.gaps if not gap.resolved]
            if unresolved_gaps:
                # GapSeverity is a str Enum, so str(g.severity) gives the value
                highest_severity = max(
                    unresolved_gaps, key=lambda g: severity_order.get(str(g.severity).lower(), 0)
                )
                severity = str(highest_severity.severity)

        # Generate follow-up question with cumulative context
        follow_up_text = await self.container.llm_port().generate_followup_question(
            parent_question=parent_question.text if parent_question else "Unknown",
            answer_text=answer.text,
            missing_concepts=decision["cumulative_gaps"],
            severity=severity,
            order=decision["follow_up_count"] + 1,
            cumulative_gaps=decision["cumulative_gaps"],
        )

        # Create and save follow-up question entity
        follow_up = FollowUpQuestion(
            parent_question_id=parent_question_id,
            interview_id=self.interview_id,
            text=follow_up_text,
            generated_reason=decision["reason"],
            order_in_sequence=decision["follow_up_count"] + 1,
        )
        await follow_up_repo.save(follow_up)

        # Use domain method to track follow-up (triggers EVALUATING → FOLLOW_UP)
        interview = await self._get_interview_or_raise(interview_repo)
        interview.ask_followup(follow_up.id, parent_question_id)
        await interview_repo.update(interview)

        # Send follow-up question with audio
        tts = self.container.text_to_speech_port()
        audio_bytes = await tts.synthesize_speech(follow_up.text)
        audio_data = base64.b64encode(audio_bytes).decode("utf-8")

        await self._send_message(
            {
                "type": "follow_up_question",
                "question_id": str(follow_up.id),
                "parent_question_id": str(parent_question_id),
                "text": follow_up.text,
                "generated_reason": follow_up.generated_reason,
                "order_in_sequence": follow_up.order_in_sequence,
                "audio_data": audio_data,
            }
        )

        logger.info(
            f"Sent follow-up #{follow_up.order_in_sequence}",
            extra={
                "interview_id": str(self.interview_id),
                "follow_up_id": str(follow_up.id),
                "parent_question_id": str(parent_question_id),
            },
        )

    async def _send_next_main_question(
        self,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
    ) -> None:
        """Send next main question using domain methods.

        Args:
            interview_repo: Interview repository
            question_repo: Question repository
        """
        # Load interview and use domain method (EVALUATING → QUESTIONING, resets counters)
        interview = await self._get_interview_or_raise(interview_repo)

        interview.proceed_to_next_question()
        await interview_repo.update(interview)

        # Get next question
        use_case = GetNextQuestionUseCase(
            interview_repository=interview_repo,
            question_repository=question_repo,
        )
        question = await use_case.execute(self.interview_id)

        if not question:
            logger.warning(f"No more questions for interview {self.interview_id}")
            # Load all required dependencies for completion
            async for session in get_async_session():
                interview_repo_complete = self.container.interview_repository_port(session)
                answer_repo_complete = self.container.answer_repository_port(session)
                question_repo_complete = self.container.question_repository_port(session)
                follow_up_repo_complete = self.container.follow_up_question_repository(session)
                evaluation_repo_complete = self.container.evaluation_repository_port(session)

                await self._complete_interview(
                    interview_repo_complete,
                    answer_repo_complete,
                    question_repo_complete,
                    follow_up_repo_complete,
                    evaluation_repo_complete,
                )
                break
            return

        # Reload interview for updated index
        interview = await self._get_interview_or_raise(interview_repo)

        # Generate TTS audio
        tts = self.container.text_to_speech_port()
        audio_bytes = await tts.synthesize_speech(question.text)
        audio_data = base64.b64encode(audio_bytes).decode("utf-8")

        # Send question message
        await self._send_message(
            {
                "type": "question",
                "question_id": str(question.id),
                "text": question.text,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "index": interview.current_question_index if interview else 0,
                "total": len(interview.question_ids) if interview else 0,
                "audio_data": audio_data,
            }
        )

        logger.info(
            f"Sent next main question: {question.id}",
            extra={
                "interview_id": str(self.interview_id),
                "question_id": str(question.id),
                "status": interview.status.value if interview else "unknown",
            },
        )

    async def _complete_interview(
        self,
        interview_repo: InterviewRepositoryPort,
        answer_repo: AnswerRepositoryPort,
        question_repo: QuestionRepositoryPort,
        follow_up_repo: FollowUpQuestionRepositoryPort,
        evaluation_repo: EvaluationRepositoryPort,
    ) -> None:
        """Complete interview using domain methods, generate summary, send results.

        State transition and summary generation handled atomically by CompleteInterviewUseCase.

        Args:
            interview_repo: Interview repository (required)
            answer_repo: Answer repository (required)
            question_repo: Question repository (required)
            follow_up_repo: Follow-up question repository (required)
            evaluation_repo: Evaluation repository (required)
        """

        # Get LLM for summary generation
        llm = self.container.llm_port()

        # Complete interview with summary generation (atomic operation)
        complete_use_case = CompleteInterviewUseCase(
            interview_repository=interview_repo,
            answer_repository=answer_repo,
            question_repository=question_repo,
            follow_up_question_repository=follow_up_repo,
            evaluation_repository=evaluation_repo,
            llm=llm,
        )
        result = await complete_use_case.execute(self.interview_id)

        # Send detailed feedback to client via WebSocket
        # Serialize DetailedInterviewFeedback DTO to JSON dict
        detailed_feedback = result.summary.model_dump(mode="json")

        await self._send_message(
            {
                "type": "interview_complete",
                "interview_id": str(result.interview.id),
                "status": result.interview.status.value,
                "detailed_feedback": detailed_feedback,
                "feedback_url": f"/api/interviews/{self.interview_id}/summary",
            }
        )

        logger.info(
            f"Interview {self.interview_id} completed with detailed feedback "
            f"(payload size: ~{len(str(detailed_feedback))} bytes)"
        )

    async def _send_evaluation(self, answer: Answer, evaluation: Evaluation) -> None:
        """Send evaluation message.

        Args:
            answer: Answer entity
            evaluation: Evaluation entity with scoring data
        """
        eval_message = {
            "type": "evaluation",
            "answer_id": str(answer.id),
            "score": evaluation.final_score,
            "feedback": evaluation.reasoning,
            "strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
            "gaps": [gap.model_dump(mode="json") for gap in evaluation.gaps],
        }

        await self._send_message(eval_message)

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send message to client via WebSocket.

        Args:
            message: Message dict to send
        """
        from .connection_manager import manager

        await manager.send_message(self.interview_id, message)

    async def _send_error(self, code: str, message: str) -> None:
        """Send error message to client.

        Args:
            code: Error code
            message: Error message
        """
        await self._send_message(
            {
                "type": "error",
                "code": code,
                "message": message,
            }
        )

    async def _handle_with_workflow(
        self,
        answer_text: str,
        current_question_id: UUID,
        session: AsyncSession,
        voice_metrics: dict[str, float] | None = None,
    ) -> None:
        """Handle answer using AdaptiveEvalSimpleWorkflow (Phase 3A).

        Args:
            answer_text: Candidate's answer text
            current_question_id: Current question ID
            session: Async database session
            voice_metrics: Optional voice quality metrics
        """
        # Create workflow
        workflow = await self.container.create_adaptive_eval_simple_workflow(session)

        # Execute workflow
        result = await workflow.execute(
            interview_id=self.interview_id,
            question_id=current_question_id,
            answer_text=answer_text,
            voice_metrics=voice_metrics,
        )

        # Extract results
        evaluation = result["evaluation"]
        answer = result["answer"]
        followup_question = result.get("followup_question")
        has_more_questions = result["has_more_questions"]
        needs_followup = result["needs_followup"]

        # Send evaluation to client
        await self._send_evaluation(answer, evaluation)

        logger.info(
            f"Workflow execution complete: needs_followup={needs_followup}, "
            f"has_more={has_more_questions}"
        )

        # Handle next step based on workflow result
        if needs_followup and followup_question:
            # Send follow-up question
            await self._send_followup_question(followup_question)
        elif has_more_questions:
            # Send next main question
            interview_repo = self.container.interview_repository_port(session)
            question_repo = self.container.question_repository_port(session)
            await self._send_next_main_question(interview_repo, question_repo)
        else:
            # Complete interview
            interview_repo = self.container.interview_repository_port(session)
            answer_repo = self.container.answer_repository_port(session)
            question_repo = self.container.question_repository_port(session)
            follow_up_repo = self.container.follow_up_question_repository(session)
            evaluation_repo = self.container.evaluation_repository_port(session)

            await self._complete_interview(
                interview_repo,
                answer_repo,
                question_repo,
                follow_up_repo,
                evaluation_repo,
            )

    async def _send_followup_question(self, followup_question: FollowUpQuestion) -> None:
        """Send follow-up question to client (Phase 3A helper).

        Args:
            followup_question: Follow-up question entity
        """
        # Generate TTS audio
        tts = self.container.text_to_speech_port()
        audio_bytes = await tts.synthesize_speech(followup_question.text)
        audio_data = base64.b64encode(audio_bytes).decode("utf-8")

        # Send follow-up question message
        await self._send_message(
            {
                "type": "followup_question",
                "question_id": str(followup_question.id),
                "parent_question_id": str(followup_question.parent_question_id),
                "text": followup_question.text,
                "order": followup_question.order_in_sequence,
                "generated_reason": followup_question.generated_reason,
                "audio_data": audio_data,
            }
        )

        logger.info(
            f"Sent follow-up question {followup_question.id} (order={followup_question.order_in_sequence})"
        )

    async def _handle_with_interrupt_workflow(
        self,
        answer_text: str,
        current_question_id: UUID,
        session: AsyncSession,
        voice_metrics: dict[str, float] | None = None,
        thread_id: str | None = None,
    ) -> None:
        """Handle answer using AdaptiveEvalInterruptWorkflow (Phase 3B).

        This method implements the WebSocket interrupt pattern:
        1. Execute workflow with interrupt configuration
        2. If interrupted, send follow-up question and wait for answer
        3. Resume workflow with new answer until complete
        4. Loop up to 3 iterations (0-3 follow-ups)

        Args:
            answer_text: Candidate's answer text
            current_question_id: Current question ID
            session: Async database session
            voice_metrics: Optional voice quality metrics
            thread_id: Optional thread ID for resuming workflow
        """
        # Create workflow
        workflow = await self.container.create_adaptive_eval_interrupt_workflow(session)

        # Execute workflow (first time or resume)
        result = await workflow.execute(
            interview_id=self.interview_id,
            question_id=current_question_id,
            answer_text=answer_text,
            voice_metrics=voice_metrics,
            thread_id=thread_id,
        )

        # Check workflow status
        if result["status"] == "interrupted":
            # Workflow paused - send follow-up question
            followup_question = result["followup_question"]
            iteration = result["iteration"]
            cumulative_gaps = result["cumulative_gaps"]
            thread_id = result["thread_id"]

            logger.info(
                f"Workflow interrupted (iteration {iteration}): "
                f"sending follow-up {followup_question.id}, gaps={len(cumulative_gaps)}"
            )

            # Send follow-up question to client
            await self._send_followup_question(followup_question)

            # Store thread_id in session for resume (implementation needed)
            # TODO: Store thread_id in WebSocketSession or Interview for tracking

        elif result["status"] == "complete":
            # Workflow complete - handle final result
            evaluation = result["evaluation"]
            answer = result["answer"]
            has_more_questions = result["has_more_questions"]
            followup_questions_generated = result.get("followup_questions_generated", [])

            logger.info(
                f"Workflow complete: {len(followup_questions_generated)} follow-ups generated, "
                f"has_more={has_more_questions}"
            )

            # Send evaluation to client
            await self._send_evaluation(answer, evaluation)

            # Handle next step based on workflow result
            if has_more_questions:
                # Send next main question
                interview_repo = self.container.interview_repository_port(session)
                question_repo = self.container.question_repository_port(session)
                await self._send_next_main_question(interview_repo, question_repo)
            else:
                # Complete interview
                interview_repo = self.container.interview_repository_port(session)
                answer_repo = self.container.answer_repository_port(session)
                question_repo = self.container.question_repository_port(session)
                follow_up_repo = self.container.follow_up_question_repository(session)
                evaluation_repo = self.container.evaluation_repository_port(session)

                await self._complete_interview(
                    interview_repo,
                    answer_repo,
                    question_repo,
                    follow_up_repo,
                    evaluation_repo,
                )

    async def _get_interview_or_raise(self, interview_repo: InterviewRepositoryPort) -> Any:
        """Get interview by ID or raise ValueError if not found.

        Args:
            interview_repo: Interview repository

        Returns:
            Interview entity

        Raises:
            ValueError: If interview not found
        """
        interview = await interview_repo.get_by_id(self.interview_id)
        if not interview:
            raise ValueError(f"Interview {self.interview_id} not found")
        return interview

    async def get_state(self) -> dict[str, Any]:
        """Get current session state from DB (stateless).

        Loads fresh interview state from database.

        Returns:
            State dict with interview data from DB
        """
        async for session in get_async_session():
            interview_repo = self.container.interview_repository_port(session)
            interview = await self._get_interview_or_raise(interview_repo)

            if not interview:
                return {
                    "interview_id": str(self.interview_id),
                    "status": "NOT_FOUND",
                    "created_at": self.created_at.isoformat(),
                    "last_activity": self.last_activity.isoformat(),
                }

            return {
                "interview_id": str(self.interview_id),
                "status": interview.status.value,
                "current_question_id": (
                    str(interview.get_current_question_id())
                    if interview.get_current_question_id()
                    else None
                ),
                "parent_question_id": (
                    str(interview.current_parent_question_id)
                    if interview.current_parent_question_id
                    else None
                ),
                "followup_count": interview.current_followup_count,
                "progress": f"{interview.current_question_index}/{len(interview.question_ids)}",
                "created_at": self.created_at.isoformat(),
                "last_activity": self.last_activity.isoformat(),
            }

        # Fallback (should not reach here)
        return {
            "interview_id": str(self.interview_id),
            "error": "Failed to retrieve state",
        }
