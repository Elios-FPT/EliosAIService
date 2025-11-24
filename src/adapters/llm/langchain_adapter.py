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

from ...domain.models.answer import AnswerEvaluation
from ...domain.models.evaluation import FollowUpEvaluationContext, Evaluation
from ...domain.models.prompt_template import PromptTemplate
from ...domain.models.question import Question
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.prompt_repository_port import PromptRepositoryPort
from .prompts import PROMPT_REGISTRY

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
        self._chains = self._build_chains()
        self._db_chain_cache: dict[str, Runnable] = {}

    def _build_chains(self) -> dict[str, Any]:
        """Build all LCEL chains for the 12 LLMPort methods.

        Returns:
            Dictionary of method_name -> chain
        """
        # JSON output parser for all chains
        json_parser = JsonOutputParser()

        chains = {}

        # Build chain for each method
        for method_name, prompt_template in PROMPT_REGISTRY.items():
            # Simple chain: prompt | model | json_parser
            chains[method_name] = prompt_template | self.model | json_parser

        return chains

    def _get_or_build_chain(
        self,
        method_name: str,
        prompt_template: PromptTemplate | None = None,
        cache_key: str | None = None,
    ) -> Runnable:
        """Return cached chain or build a dynamic one from DB template."""
        if not prompt_template:
            return self._chains[method_name]

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
        json_parser = JsonOutputParser()
        chain = prompt_template_obj | self.model | json_parser
        self._db_chain_cache[cache_identifier] = chain
        return chain

    async def _load_prompt_from_db(
        self,
        prompt_name: str,
    ) -> tuple[PromptTemplate | None, str | None]:
        """Load prompt from DB with fallback.

        Args:
            prompt_name: DB prompt identifier (e.g., "ideal_answer_generation")

        Returns:
            Tuple of (prompt_template, cache_key)
            Returns (None, None) if DB unavailable or prompt not found

        Example:
            prompt_template, cache_key = await self._load_prompt_from_db("answer_evaluation")
            chain = self._get_or_build_chain("evaluate_answer", prompt_template, cache_key)
        """
        if not self.prompt_repo:
            return None, None

        try:
            prompt_template = await self.prompt_repo.get_active_prompt(prompt_name)
            if not prompt_template:
                logger.info(
                    "No active DB prompt for '%s', falling back to PROMPT_REGISTRY",
                    prompt_name,
                )
                return None, None

            cache_key = f"{prompt_template.prompt_name}:v{prompt_template.version}"
            return prompt_template, cache_key

        except Exception as exc:
            logger.warning(
                "Failed loading DB prompt for '%s': %s. Falling back to PROMPT_REGISTRY.",
                prompt_name,
                exc,
                exc_info=True,  # Include stack trace for debugging
            )
            return None, None

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
        from ...infrastructure.observability.langsmith_config import create_metadata_for_tracing

        # Extract common fields from context
        metadata = create_metadata_for_tracing(
            interview_id=context.get("interview_id") if context else None,
            candidate_id=context.get("candidate_id") if context else None,
            **metadata_kwargs,
        )

        return RunnableConfig(metadata=metadata, callbacks=self.callbacks)

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
            metadata = self._extract_response_metadata(result)

        # Debug logging to help diagnose token extraction issues
        if not metadata or not metadata.get("usage"):
            logger.debug(
                f"Token metadata not found. Callback metadata keys: {list(metadata_callback.metadata.keys()) if metadata_callback.metadata else 'None'}, "
                f"Final metadata keys: {list(metadata.keys()) if metadata else 'None'}"
            )

        return result, metadata

    async def evaluate_answer(
        self,
        question: Question,
        answer_text: str,
        context: dict[str, Any],
        followup_context: FollowUpEvaluationContext | None = None,
    ) -> AnswerEvaluation:
        """Evaluate a candidate's answer using LangChain."""
        start_time = time.time()

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "answer_evaluation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("evaluate_answer", prompt_template, cache_key)

        # Format followup context if present
        followup_context_section = ""
        if followup_context:
            followup_context_section = f"""
This is a follow-up question (attempt #{followup_context.attempt_number}).

Previous Evaluations:
{self._format_previous_evaluations(followup_context.previous_evaluations)}

Cumulative Gaps: {', '.join([str(gap.concept) for gap in followup_context.cumulative_gaps]) if followup_context.cumulative_gaps else 'None'}

Apply attempt-based penalty:
- Attempt 2: Reduce score by 10% (gaps should be addressed)
- Attempt 3+: Reduce score by 20% (repeated failure to address gaps)
"""

        # Format ideal answer section (if available from followup_context)
        ideal_answer_section = ""
        if followup_context and followup_context.parent_ideal_answer:
            ideal_answer_section = f"""
Ideal Answer Reference:
{followup_context.parent_ideal_answer}
"""

        # Format semantic similarity section (only if ideal answer exists)
        semantic_similarity_section = ""
        semantic_similarity_key = ""
        if ideal_answer_section:
            semantic_similarity_section = "\n9. Semantic similarity to ideal answer (0.0-1.0)"
            semantic_similarity_key = ", semantic_similarity"

        # Prepare variables - must match DB template or hardcoded prompt
        variables = {
            "question_text": question.text,
            "question_type": question.question_type.value if hasattr(question.question_type, "value") else str(question.question_type),
            "difficulty": question.difficulty.value if hasattr(question.difficulty, "value") else str(question.difficulty),
            "skills": ", ".join(question.skills) if question.skills else "General",
            "answer_text": answer_text,
            "ideal_answer_section": ideal_answer_section,
            "followup_context_section": followup_context_section,
            "semantic_similarity_section": semantic_similarity_section,
            "semantic_similarity_key": semantic_similarity_key,
        }

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
            method="evaluate_answer",
        )

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=str(result),  # JSON result
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            # Map to domain model with required fields
            # semantic_similarity, completeness, relevance extracted from score if not provided
            semantic_similarity = result.get("semantic_similarity", result["score"] / 100.0)
            completeness = result.get("completeness", result["score"] / 100.0)
            relevance = result.get("relevance", 1.0)  # Assume relevant if LLM provided feedback

            return AnswerEvaluation(
                score=result["score"],
                semantic_similarity=max(0.0, min(1.0, semantic_similarity)),
                completeness=max(0.0, min(1.0, completeness)),
                relevance=max(0.0, min(1.0, relevance)),
                sentiment=result.get("sentiment"),
                reasoning=result.get("feedback"),  # Map feedback to reasoning
                strengths=result.get("strengths", []),
                weaknesses=result.get("weaknesses", []),
                improvement_suggestions=result.get(
                    "missing_concepts", []
                ),  # Map missing_concepts to improvements
            )

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def generate_feedback_report(
        self,
        interview_id: UUID,
        questions: list[Question],
        answers: list[dict[str, Any]],
    ) -> str:
        """Generate comprehensive feedback report."""
        start_time = time.time()
        context = {"interview_id": str(interview_id)}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "feedback_report"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_feedback_report", prompt_template, cache_key)

        # Format questions and answers
        qa_formatted = self._format_questions_answers(questions, answers)

        # Prepare variables
        variables = {
            "interview_id": str(interview_id),
            "total_questions": len(questions),
            "questions_and_answers": qa_formatted,
        }

        # Create config with metadata
        config = self._create_config(
            context=context,
            method="generate_feedback_report",
            question_count=len(questions),
        )

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=result["report_text"],
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return result["report_text"]

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def summarize_cv(self, cv_text: str, context: dict[str, Any] | None = None) -> str:
        """Generate a summary of a CV."""
        start_time = time.time()
        context = context or {}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db("cv_summary")

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("summarize_cv", prompt_template, cache_key)

        # Prepare variables
        variables = {"cv_text": cv_text}

        # Create config with metadata
        config = self._create_config(context=context, method="summarize_cv")

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=result["summary_text"],
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return result["summary_text"]

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def extract_skills_from_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> list[dict[str, str]]:
        """Extract skills from CV text using LLM."""
        start_time = time.time()
        context = context or {}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "skill_extraction"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("extract_skills_from_text", prompt_template, cache_key)

        # Prepare variables
        variables = {"text": text}

        # Create config with metadata
        config = self._create_config(context=context, method="extract_skills_from_text")

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            # Convert to expected format
            skills = []
            for skill_item in result.get("skills", []):
                skills.append(
                    {
                        "skill": skill_item["name"],
                        "category": skill_item.get("category", ""),
                        "proficiency": skill_item.get("proficiency", ""),
                    }
                )

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=str(skills),  # JSON result
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return skills

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def generate_ideal_answer(
        self,
        question_text: str,
        context: dict[str, Any],
    ) -> str:
        """Generate ideal answer for a question."""
        start_time = time.time()

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "ideal_answer_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_ideal_answer", prompt_template, cache_key)

        variables = {
            "question_text": question_text,
            "summary": context.get("summary", context.get("cv_summary", "Not provided")),
            "skills": (
                ", ".join(context.get("skills", [])[:5])
                if context.get("skills")
                else "Not specified"
            ),
            "experience": str(context.get("experience", "Not specified")),
            "cv_summary": context.get("cv_summary", "Not provided"),
            "skill_level": context.get("skill_level", "intermediate"),
        }

        config = self._create_config(
            context=context,
            method="generate_ideal_answer",
        )

        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, config)

            output_text = result.get("answer_text") or result.get("answer")

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=output_text,
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return output_text

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def generate_rationale(
        self,
        question_text: str,
        ideal_answer: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Generate rationale explaining why answer is ideal."""
        start_time = time.time()
        context = context or {}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "rationale_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_rationale", prompt_template, cache_key)

        # Prepare variables
        variables = {
            "question_text": question_text,
            "ideal_answer": ideal_answer,
        }

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, None)

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=result["rationale_text"],
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return result["rationale_text"]

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def detect_concept_gaps(
        self,
        answer_text: str,
        ideal_answer: str,
        question_text: str,
        keyword_gaps: list[str],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Detect missing concepts in answer using LLM."""
        start_time = time.time()
        context = context or {}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db("gap_detection")

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("detect_concept_gaps", prompt_template, cache_key)

        # Prepare variables
        variables = {
            "question_text": question_text,
            "ideal_answer": ideal_answer,
            "answer_text": answer_text,
            "keyword_gaps": ", ".join(keyword_gaps),
        }

        # Execute chain
        try:
            result, metadata = await self._invoke_chain_with_metadata(chain, variables, None)

            output = {
                "concepts": result.get("concepts", []),
                "keywords": result.get("keywords", []),
                "confirmed": result.get("confirmed", False),
                "severity": result.get("severity", "minor"),
            }

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=str(result),
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return output

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

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
                metadata = self._extract_response_metadata(result)

            # Extract question text - handle both dict (JSON) and string responses
            if isinstance(result, dict):
                question_text = result.get("question_text", "")
            elif isinstance(result, str):
                # If plain text response, use it directly
                question_text = result.strip()
            else:
                raise ValueError(f"Unexpected result type: {type(result)}")

            if not question_text:
                raise ValueError("Empty question text returned from LLM")

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=question_text,
                    start_time=start_time,
                    success=True,
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
                        metadata = self._extract_response_metadata(None)

                    # Log as successful with plain text
                    if prompt_template:
                        await self._log_execution(
                            prompt_template=prompt_template,
                            context=context,
                            input_variables=variables,
                            output_text=plain_text,
                            start_time=start_time,
                            success=True,
                            model_response_metadata=metadata,
                        )

                    return plain_text

            # Log other exceptions as failures
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
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
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=str(result),
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return output

        except Exception as exc:
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=None,
                    start_time=start_time,
                    success=False,
                    error_message=str(exc),
                )
            raise

    async def generate_questions_batch(
        self,
        question_specs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[str]:
        """Generate multiple questions in parallel using asyncio.gather()."""
        start_time = time.time()

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "question_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_questions_batch", prompt_template, cache_key)

        # Build coroutines for all questions with metadata capture
        coroutines = []
        for spec in question_specs:
            # Format exemplars for this spec
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

            # Create chain input for this question
            chain_input = {
                "skill": spec["skill"],
                "difficulty": spec["difficulty"],
                "cv_summary": context.get("cv_summary", "Not provided"),
                "covered_topics": context.get("covered_topics", []),
                "stage": context.get("stage", "early"),
                "exemplar_section": exemplar_section,
            }

            # Use _invoke_chain_with_metadata to capture metadata
            coroutines.append(self._invoke_chain_with_metadata(chain, chain_input, None))

        # Execute all in parallel
        results_with_metadata = await asyncio.gather(*coroutines)

        # Extract questions and aggregate metadata
        questions = []
        aggregated_metadata = self._aggregate_metadata([meta for _, meta in results_with_metadata])
        for result, _ in results_with_metadata:
            questions.append(result["question_text"])

        # Log execution (if DB prompt was used)
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables={"question_specs_count": len(question_specs)},
                output_text=str(questions),
                start_time=start_time,
                success=True,
                model_response_metadata=aggregated_metadata,
            )

        return questions

    async def generate_ideal_answers_batch(
        self,
        question_texts: list[str],
        context: dict[str, Any],
    ) -> list[str]:
        """Generate ideal answers in parallel."""
        start_time = time.time()

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "ideal_answer_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_ideal_answers_batch", prompt_template, cache_key)

        # Build coroutines for all answers with metadata capture
        coroutines = []
        for question_text in question_texts:
            chain_input = {
                "question_text": question_text,
                "cv_summary": context.get("cv_summary", "Not provided"),
                "skill_level": context.get("skill_level", "intermediate"),
            }
            coroutines.append(self._invoke_chain_with_metadata(chain, chain_input, None))

        # Execute all in parallel
        results_with_metadata = await asyncio.gather(*coroutines)

        # Extract answers and aggregate metadata
        answers = []
        aggregated_metadata = self._aggregate_metadata([meta for _, meta in results_with_metadata])
        for result, _ in results_with_metadata:
            answers.append(result["answer_text"])

        # Log execution (if DB prompt was used)
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables={"question_count": len(question_texts)},
                output_text=str(answers),
                start_time=start_time,
                success=True,
                model_response_metadata=aggregated_metadata,
            )

        return answers

    async def generate_rationales_batch(
        self,
        question_ideal_pairs: list[tuple[str, str]],
    ) -> list[str]:
        """Generate rationales in parallel."""
        start_time = time.time()
        context = {}

        # Load DB prompt
        prompt_template, cache_key = await self._load_prompt_from_db(
            "rationale_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_rationales_batch", prompt_template, cache_key)

        # Build coroutines for all rationales with metadata capture
        coroutines = []
        for question_text, ideal_answer in question_ideal_pairs:
            chain_input = {
                "question_text": question_text,
                "ideal_answer": ideal_answer,
            }
            coroutines.append(self._invoke_chain_with_metadata(chain, chain_input, None))

        # Execute all in parallel
        results_with_metadata = await asyncio.gather(*coroutines)

        # Extract rationales and aggregate metadata
        rationales = []
        aggregated_metadata = self._aggregate_metadata([meta for _, meta in results_with_metadata])
        for result, _ in results_with_metadata:
            rationales.append(result["rationale_text"])

        # Log execution (if DB prompt was used)
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables={"pairs_count": len(question_ideal_pairs)},
                output_text=str(rationales),
                start_time=start_time,
                success=True,
                model_response_metadata=aggregated_metadata,
            )

        return rationales

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

        # Load DB prompt (uses same prompt as question generation)
        prompt_template, cache_key = await self._load_prompt_from_db(
            "question_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain(
            "generate_questions_with_answers_and_rationales_batch", prompt_template, cache_key
        )

        # Build coroutines for all question sets
        coroutines = []
        for spec in question_specs:
            # Format exemplars for this spec
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

            # Create chain input for this question set
            chain_input = {
                "skill": spec["skill"],
                "difficulty": spec["difficulty"],
                "cv_summary": context.get("cv_summary", "Not provided"),
                "covered_topics": context.get("covered_topics", []),
                "stage": context.get("stage", "early"),
                "exemplar_section": exemplar_section,
            }

            # Use _invoke_chain_with_metadata to capture metadata
            coroutines.append(self._invoke_chain_with_metadata(chain, chain_input, None))

        # Execute all in parallel
        results_with_metadata = await asyncio.gather(*coroutines)

        # Extract question sets in order and return as tuples
        question_sets = []
        aggregated_metadata = self._aggregate_metadata([meta for _, meta in results_with_metadata])
        for result, _ in results_with_metadata:
            question_text = result.get("question_text", "").strip()
            ideal_answer = result.get("ideal_answer", "").strip()
            rationale = result.get("rationale", "").strip()

            # Validate all three components are present
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

        # Log execution (if DB prompt was used)
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables={"question_specs_count": len(question_specs)},
                output_text=str(question_sets),
                start_time=start_time,
                success=True,
                model_response_metadata=aggregated_metadata,
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

    # Helper methods
    def _format_previous_evaluations(self, evaluations: list[Evaluation]) -> str:
        """Format previous evaluations for context."""
        if not evaluations:
            return "None"

        formatted = []
        for i, eval_obj in enumerate(evaluations, 1):
            formatted.append(f"Attempt {i}: Score {eval_obj.final_score:.1f}/100")
            # Check if it's an Evaluation (has concept_gaps) or AnswerEvaluation (has improvement_suggestions)
            if hasattr(eval_obj, "concept_gaps") and eval_obj.concept_gaps:
                gaps = [gap.concept for gap in eval_obj.concept_gaps[:3]]
                formatted.append(f"  Gaps: {', '.join(gaps)}")
            elif hasattr(eval_obj, "improvement_suggestions") and eval_obj.improvement_suggestions:
                formatted.append(f"  Gaps: {', '.join(eval_obj.improvement_suggestions[:3])}")

        return "\n".join(formatted)

    def _format_questions_answers(
        self, questions: list[Question], answers: list[dict[str, Any]]
    ) -> str:
        """Format questions and answers for report generation."""
        formatted = []
        for i, (q, a) in enumerate(zip(questions, answers, strict=True), 1):
            formatted.append(f"\n--- Question {i} ---")
            formatted.append(f"Q: {q.text}")
            # Use first skill from skills list, or "General" if empty
            skill = q.skills[0] if q.skills else "General"
            # Convert difficulty enum to string value
            difficulty = q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty)
            formatted.append(f"Skill: {skill} | Difficulty: {difficulty}")
            formatted.append(f"\nA: {a.get('answer_text', 'No answer provided')[:200]}...")
            formatted.append(f"Score: {a.get('score', 0):.1f}/100")
            formatted.append(f"Feedback: {a.get('feedback', '')[:150]}...")

        return "\n".join(formatted)

    async def _log_execution(
        self,
        prompt_template: PromptTemplate,
        context: dict[str, Any],
        input_variables: dict,
        output_text: str | None,
        start_time: float,
        success: bool,
        model_response_metadata: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log prompt execution to database with token tracking.

        Args:
            prompt_template: The PromptTemplate used
            context: Execution context (interview_id, candidate_id)
            input_variables: Variables passed to prompt
            output_text: LLM output (None if failed)
            start_time: Start timestamp
            success: Whether execution succeeded
            model_response_metadata: LangChain response metadata (for tokens)
            error_message: Error message if failed
        """
        if not self.prompt_repo:
            return  # No repository available, skip logging

        try:
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Get model name (try multiple sources)
            model_name = self._get_model_name(model_response_metadata)

            # Extract token usage
            total_tokens, prompt_tokens, completion_tokens = self._extract_token_usage(
                model_response_metadata, model_name
            )

            # Calculate estimated cost
            estimated_cost = self._estimate_cost(model_name, prompt_tokens, completion_tokens)

            # Sanitize input variables (remove PII if present)
            sanitized_input = self._sanitize_variables(input_variables)

            # Prepare execution data
            execution_data = {
                "interview_id": context.get("interview_id"),
                "input_variables": sanitized_input,
                "output_text": output_text[:10000] if output_text else None,  # Truncate
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "model_name": model_name,
                "success": success,
                "error_message": error_message,
            }

            # Log to database
            await self.prompt_repo.log_execution(
                prompt_template_id=prompt_template.id,
                execution_data=execution_data,
            )

            # Log to application logs (INFO for success, WARNING for failure)
            if success:
                logger.info(
                    "Prompt execution: %s (v%d) | Tokens: %s | Latency: %dms | Cost: $%.6f",
                    prompt_template.prompt_name,
                    prompt_template.version,
                    total_tokens or "N/A",
                    latency_ms,
                    estimated_cost or 0.0,
                )
            else:
                logger.warning(
                    "Prompt execution FAILED: %s (v%d) | Error: %s | Latency: %dms",
                    prompt_template.prompt_name,
                    prompt_template.version,
                    error_message,
                    latency_ms,
                )

        except Exception as log_error:
            # Don't fail the main operation if logging fails
            logger.error(
                "Failed to log prompt execution for %s: %s",
                prompt_template.prompt_name,
                log_error,
                exc_info=True,
            )

    async def _log_execution_with_retry(
        self,
        prompt_template: PromptTemplate,
        execution_data: dict,
        max_retries: int = 3,
    ) -> None:
        """Log execution with exponential backoff retry.

        Args:
            prompt_template: The PromptTemplate used
            execution_data: Execution data to log
            max_retries: Maximum retry attempts
        """
        import asyncio

        for attempt in range(max_retries):
            try:
                await self.prompt_repo.log_execution(
                    prompt_template_id=prompt_template.id,
                    execution_data=execution_data,
                )
                return  # Success

            except Exception as exc:
                if attempt == max_retries - 1:
                    # Final attempt failed
                    logger.error(
                        "Failed to log execution after %d attempts: %s",
                        max_retries,
                        exc,
                        exc_info=True,
                    )
                    raise

                # Exponential backoff: 0.1s, 0.2s, 0.4s
                wait_time = 0.1 * (2**attempt)
                logger.warning(
                    "Logging failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries,
                    wait_time,
                    exc,
                )
                await asyncio.sleep(wait_time)

    def _get_model_name(self, model_response_metadata: dict[str, Any] | None = None) -> str:
        """Extract model name from LangChain model object.

        Checks multiple possible attributes and metadata sources.

        Args:
            model_response_metadata: Optional metadata from response (may contain model name)

        Returns:
            Model name string, or "unknown" if not found
        """
        # Try to get from response metadata first
        if model_response_metadata:
            model_name = model_response_metadata.get("model_name") or model_response_metadata.get("model")
            if model_name:
                return model_name

        # Try common model attributes
        if hasattr(self.model, "model_name"):
            return self.model.model_name
        if hasattr(self.model, "model"):
            return self.model.model
        if hasattr(self.model, "model_id"):
            return self.model.model_id

        # Try to get from model's __dict__ (some models store it differently)
        if hasattr(self.model, "__dict__"):
            model_dict = self.model.__dict__
            if "model_name" in model_dict:
                return model_dict["model_name"]
            if "model" in model_dict:
                return model_dict["model"]

        # Fallback to class name
        return type(self.model).__name__

    def _extract_response_metadata(self, chain_response: Any) -> dict | None:
        """Extract metadata from LangChain chain response.

        LangChain responses may include token usage, model info in various formats.
        This method standardizes extraction across different model providers.

        Args:
            chain_response: Response from chain.ainvoke()

        Returns:
            Dict with keys: usage (token_usage), model_name, etc.
            None if no metadata available
        """
        # LangChain responses can be dict, AIMessage, or raw JSON
        if isinstance(chain_response, dict):
            # Direct dict response (JSON output parser)
            return chain_response.get("_metadata")

        # AIMessage (structured output)
        if hasattr(chain_response, "response_metadata"):
            return chain_response.response_metadata

        # Check for usage_metadata (newer LangChain versions)
        if hasattr(chain_response, "usage_metadata"):
            return {"usage": chain_response.usage_metadata}

        return None

    def _extract_token_usage(
        self,
        model_response_metadata: dict | None,
        model_name: str,
    ) -> tuple[int | None, int | None, int | None]:
        """Extract token usage from LangChain response metadata.

        Supports multiple token formats:
        - OpenAI: usage.total_tokens, usage.prompt_tokens, usage.completion_tokens
        - Anthropic: usage.input_tokens, usage.output_tokens
        - Generic: token_usage.total, token_usage.prompt, token_usage.completion

        Args:
            model_response_metadata: Response metadata from LangChain
            model_name: Model identifier (for provider detection)

        Returns:
            Tuple of (total_tokens, prompt_tokens, completion_tokens)
            Returns (None, None, None) if no token data available
        """
        if not model_response_metadata:
            logger.debug("No model_response_metadata provided for token extraction")
            return None, None, None

        # Try multiple paths to find usage data
        # Priority: token_usage (OpenAI format) > usage (Anthropic format)
        token_usage = None
        usage = None

        # Path 1: token_usage key (OpenAI format: prompt_tokens, completion_tokens)
        if "token_usage" in model_response_metadata:
            token_usage = model_response_metadata["token_usage"]
        # Path 2: usage key (Anthropic format: input_tokens, output_tokens)
        if "usage" in model_response_metadata:
            usage = model_response_metadata["usage"]
        # Path 3: Check if nested in response_metadata
        elif isinstance(model_response_metadata.get("response_metadata"), dict):
            nested_meta = model_response_metadata["response_metadata"]
            token_usage = nested_meta.get("token_usage") or token_usage
            usage = nested_meta.get("usage") or usage

        # Prefer token_usage (OpenAI format) as it has prompt_tokens/completion_tokens directly
        if token_usage and isinstance(token_usage, dict):
            # OpenAI format: total_tokens, prompt_tokens, completion_tokens
            if "prompt_tokens" in token_usage or "completion_tokens" in token_usage:
                return (
                    token_usage.get("total_tokens"),
                    token_usage.get("prompt_tokens"),
                    token_usage.get("completion_tokens"),
                )

        # Fall back to usage (Anthropic format)
        if usage and isinstance(usage, dict):
            # Anthropic format: input_tokens, output_tokens
            if "input_tokens" in usage:
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total = (
                    (input_tokens or 0) + (output_tokens or 0)
                    if input_tokens is not None and output_tokens is not None
                    else usage.get("total_tokens")
                )
                return total, input_tokens, output_tokens

            # Also check for OpenAI format in usage dict (some providers use this)
            if "prompt_tokens" in usage or "completion_tokens" in usage:
                return (
                    usage.get("total_tokens"),
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )

            # Generic format: total, prompt, completion
            if "total" in usage or "prompt" in usage or "completion" in usage:
                return (
                    usage.get("total"),
                    usage.get("prompt"),
                    usage.get("completion"),
                )

        logger.debug(f"No usage data found in metadata. Keys: {list(model_response_metadata.keys())}")
        return None, None, None

    def _estimate_cost(
        self,
        model_name: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> float | None:
        """Estimate LLM cost based on token usage.

        Uses approximate pricing (as of 2025-11):
        - GPT-4: $0.03/1K prompt, $0.06/1K completion
        - GPT-3.5: $0.0005/1K prompt, $0.0015/1K completion
        - Claude 3 Opus: $0.015/1K prompt, $0.075/1K completion
        - Claude 3 Sonnet: $0.003/1K prompt, $0.015/1K completion

        Args:
            model_name: Model identifier
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Estimated cost in USD, or None if tokens unavailable
        """
        if not prompt_tokens or not completion_tokens:
            return None

        # Pricing table (cents per 1K tokens)
        PRICING = {
            "gpt-4": (3.0, 6.0),
            "gpt-3.5-turbo": (0.05, 0.15),
            "claude-3-opus": (1.5, 7.5),
            "claude-3-sonnet": (0.3, 1.5),
            "claude-3-haiku": (0.025, 0.125),
        }

        # Match model name (case-insensitive, partial match)
        model_lower = model_name.lower()
        for key, (prompt_cost, completion_cost) in PRICING.items():
            if key in model_lower:
                cost_usd = (prompt_tokens / 1000 * prompt_cost / 100) + (
                    completion_tokens / 1000 * completion_cost / 100
                )
                return round(cost_usd, 6)  # 6 decimal places ($0.000001 precision)

        # Unknown model
        logger.warning("Unknown model '%s' for cost estimation", model_name)
        return None

    def _sanitize_variables(self, input_variables: dict) -> dict:
        """Sanitize input variables to remove PII.

        Removes or redacts:
        - Email addresses
        - Phone numbers
        - Long text fields (truncate to 500 chars)

        Args:
            input_variables: Raw input variables

        Returns:
            Sanitized dict safe for logging
        """
        import re

        sanitized = {}
        for key, value in input_variables.items():
            if value is None:
                sanitized[key] = None
                continue

            # Convert to string for processing
            str_value = str(value)

            # Redact emails
            str_value = re.sub(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "[EMAIL_REDACTED]",
                str_value,
            )

            # Redact phone numbers
            str_value = re.sub(
                r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
                "[PHONE_REDACTED]",
                str_value,
            )

            # Truncate long text (preserve structure for debugging)
            if len(str_value) > 500:
                str_value = str_value[:500] + f"... [TRUNCATED {len(str_value)-500} chars]"

            sanitized[key] = str_value

        return sanitized
