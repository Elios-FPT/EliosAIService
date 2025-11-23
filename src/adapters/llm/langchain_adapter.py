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

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from ...domain.models.answer import AnswerEvaluation
from ...domain.models.evaluation import FollowUpEvaluationContext
from ...domain.models.prompt_template import PromptTemplate
from ...domain.models.question import Question
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.prompt_repository_port import PromptRepositoryPort
from .prompts import PROMPT_REGISTRY

logger = logging.getLogger(__name__)


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
        db_template_json: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> Runnable:
        """Return cached chain or build a dynamic one from DB template."""
        if not db_template_json:
            return self._chains[method_name]

        required_keys = {"system", "user_template"}
        missing = required_keys - set(db_template_json.keys())
        if missing:
            logger.warning(
                "Invalid template for %s missing keys %s. Falling back to hardcoded chain.",
                method_name,
                ", ".join(sorted(missing)),
            )
            return self._chains[method_name]

        cache_identifier = (
            f"{method_name}:{cache_key or json.dumps(db_template_json, sort_keys=True)}"
        )
        if cache_identifier in self._db_chain_cache:
            return self._db_chain_cache[cache_identifier]

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", db_template_json["system"]),
                ("human", db_template_json["user_template"]),
            ]
        )
        json_parser = JsonOutputParser()
        chain = prompt_template | self.model | json_parser
        self._db_chain_cache[cache_identifier] = chain
        return chain

    async def _load_prompt_from_db(
        self,
        prompt_name: str,
    ) -> tuple[PromptTemplate | None, dict | None, str | None]:
        """Load prompt from DB with fallback.

        Args:
            prompt_name: DB prompt identifier (e.g., "ideal_answer_generation")

        Returns:
            Tuple of (prompt_template, template_json, cache_key)
            Returns (None, None, None) if DB unavailable or prompt not found

        Example:
            prompt_template, template_json, cache_key = await self._load_prompt_from_db("answer_evaluation")
            chain = self._get_or_build_chain("evaluate_answer", template_json, cache_key)
        """
        if not self.prompt_repo:
            return None, None, None

        try:
            prompt_template = await self.prompt_repo.get_active_prompt(prompt_name)
            if not prompt_template:
                logger.info(
                    "No active DB prompt for '%s', falling back to PROMPT_REGISTRY",
                    prompt_name,
                )
                return None, None, None

            template_json = prompt_template.template_json_legacy
            cache_key = f"{prompt_template.prompt_name}:v{prompt_template.version}"
            return prompt_template, template_json, cache_key

        except Exception as exc:
            logger.warning(
                "Failed loading DB prompt for '%s': %s. Falling back to PROMPT_REGISTRY.",
                prompt_name,
                exc,
                exc_info=True,  # Include stack trace for debugging
            )
            return None, None, None

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "answer_evaluation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("evaluate_answer", template_json, cache_key)

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
            result = await chain.ainvoke(variables, config=config)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "feedback_report"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_feedback_report", template_json, cache_key)

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
            result = await chain.ainvoke(variables, config=config)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db("cv_summary")

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("summarize_cv", template_json, cache_key)

        # Prepare variables
        variables = {"cv_text": cv_text}

        # Create config with metadata
        config = self._create_config(context=context, method="summarize_cv")

        # Execute chain
        try:
            result = await chain.ainvoke(variables, config=config)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "skill_extraction"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("extract_skills_from_text", template_json, cache_key)

        # Prepare variables
        variables = {"text": text}

        # Create config with metadata
        config = self._create_config(context=context, method="extract_skills_from_text")

        # Execute chain
        try:
            result = await chain.ainvoke(variables, config=config)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "ideal_answer_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_ideal_answer", template_json, cache_key)

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
            result = await chain.ainvoke(variables, config=config)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "rationale_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_rationale", template_json, cache_key)

        # Prepare variables
        variables = {
            "question_text": question_text,
            "ideal_answer": ideal_answer,
        }

        # Execute chain
        try:
            result = await chain.ainvoke(variables)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db("gap_detection")

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("detect_concept_gaps", template_json, cache_key)

        # Prepare variables
        variables = {
            "question_text": question_text,
            "ideal_answer": ideal_answer,
            "answer_text": answer_text,
            "keyword_gaps": ", ".join(keyword_gaps),
        }

        # Execute chain
        try:
            result = await chain.ainvoke(variables)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "follow_up_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_followup_question", template_json, cache_key)

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

        # Prepare variables
        variables = {
            "parent_question": parent_question,
            "answer_text": answer_text,
            "missing_concepts": ", ".join(missing_concepts),
            "severity": severity,
            "order": order,
            "cumulative_context": cumulative_context,
            "previous_followups": previous_context,
        }

        # Create config with metadata
        config = self._create_config(
            context=context,
            method="generate_followup_question",
            severity=severity,
            order=order,
        )

        # Execute chain
        try:
            result = await chain.ainvoke(variables, config=config)
            metadata = self._extract_response_metadata(result)

            # Log execution
            if prompt_template:
                await self._log_execution(
                    prompt_template=prompt_template,
                    context=context,
                    input_variables=variables,
                    output_text=result["question_text"],
                    start_time=start_time,
                    success=True,
                    model_response_metadata=metadata,
                )

            return result["question_text"]

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

    async def generate_interview_recommendations(
        self,
        context: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Generate personalized interview recommendations."""
        start_time = time.time()

        # Load DB prompt
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "interview_recommendations"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain(
            "generate_interview_recommendations", template_json, cache_key
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
            result = await chain.ainvoke(variables)
            metadata = self._extract_response_metadata(result)

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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "question_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_questions_batch", template_json, cache_key)

        # Build coroutines for all questions
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

            # Add coroutine to list
            coroutines.append(chain.ainvoke(chain_input))

        # Execute all in parallel
        results = await asyncio.gather(*coroutines)

        # Extract questions in order
        questions = []
        for result in results:
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
                model_response_metadata=None,
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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "ideal_answer_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_ideal_answers_batch", template_json, cache_key)

        # Build coroutines for all answers
        coroutines = []
        for question_text in question_texts:
            chain_input = {
                "question_text": question_text,
                "cv_summary": context.get("cv_summary", "Not provided"),
                "skill_level": context.get("skill_level", "intermediate"),
            }
            coroutines.append(chain.ainvoke(chain_input))

        # Execute all in parallel
        results = await asyncio.gather(*coroutines)

        # Extract answers in order
        answers = []
        for result in results:
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
                model_response_metadata=None,
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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "rationale_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain("generate_rationales_batch", template_json, cache_key)

        # Build coroutines for all rationales
        coroutines = []
        for question_text, ideal_answer in question_ideal_pairs:
            chain_input = {
                "question_text": question_text,
                "ideal_answer": ideal_answer,
            }
            coroutines.append(chain.ainvoke(chain_input))

        # Execute all in parallel
        results = await asyncio.gather(*coroutines)

        # Extract rationales in order
        rationales = []
        for result in results:
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
                model_response_metadata=None,
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
        prompt_template, template_json, cache_key = await self._load_prompt_from_db(
            "question_generation"
        )

        # Get chain (DB or fallback)
        chain = self._get_or_build_chain(
            "generate_questions_with_answers_and_rationales_batch", template_json, cache_key
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

            # Add coroutine to list
            coroutines.append(chain.ainvoke(chain_input))

        # Execute all in parallel
        results = await asyncio.gather(*coroutines)

        # Extract question sets in order and return as tuples
        question_sets = []
        for result in results:
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
                model_response_metadata=None,
            )

        return question_sets

    # Helper methods
    def _format_previous_evaluations(self, evaluations: list[Any]) -> str:
        """Format previous evaluations for context."""
        if not evaluations:
            return "None"

        formatted = []
        for i, eval_obj in enumerate(evaluations, 1):
            formatted.append(f"Attempt {i}: Score {eval_obj.score:.1f}/100")
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

            # Get model name
            model_name = getattr(self.model, "model_name", getattr(self.model, "model", "unknown"))

            # Extract token usage
            total_tokens, prompt_tokens, completion_tokens = self._extract_token_usage(
                model_response_metadata, model_name
            )

            # Estimate cost
            estimated_cost = self._estimate_cost(model_name, prompt_tokens, completion_tokens)

            # Sanitize input variables (remove PII if present)
            sanitized_input = self._sanitize_variables(input_variables)

            # Prepare execution data
            execution_data = {
                "interview_id": context.get("interview_id"),
                "candidate_id": context.get("candidate_id"),
                "input_variables": sanitized_input,
                "output_text": output_text[:10000] if output_text else None,  # Truncate
                "tokens_used": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "model_name": model_name,
                "success": success,
                "error_message": error_message,
                "estimated_cost_usd": estimated_cost,
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
            return None, None, None

        usage = model_response_metadata.get("usage") or model_response_metadata.get("token_usage")
        if not usage:
            return None, None, None

        # OpenAI format
        if "total_tokens" in usage:
            return (
                usage.get("total_tokens"),
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )

        # Anthropic format
        if "input_tokens" in usage:
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            total = (
                (input_tokens or 0) + (output_tokens or 0)
                if input_tokens and output_tokens
                else None
            )
            return total, input_tokens, output_tokens

        # Generic format
        return (
            usage.get("total"),
            usage.get("prompt"),
            usage.get("completion"),
        )

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
