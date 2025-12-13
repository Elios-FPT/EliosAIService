"""LangChain adapter implementation of LLMPort.

This adapter uses LangChain LCEL (Expression Language) chains to implement
all LLMPort methods with structured outputs and cleaner code.
"""

import asyncio
import json
import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from src.domain.models.evaluation import FollowUpEvaluationContext
from src.domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackResult,
    InputType,
)
from src.domain.models.prompt_template import PromptTemplate
from src.domain.models.question import Question
from src.application.ports.llm_port import LLMPort
from src.application.ports.prompt_repository_port import PromptRepositoryPort
from .execution_logger import ExecutionLogger
from .comprehensive_models import ComprehensiveAnalysis
from .feedback_models import CVFeedbackAnalysis, CodeFeedbackAnalysis

logger = logging.getLogger(__name__)


class MetadataCaptureCallback(AsyncCallbackHandler):
    """Callback to capture token usage metadata from LangChain LLM responses.

    When using chains with JSON output parser, the final response is just a dict
    and metadata is lost. This callback captures metadata from the LLM step
    before JSON parsing.
    """

    def __init__(self):
        super().__init__()
        self.metadata: dict[str, Any] | None = None
        self.model_name: str | None = None

    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Capture metadata when LLM call completes.

        Args:
            response: LLMResult object containing generations and llm_output
        """
        from langchain_core.outputs import LLMResult

        if not isinstance(response, LLMResult):
            return

        # Initialize metadata dict
        if not self.metadata:
            self.metadata = {}

        # First, check llm_output (contains token usage for some providers)
        if response.llm_output:
            self.metadata.update(response.llm_output)
            # Extract model name if available
            if not self.model_name:
                self.model_name = response.llm_output.get("model_name") or response.llm_output.get("model")

        # Most importantly, check generations for response_metadata (AIMessage objects)
        # This is where token usage is typically stored for OpenAI/Anthropic
        if response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "message"):
                        message = gen.message

                        # Check response_metadata (primary source for token usage)
                        if hasattr(message, "response_metadata") and message.response_metadata:
                            # Merge response_metadata (contains usage dict)
                            self.metadata.update(message.response_metadata)

                            # Extract model name from message metadata
                            if not self.model_name:
                                self.model_name = message.response_metadata.get("model_name") or message.response_metadata.get("model")

                        # Check for usage_metadata (newer LangChain versions)
                        if hasattr(message, "usage_metadata") and message.usage_metadata:
                            # Ensure usage dict exists
                            if "usage" not in self.metadata:
                                self.metadata["usage"] = {}
                            # Merge usage_metadata into usage dict
                            if isinstance(message.usage_metadata, dict):
                                self.metadata["usage"].update(message.usage_metadata)
                            else:
                                # If usage_metadata is an object, try to convert
                                self.metadata["usage"].update(vars(message.usage_metadata))


class LangChainAdapter(LLMPort):
    """LangChain implementation of LLM port.

    Uses LCEL chains for cleaner code and structured outputs.
    All LangChain-specific logic is contained in this adapter.

    Supports optional DB-based prompt management for version control
    and A/B testing of prompts.
    """

    def __init__(
        self,
        model: BaseChatModel,
        callbacks: list[Any] | None = None,
        prompt_repository: PromptRepositoryPort | None = None,
    ):
        """Initialize LangChain adapter.

        Args:
            model: LangChain chat model (ChatOpenAI, ChatAnthropic, etc.)
            callbacks: Optional list of LangChain callbacks (e.g., PIIFilteringTracer)
            prompt_repository: Optional prompt repository for DB-managed prompts
        """
        self.model = model
        self.callbacks = callbacks or []
        self.prompt_repo = prompt_repository
        self._db_chain_cache: dict[str, Runnable] = {}

    def _get_or_build_chain(
        self,
        method_name: str,
        prompt_template: PromptTemplate,
        cache_key: str | None = None,
        structured_output_model: type[Any] | None = None,
    ) -> Runnable:
        """Return cached chain built from DB template (no registry fallback).

        Args:
            method_name: Method name for caching
            prompt_template: Prompt template from DB
            cache_key: Optional cache key override
            structured_output_model: Optional Pydantic model for structured output
        """
        cache_identifier = (
            f"{method_name}:{cache_key or f'{prompt_template.prompt_name}:v{prompt_template.version}'}"
        )
        if cache_identifier in self._db_chain_cache:
            return self._db_chain_cache[cache_identifier]

        prompt_template_obj = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_template.system_prompt),
                ("human", prompt_template.user_template),
            ]
        )

        if prompt_template.partial_variables:
            prompt_template_obj = prompt_template_obj.partial(**prompt_template.partial_variables)

        # Bind model parameters per template
        bound_model = self.model.bind(
            temperature=float(prompt_template.temperature),
            # TODO: Uncomment this when we have a way to set max_tokens
            # max_tokens=prompt_template.max_tokens,
            top_p=float(prompt_template.top_p),
            frequency_penalty=float(prompt_template.frequency_penalty),
            presence_penalty=float(prompt_template.presence_penalty),
        )

        # Use structured output if model provided or for specific methods
        if structured_output_model:
            structured_model = bound_model.with_structured_output(structured_output_model)
            chain = prompt_template_obj | structured_model
        elif method_name == "comprehensive_answer_analysis":
            structured_model = bound_model.with_structured_output(ComprehensiveAnalysis)
            chain = prompt_template_obj | structured_model
        else:
            chain = prompt_template_obj | bound_model | JsonOutputParser()

        self._db_chain_cache[cache_identifier] = chain
        return chain

    def _extract_followup_question_text(self, raw_result: Any) -> str:
        """Normalize follow-up question output to plain text."""
        if isinstance(raw_result, dict):
            question_text = raw_result.get("question_text", "")
            return question_text.strip() if isinstance(question_text, str) else ""

        if raw_result is None:
            return ""

        text = raw_result.strip() if isinstance(raw_result, str) else str(raw_result).strip()
        if not text:
            return ""

        # Attempt to parse JSON payload if the model returned structured text
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                candidate = parsed.get("question_text")
                if isinstance(candidate, str):
                    return candidate.strip()
        except json.JSONDecodeError:
            pass

        return text

    @staticmethod
    def _sanitize_followup_question_text(text: str) -> str:
        """Remove LangChain troubleshooting hints or stray quotes."""
        if not text:
            return ""

        sanitized = text
        troubleshooting_marker = "For troubleshooting, visit:"
        if troubleshooting_marker in sanitized:
            sanitized = sanitized.split(troubleshooting_marker, 1)[0]

        sanitized = sanitized.strip().strip('"').strip("'")
        return sanitized

    async def _load_prompt_from_db(
        self,
        prompt_name: str,
    ) -> tuple[PromptTemplate, str | None]:
        """Load prompt from DB (required, no fallback).

        Args:
            prompt_name: DB prompt identifier (e.g., "ideal_answer_generation")

        Returns:
            Tuple of (prompt_template, cache_key)

        Example:
            prompt_template, cache_key = await self._load_prompt_from_db("answer_evaluation")
            chain = self._get_or_build_chain("evaluate_answer", prompt_template, cache_key)
        """
        if not self.prompt_repo:
            raise RuntimeError(
                f"Prompt repository is not configured; cannot load prompt '{prompt_name}'."
            )

        try:
            prompt_template = await self.prompt_repo.get_active_prompt(prompt_name)
            if not prompt_template:
                raise LookupError(f"No active prompt found for '{prompt_name}'.")

            cache_key = f"{prompt_template.prompt_name}:v{prompt_template.version}"
            return prompt_template, cache_key

        except Exception as exc:
            logger.error(
                "Failed loading DB prompt for '%s': %s.",
                prompt_name,
                exc,
                exc_info=True,
            )
            raise

    def _create_config(
        self, context: dict[str, Any] | None = None, **metadata_kwargs: Any
    ) -> RunnableConfig:
        """Create RunnableConfig with metadata for tracing.

        Args:
            context: Context dictionary that may contain interview_id, candidate_id, etc.
            **metadata_kwargs: Additional metadata fields

        Returns:
            RunnableConfig with metadata and callbacks
        """
        # Build metadata dictionary (LangSmith removed, but metadata still useful for logging)
        metadata: dict[str, Any] = {}

        # Add UUIDs from context
        if context:
            if context.get("interview_id"):
                metadata["interview_id"] = str(context["interview_id"])
            if context.get("candidate_id"):
                metadata["candidate_id"] = str(context["candidate_id"])

        # Add any additional metadata
        for key, value in metadata_kwargs.items():
            if value is not None:
                metadata[key] = str(value) if isinstance(value, UUID) else value

        return RunnableConfig(metadata=metadata, callbacks=self.callbacks)

    @staticmethod
    def _validate_variables(prompt_template: PromptTemplate, variables: dict[str, Any]) -> None:
        """Ensure required variables are provided for the prompt."""
        provided = set(variables.keys()) | set(prompt_template.partial_variables.keys())
        required = set(prompt_template.input_variables)
        missing = required - provided
        if missing:
            raise ValueError(
                f"Missing variables for prompt '{prompt_template.prompt_name}': {sorted(missing)}. "
                f"Provided keys: {sorted(variables.keys())}"
            )

    async def _invoke_chain_with_metadata(
        self, chain: Runnable, variables: dict[str, Any], config: RunnableConfig | dict[str, Any] | None = None
    ) -> tuple[Any, dict[str, Any] | None]:
        """Invoke chain and capture metadata using callback.

        Args:
            chain: LangChain runnable chain to execute
            variables: Input variables for the chain
            config: Optional RunnableConfig or dict (will add metadata callback)

        Returns:
            Tuple of (result, metadata_dict)
        """
        # Create metadata capture callback
        metadata_callback = MetadataCaptureCallback()

        # Merge callbacks: existing callbacks + metadata callback
        all_callbacks = list(self.callbacks) + [metadata_callback]

        # Update config with combined callbacks
        # LangChain accepts both RunnableConfig and dict for config
        if config:
            # Handle both dict and RunnableConfig
            if isinstance(config, dict):
                # If config is a dict, create new dict with merged callbacks
                config_with_callbacks = config.copy()
                # Merge callbacks - if config already has callbacks, combine them
                existing_callbacks = config_with_callbacks.get("callbacks", [])
                if not isinstance(existing_callbacks, list):
                    existing_callbacks = [existing_callbacks] if existing_callbacks else []
                config_with_callbacks["callbacks"] = list(existing_callbacks) + all_callbacks
            else:
                # If config is RunnableConfig, create new RunnableConfig
                config_with_callbacks = RunnableConfig(
                    metadata=getattr(config, "metadata", None),
                    callbacks=all_callbacks,
                    tags=getattr(config, "tags", None),
                    run_name=getattr(config, "run_name", None),
                )
        else:
            config_with_callbacks = RunnableConfig(callbacks=all_callbacks)

        # Execute chain
        result = await chain.ainvoke(variables, config=config_with_callbacks)

        # Extract metadata from callback or response
        metadata = metadata_callback.metadata
        if not metadata:
            metadata = ExecutionLogger.extract_response_metadata(result)

        # Debug logging to help diagnose token extraction issues
        if not metadata or not metadata.get("usage"):
            logger.debug(
                f"Token metadata not found. Callback metadata keys: {list(metadata_callback.metadata.keys()) if metadata_callback.metadata else 'None'}, "
                f"Final metadata keys: {list(metadata.keys()) if metadata else 'None'}"
            )

        return result, metadata

    async def analyze_answer_comprehensive(
        self,
        question: Question,
        answer_text: str,
        context: dict[str, Any],
        followup_context: FollowUpEvaluationContext | None = None,
    ) -> ComprehensiveAnalysis:
        """Unified answer analysis (evaluation + gaps + follow-up).

        Consolidates 3 LLM calls into 1 for 46% latency reduction (Phase 2 optimization).
        Uses chain-of-thought prompting for multi-task quality.

        Args:
            question: Question entity with ideal_answer
            answer_text: Candidate's answer
            context: Interview context (interview_id, candidate_id, conversation_history)
            followup_context: Follow-up context if applicable (attempt_number, previous_scores, gaps)

        Returns:
            ComprehensiveAnalysis with evaluation + gaps + follow_up

        Raises:
            ValueError: If question has no ideal_answer
            RuntimeError: If LLM call fails after retries
        """
        start_time = time.time()

        # Validate inputs
        if not question.has_ideal_answer():
            raise ValueError(f"Question {question.id} has no ideal_answer for comprehensive analysis")

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db("comprehensive_answer_analysis")

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("comprehensive_answer_analysis", prompt_template, cache_key)

        # Build context
        attempt_number = followup_context.attempt_number if followup_context else 1
        previous_scores = followup_context.previous_scores if followup_context else []
        cumulative_gaps = (
            [gap.concept for gap in followup_context.cumulative_gaps]
            if followup_context and followup_context.cumulative_gaps
            else []
        )

        # Prepare variables
        variables = {
            "question_text": question.text,
            "ideal_answer": question.ideal_answer or "",
            "answer_text": answer_text,
            "attempt_number": attempt_number,
            "previous_scores": previous_scores,
            "cumulative_gaps": cumulative_gaps,
        }

        self._validate_variables(prompt_template, variables)

        # Create config with metadata
        config = self._create_config(
            context=context,
            question_id=str(question.id) if question.id else None,
            difficulty=(
                question.difficulty.value
                if hasattr(question.difficulty, "value")
                else str(question.difficulty)
            ),
            skills=", ".join(question.skills) if question.skills else "General",
            method="analyze_answer_comprehensive",
        )

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            # Result is already ComprehensiveAnalysis instance when using structured output
            if isinstance(result, ComprehensiveAnalysis):
                analysis = result
            else:
                # Fallback: parse dict if structured output not available
                analysis = ComprehensiveAnalysis(**result)

            # Log execution
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=analysis.model_dump_json(),
                    start_time=start_time,
                    success=True,
                    model=self.model,
                    model_response_metadata=metadata,
                )

            logger.info(
                f"Comprehensive analysis: score={analysis.evaluation.total_score:.1f}, "
                f"gaps={len(analysis.gaps)}, has_followup={analysis.follow_up is not None}, "
                f"duration={(time.time() - start_time) * 1000:.0f}ms"
            )

            return analysis

        except Exception as exc:
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    model=self.model,
                    error_message=str(exc),
                )
            logger.error(f"Comprehensive analysis failed: {exc}", exc_info=True)
            raise RuntimeError(f"Comprehensive analysis failed: {exc}") from exc

    async def analyze_feedback(
        self,
        input_type: InputType,
        feedback_input: str,
        context: dict[str, Any] | None = None,
    ) -> FeedbackResult:
        """Analyze feedback using DB prompts.

        Args:
            input_type: CV or CODE only
            feedback_input: JSON string with entity content
            context: Optional context

        Returns:
            CVFeedbackResult or CodeReviewFeedbackResult

        Raises:
            ValueError: If input_type is INTERVIEW or invalid
            RuntimeError: If LLM call fails
        """
        start_time = time.time()
        context = context or {}

        # Validate input_type
        if input_type == InputType.INTERVIEW:
            raise ValueError("INTERVIEW analysis not supported. Use CV or CODE.")

        # Determine prompt name and structured output model
        if input_type == InputType.CV:
            prompt_name = "cv_feedback"
            structured_output_model = CVFeedbackAnalysis
        else:  # CODE
            prompt_name = "code_solution_feedback"
            structured_output_model = CodeFeedbackAnalysis

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(prompt_name)

        # Get chain (uses _get_or_build_chain with structured output)
        chain = self._get_or_build_chain(
            method_name="analyze_feedback",
            prompt_template=prompt_template,
            cache_key=cache_key,
            structured_output_model=structured_output_model,
        )

        # Parse feedback_input JSON
        try:
            feedback_data = json.loads(feedback_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid feedback_input JSON: {e}") from e

        # Prepare variables based on input_type
        if input_type == InputType.CV:
            variables = {
                "cv_data": feedback_input,  # Pass raw JSON string
            }
        else:  # CODE
            variables = {
                "problem_description": feedback_data.get("problem_description", ""),
                "language": feedback_data.get("language", "python"),
                "user_code_solution": feedback_data.get("user_code_solution", ""),
            }

        self._validate_variables(prompt_template, variables)

        # Create config
        config = self._create_config(
            context=context,
            method="analyze_feedback",
            input_type=input_type.value,
        )

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            # Map LLM result to FeedbackResult
            if input_type == InputType.CV:
                feedback_result = self._map_cv_analysis_to_result(
                    analysis=result,
                    entity_id=context.get("entity_id"),
                )
            else:  # CODE
                feedback_result = self._map_code_analysis_to_result(
                    analysis=result,
                    entity_id=context.get("entity_id"),
                    language=variables.get("language", "python"),
                )

            # Log execution
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=feedback_result.model_dump_json(),
                    start_time=start_time,
                    success=True,
                    model=self.model,
                    model_response_metadata=metadata,
                )

            logger.info(
                f"Feedback analysis completed: type={input_type.value}, "
                f"duration={(time.time() - start_time) * 1000:.0f}ms"
            )

            return feedback_result

        except Exception as exc:
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    model=self.model,
                    error_message=str(exc),
                )
            logger.error(f"Feedback analysis failed: {exc}", exc_info=True)
            raise RuntimeError(f"Feedback analysis failed: {exc}") from exc

    def _map_cv_analysis_to_result(
        self,
        analysis: CVFeedbackAnalysis,
        entity_id: Any,
    ) -> CVFeedbackResult:
        """Map CVFeedbackAnalysis to CVFeedbackResult.

        Models now match prompt schema directly, so mapping is straightforward.
        """
        from uuid import UUID
        from src.domain.models.feedback_result import (
            OverallAssessment,
            SectionFeedback,
            ActionableRecommendations,
            Recommendation,
            MarketCompetitiveness,
        )

        # Convert nested models to domain models
        overall_assessment = OverallAssessment(
            overall_score=analysis.overall_assessment.overall_score,
            summary=analysis.overall_assessment.summary,
        )

        professional_summary = SectionFeedback(
            score=analysis.professional_summary.score,
            feedback=analysis.professional_summary.feedback,
            suggestions=analysis.professional_summary.suggestions,
        )

        work_experience = SectionFeedback(
            score=analysis.work_experience.score,
            feedback=analysis.work_experience.feedback,
            suggestions=analysis.work_experience.suggestions,
        )

        projects = SectionFeedback(
            score=analysis.projects.score,
            feedback=analysis.projects.feedback,
            suggestions=analysis.projects.suggestions,
        )

        skills = SectionFeedback(
            score=analysis.skills.score,
            feedback=analysis.skills.feedback,
            suggestions=analysis.skills.suggestions,
        )

        # Convert recommendations
        actionable_recommendations = ActionableRecommendations(
            high_priority=[
                Recommendation(
                    recommendation=rec.recommendation,
                    impact=rec.impact,
                    effort=rec.effort,
                )
                for rec in analysis.actionable_recommendations.high_priority
            ],
            medium_priority=[
                Recommendation(
                    recommendation=rec.recommendation,
                    impact=rec.impact,
                    effort=rec.effort,
                )
                for rec in analysis.actionable_recommendations.medium_priority
            ],
            low_priority=[
                Recommendation(
                    recommendation=rec.recommendation,
                    impact=rec.impact,
                    effort=rec.effort,
                )
                for rec in analysis.actionable_recommendations.low_priority
            ],
        )

        market_competitiveness = MarketCompetitiveness(
            assessment=analysis.market_competitiveness.assessment,
            target_roles=analysis.market_competitiveness.target_roles,
            improvement_areas=analysis.market_competitiveness.improvement_areas,
        )

        return CVFeedbackResult(
            cv_analysis_id=UUID(str(entity_id)) if entity_id else UUID(),
            overall_assessment=overall_assessment,
            professional_summary=professional_summary,
            work_experience=work_experience,
            projects=projects,
            skills=skills,
            actionable_recommendations=actionable_recommendations,
            market_competitiveness=market_competitiveness,
        )

    def _map_code_analysis_to_result(
        self,
        analysis: CodeFeedbackAnalysis,
        entity_id: Any,
        language: str,
    ) -> CodeReviewFeedbackResult:
        """Map CodeFeedbackAnalysis to CodeReviewFeedbackResult.

        Models now match prompt schema directly, so mapping is straightforward.
        """
        from src.domain.models.feedback_result import (
            OverallAssessment,
            CodeQuality,
            BestPractices,
            CodeActionableRecommendation,
        )

        # Convert nested models to domain models
        overall_assessment = OverallAssessment(
            overall_score=analysis.overall_assessment.overall_score,
            summary=analysis.overall_assessment.summary,
        )

        code_quality = CodeQuality(
            score=analysis.code_quality.score,
            feedback=analysis.code_quality.feedback,
            suggestions=analysis.code_quality.suggestions,
        )

        best_practices = BestPractices(
            score=analysis.best_practices.score,
            feedback=analysis.best_practices.feedback,
            principles_violated=analysis.best_practices.principles_violated,
            principles_followed=analysis.best_practices.principles_followed,
            suggestions=analysis.best_practices.suggestions,
        )

        actionable_recommendations = CodeActionableRecommendation(
            recommendation=analysis.actionable_recommendations.recommendation,
            impact=analysis.actionable_recommendations.impact,
            effort=analysis.actionable_recommendations.effort,
            line_reference=analysis.actionable_recommendations.line_reference,
        )

        return CodeReviewFeedbackResult(
            submission_id=str(entity_id) if entity_id else "",
            language=language,
            overall_assessment=overall_assessment,
            code_quality=code_quality,
            best_practices=best_practices,
            actionable_recommendations=actionable_recommendations,
        )

    async def generate_followup_question(
        self,
        parent_question: str,
        answer_text: str,
        missing_concepts: list[str],
        severity: str,
        order: int,
        cumulative_gaps: list[str] | None = None,
        previous_follow_ups: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Generate targeted follow-up question."""
        start_time = time.time()
        context = context or {}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "follow_up_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_followup_question", prompt_template, cache_key)

        # Format cumulative context
        cumulative_context = ""
        if cumulative_gaps:
            cumulative_context = f"Cumulative Gaps (all attempts): {', '.join(cumulative_gaps)}"

        # Format previous follow-ups
        previous_context = ""
        if previous_follow_ups:
            previous_context = "Previous Follow-ups:\n"
            for i, fu in enumerate(previous_follow_ups, 1):
                previous_context += f"{i}. Q: {fu.get('question', '')}\n"
                previous_context += f"   A: {fu.get('answer', '')[:100]}...\n"

        # Determine priority concepts (first 2-3 most critical gaps)
        priority_concepts = ", ".join(missing_concepts[:3]) if missing_concepts else "None"

        # Prepare variables - must match DB template or hardcoded prompt
        variables = {
            "parent_question": parent_question,
            "answer_text": answer_text,
            "missing_concepts": ", ".join(missing_concepts),
            "severity": severity,
            "order": order,
            "cumulative_context": cumulative_context,
            "previous_context": previous_context,
            "priority_concepts": priority_concepts,
        }

        self._validate_variables(prompt_template, variables)

        # Create config with metadata
        config = self._create_config(
            context=context,
            method="generate_followup_question",
            severity=severity,
            order=order,
        )

        # Execute chain with metadata capture
        # Create callback before try block so we can access metadata even on parsing errors
        metadata_callback = MetadataCaptureCallback()
        all_callbacks = list(self.callbacks) + [metadata_callback]

        if config:
            if isinstance(config, dict):
                config_with_callbacks = config.copy()
                existing_callbacks = config_with_callbacks.get("callbacks", [])
                if not isinstance(existing_callbacks, list):
                    existing_callbacks = [existing_callbacks] if existing_callbacks else []
                config_with_callbacks["callbacks"] = list(existing_callbacks) + all_callbacks
            else:
                config_with_callbacks = RunnableConfig(
                    metadata=getattr(config, "metadata", None),
                    callbacks=all_callbacks,
                    tags=getattr(config, "tags", None),
                    run_name=getattr(config, "run_name", None),
                )
        else:
            config_with_callbacks = RunnableConfig(callbacks=all_callbacks)

        try:
            result = await chain.ainvoke(variables, config=config_with_callbacks)
            metadata = metadata_callback.metadata
            if not metadata:
                metadata = ExecutionLogger.extract_response_metadata(result)

            question_text = self._extract_followup_question_text(result)
            if not question_text:
                raise ValueError("Empty question text returned from LLM")
            question_text = self._sanitize_followup_question_text(question_text)

            # Log execution
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=question_text,
                    start_time=start_time,
                    success=True,
                    model=self.model,
                    model_response_metadata=metadata,
                )

            return question_text

        except Exception as exc:
            # Handle OutputParserException - try to extract plain text
            from langchain_core.exceptions import OutputParserException

            if isinstance(exc, OutputParserException):
                # DB template might return plain text instead of JSON
                # Extract the text from the error message
                error_msg = str(exc)
                if "Invalid json output:" in error_msg:
                    # Extract the plain text after "Invalid json output: "
                    plain_text = error_msg.split("Invalid json output:", 1)[1].strip()
                    # Remove "The error happen in:" suffix if present
                    if "\nThe error happen in:" in plain_text:
                        plain_text = plain_text.split("\nThe error happen in:")[0].strip()

                    logger.warning(
                        f"Got plain text instead of JSON from follow-up generation, using it directly: {plain_text[:100]}..."
                    )

                    # Get metadata from callback (LLM call completed, just parsing failed)
                    metadata = metadata_callback.metadata
                    if not metadata:
                        metadata = ExecutionLogger.extract_response_metadata(None)

                    # Log as successful with plain text
                    if prompt_template:
                        await ExecutionLogger.log_execution(
                            prompt_repo=self.prompt_repo,
                            prompt_template=prompt_template,
                            context=context,
                            input_variables=variables,
                            output_text=plain_text,
                            start_time=start_time,
                            success=True,
                            model=self.model,
                            model_response_metadata=metadata,
                        )

                    return self._sanitize_followup_question_text(plain_text)

            # Log other exceptions as failures
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    model=self.model,
                    error_message=str(exc),
                )
            raise

    async def generate_interview_recommendations(
        self,
        context: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Generate personalized interview recommendations."""
        start_time = time.time()

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "interview_recommendations"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain(
            "generate_interview_recommendations", prompt_template, cache_key
        )

        # Prepare variables
        variables = {
            "interview_id": context.get("interview_id", ""),
            "total_answers": context.get("total_answers", 0),
            "gap_progression": json.dumps(context.get("gap_progression", {})),
            "evaluations": json.dumps(context.get("evaluations", [])),
        }

        self._validate_variables(prompt_template, variables)

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, None)

            output = {
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "study_topics": result.get("study_topics", []),
                "technique_tips": result.get("technique_tips", []),
            }

            # Log execution
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=str(result),
                    start_time=start_time,
                    success=True,
                    model=self.model,
                    model_response_metadata=metadata,
                )

            return output

        except Exception as exc:
            if prompt_template:
                await ExecutionLogger.log_execution(
                    prompt_repo=self.prompt_repo,
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    model=self.model,
                    error_message=str(exc),
                )
            raise

    async def generate_questions_with_answers_and_rationales_batch(
        self,
        question_specs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[tuple[str, str, str]]:
        """Generate questions with ideal answers and rationales in a single LLM call per spec.

        For each question_spec, generates question, ideal_answer, and rationale together
        in one LLM call to ensure consistency.
        """
        start_time = time.time()

        # Load DB prompt dedicated to question + answer + rationale generation
        prompt_template, cache_key = await self._load_prompt_from_db(
            "generate_question_set"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain(
            "generate_questions_with_answers_and_rationales_batch", prompt_template, cache_key
        )

        # When DB prompt is active, it expects aggregated variables identical to batch question generation.
        if prompt_template:
            questions_section = ""
            for idx, spec in enumerate(question_specs, 1):
                skill = spec.get("skill", "general knowledge")
                difficulty = spec.get("difficulty", "medium")
                exemplars = spec.get("exemplars") or []

                questions_section += f"\n\nQuestion {idx}:\n"
                questions_section += f"- Skill to test: {skill}\n"
                questions_section += f"- Difficulty: {difficulty}\n"
                questions_section += "- Deliverables: Provide question_text, a 150-300 word ideal_answer, and a 50-100 word question rationale.\n"

                if exemplars:
                    questions_section += "- Similar questions for inspiration (do NOT copy exactly):\n"
                    for j, exemplar in enumerate(exemplars[:3], 1):
                        questions_section += (
                            f"  {j}. \"{exemplar.get('text', '')}\" ({exemplar.get('difficulty', 'UNKNOWN')})\n"
                        )

            skills = context.get("skills")
            if not skills:
                skills = list({spec.get("skill", "general knowledge") for spec in question_specs})

            chain_input = {
                "question_count": len(question_specs),
                "summary": context.get("summary") or context.get("cv_summary", "Not provided"),
                "skills": ", ".join(skills[:10]) if isinstance(skills, list) else skills,
                "experience": context.get("experience", context.get("experience_years", "Not specified")),
                "questions_section": questions_section.strip(),
            }

            self._validate_variables(prompt_template, chain_input)

            result, metadata = await self._invoke_chain_with_metadata(chain, chain_input, None)

            raw_sets = []
            if isinstance(result, dict):
                raw_sets = (
                    result.get("question_sets")
                    or result.get("questions")
                    or result.get("items")
                    or []
                )
            elif isinstance(result, list):
                raw_sets = result

            if not isinstance(raw_sets, list) or not raw_sets:
                raise ValueError("Expected list of question objects in response.")

            question_sets = []
            for item in raw_sets:
                if isinstance(item, dict):
                    question_text = (item.get("question_text") or item.get("question") or "").strip()
                    ideal_answer = (item.get("ideal_answer") or item.get("answer") or "").strip()
                    rationale = (
                        item.get("question_rationale")
                        or item.get("rationale")
                        or item.get("reasoning")
                        or ""
                    ).strip()
                elif isinstance(item, (list, tuple)) and len(item) >= 3:
                    question_text = str(item[0]).strip()
                    ideal_answer = str(item[1]).strip()
                    rationale = str(item[2]).strip()
                else:
                    raise ValueError(f"Unrecognized question set format: {item}")

                if not question_text or not ideal_answer or not rationale:
                    raise ValueError("Incomplete question set returned from LLM.")

                question_sets.append((question_text, ideal_answer, rationale))

            if len(question_sets) != len(question_specs):
                raise ValueError(
                    f"Expected {len(question_specs)} question sets, got {len(question_sets)}"
                )

            await ExecutionLogger.log_execution(
                prompt_repo=self.prompt_repo,
                prompt_template=prompt_template,
                context=context,
                input_variables={"question_specs_count": len(question_specs)},
                output_text=str(question_sets),
                start_time=start_time,
                success=True,
                model=self.model,
                model_response_metadata=metadata,
            )

            return question_sets

        # Fallback prompt path: generate per spec using legacy template
        coroutines = []
        for spec in question_specs:
            exemplar_section = ""
            exemplars = spec.get("exemplars")
            if exemplars:
                exemplar_section = "Similar questions for inspiration (do NOT copy exactly):\n"
                for j, ex in enumerate(exemplars[:3], 1):
                    exemplar_section += (
                        f"{j}. \"{ex.get('text', '')}\" ({ex.get('difficulty', 'UNKNOWN')})\n"
                    )
                exemplar_section += (
                    "\nGenerate a NEW question inspired by the style and structure above.\n"
                )

            chain_input = {
                "skill": spec["skill"],
                "difficulty": spec["difficulty"],
                "cv_summary": context.get("cv_summary", "Not provided"),
                "covered_topics": context.get("covered_topics", []),
                "stage": context.get("stage", "early"),
                "exemplar_section": exemplar_section,
            }

            coroutines.append(self._invoke_chain_with_metadata(chain, chain_input, None))

        results_with_metadata = await asyncio.gather(*coroutines)

        question_sets = []
        aggregated_metadata = self._aggregate_metadata([meta for _, meta in results_with_metadata])
        for result, _ in results_with_metadata:
            question_text = result.get("question_text", "").strip()
            ideal_answer = result.get("ideal_answer", "").strip()
            rationale = result.get("rationale", "").strip()

            if not question_text or not ideal_answer or not rationale:
                raise ValueError(
                    f"Incomplete response from LLM: missing question_text, ideal_answer, or rationale. "
                    f"Got: question_text={bool(question_text)}, ideal_answer={bool(ideal_answer)}, "
                    f"rationale={bool(rationale)}"
                )

            question_sets.append((question_text, ideal_answer, rationale))

        if len(question_sets) != len(question_specs):
            raise ValueError(
                f"Expected {len(question_specs)} question sets, got {len(question_sets)}"
            )

        return question_sets

    def _aggregate_metadata(self, metadata_list: list[dict[str, Any] | None]) -> dict[str, Any] | None:
        """Aggregate metadata from multiple LLM calls (for batch operations).

        Sums up token counts and merges other metadata fields.

        Args:
            metadata_list: List of metadata dicts from multiple calls

        Returns:
            Aggregated metadata dict, or None if no metadata available
        """
        if not metadata_list or all(m is None for m in metadata_list):
            return None

        aggregated = {}
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0

        # Aggregate token usage
        for metadata in metadata_list:
            if not metadata:
                continue

            # Merge non-token fields (use first non-None value)
            for key, value in metadata.items():
                if key not in ("usage", "token_usage") and key not in aggregated:
                    aggregated[key] = value

            # Extract and sum tokens
            usage = metadata.get("usage") or metadata.get("token_usage")
            if usage and isinstance(usage, dict):
                # OpenAI format
                if "prompt_tokens" in usage:
                    total_prompt_tokens += usage.get("prompt_tokens", 0)
                    total_completion_tokens += usage.get("completion_tokens", 0)
                    total_tokens += usage.get("total_tokens", 0)
                # Anthropic format
                elif "input_tokens" in usage:
                    total_prompt_tokens += usage.get("input_tokens", 0)
                    total_completion_tokens += usage.get("output_tokens", 0)
                    total_tokens += usage.get("total_tokens", 0) or (total_prompt_tokens + total_completion_tokens)

        # Add aggregated usage
        if total_tokens > 0 or total_prompt_tokens > 0 or total_completion_tokens > 0:
            aggregated["usage"] = {
                "total_tokens": total_tokens if total_tokens > 0 else (total_prompt_tokens + total_completion_tokens),
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
            }

        return aggregated if aggregated else None

