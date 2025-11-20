"""LangChain adapter implementation of LLMPort.

This adapter uses LangChain LCEL (Expression Language) chains to implement
all LLMPort methods with structured outputs and cleaner code.
"""

import json
import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableParallel, RunnableConfig

from ...domain.models.answer import AnswerEvaluation
from ...domain.models.evaluation import FollowUpEvaluationContext
from ...domain.models.question import Question
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.prompt_repository_port import PromptRepositoryPort
from .langchain_models import (
    CVSummaryOutput,
    EvaluationOutput,
    FeedbackReportOutput,
    FollowUpOutput,
    GapDetectionOutput,
    IdealAnswerOutput,
    RationaleOutput,
    RecommendationsOutput,
    SkillExtractionOutput,
)
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

        cache_identifier = f"{method_name}:{cache_key or json.dumps(db_template_json, sort_keys=True)}"
        if cache_identifier in self._db_chain_cache:
            return self._db_chain_cache[cache_identifier]

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", db_template_json["system"]),
            ("human", db_template_json["user_template"]),
        ])
        json_parser = JsonOutputParser()
        chain = prompt_template | self.model | json_parser
        self._db_chain_cache[cache_identifier] = chain
        return chain

    def _create_config(self, context: dict[str, Any] | None = None, **metadata_kwargs: Any) -> RunnableConfig:
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
        # Format followup context if present
        followup_section = ""
        if followup_context:
            followup_section = f"""
This is a follow-up question (attempt #{followup_context.attempt_number}).

Previous Evaluations:
{self._format_previous_evaluations(followup_context.previous_evaluations)}

Cumulative Gaps: {', '.join(followup_context.cumulative_gaps) if followup_context.cumulative_gaps else 'None'}

Apply attempt-based penalty:
- Attempt 2: Reduce score by 10% (gaps should be addressed)
- Attempt 3+: Reduce score by 20% (repeated failure to address gaps)
"""

        # Create config with metadata
        config = self._create_config(
            context=context,
            question_id=str(question.id) if question.id else None,
            difficulty=question.difficulty.value if hasattr(question.difficulty, 'value') else str(question.difficulty),
            skill=question.skills[0] if question.skills else "General",
            method="evaluate_answer",
        )

        # Execute chain
        result = await self._chains["evaluate_answer"].ainvoke({
            "question_text": question.text,
            "difficulty": question.difficulty,
            "skill": question.skills[0] if question.skills else "General",
            "answer_text": answer_text,
            "followup_context": followup_section,
        }, config=config)

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
            improvement_suggestions=result.get("missing_concepts", []),  # Map missing_concepts to improvements
        )

    async def generate_feedback_report(
        self,
        interview_id: UUID,
        questions: list[Question],
        answers: list[dict[str, Any]],
    ) -> str:
        """Generate comprehensive feedback report."""
        # Format questions and answers
        qa_formatted = self._format_questions_answers(questions, answers)

        # Create config with metadata
        config = self._create_config(
            context={"interview_id": str(interview_id)},
            method="generate_feedback_report",
            question_count=len(questions),
        )

        result = await self._chains["generate_feedback_report"].ainvoke({
            "interview_id": str(interview_id),
            "total_questions": len(questions),
            "questions_and_answers": qa_formatted,
        }, config=config)

        return result["report_text"]

    async def summarize_cv(self, cv_text: str) -> str:
        """Generate a summary of a CV."""
        # Create config with metadata
        config = self._create_config(method="summarize_cv")

        result = await self._chains["summarize_cv"].ainvoke({
            "cv_text": cv_text,
        }, config=config)

        return result["summary_text"]

    async def extract_skills_from_text(self, text: str) -> list[dict[str, str]]:
        """Extract skills from CV text using LLM."""
        # Create config with metadata
        config = self._create_config(method="extract_skills_from_text")

        result = await self._chains["extract_skills_from_text"].ainvoke({
            "text": text,
        }, config=config)

        # Convert to expected format
        skills = []
        for skill_item in result.get("skills", []):
            skills.append({
                "skill": skill_item["name"],
                "category": skill_item.get("category", ""),
                "proficiency": skill_item.get("proficiency", ""),
            })

        return skills

    async def generate_ideal_answer(
        self,
        question_text: str,
        context: dict[str, Any],
    ) -> str:
        """Generate ideal answer for a question."""
        start_time = time.time()
        prompt_template = None
        template_json = None
        cache_key = None

        if self.prompt_repo:
            try:
                prompt_template = await self.prompt_repo.get_active_prompt(
                    name="ideal_answer_generation"
                )
                if prompt_template:
                    template_json = prompt_template.template_json
                    cache_key = f"{prompt_template.name}:v{prompt_template.version}"
            except Exception as exc:
                logger.warning(
                    "Failed loading DB prompt for generate_ideal_answer: %s", exc
                )
                prompt_template = None
                template_json = None

        chain = self._get_or_build_chain(
            "generate_ideal_answer",
            db_template_json=template_json,
            cache_key=cache_key,
        )

        variables = {
            "question_text": question_text,
            "summary": context.get("summary", context.get("cv_summary", "Not provided")),
            "skills": ", ".join(context.get("skills", [])[:5])
            if context.get("skills")
            else "Not specified",
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

        output_text = result.get("answer_text") or result.get("answer")

        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=output_text,
                start_time=start_time,
                success=True,
            )

        return output_text

    async def generate_rationale(
        self,
        question_text: str,
        ideal_answer: str,
    ) -> str:
        """Generate rationale explaining why answer is ideal."""
        result = await self._chains["generate_rationale"].ainvoke({
            "question_text": question_text,
            "ideal_answer": ideal_answer,
        })

        return result["rationale_text"]

    async def detect_concept_gaps(
        self,
        answer_text: str,
        ideal_answer: str,
        question_text: str,
        keyword_gaps: list[str],
    ) -> dict[str, Any]:
        """Detect missing concepts in answer using LLM."""
        result = await self._chains["detect_concept_gaps"].ainvoke({
            "question_text": question_text,
            "ideal_answer": ideal_answer,
            "answer_text": answer_text,
            "keyword_gaps": ", ".join(keyword_gaps),
        })

        return {
            "concepts": result.get("concepts", []),
            "keywords": result.get("keywords", []),
            "confirmed": result.get("confirmed", False),
            "severity": result.get("severity", "minor"),
        }

    async def generate_followup_question(
        self,
        parent_question: str,
        answer_text: str,
        missing_concepts: list[str],
        severity: str,
        order: int,
        cumulative_gaps: list[str] | None = None,
        previous_follow_ups: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate targeted follow-up question."""
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

        # Create config with metadata
        config = self._create_config(
            method="generate_followup_question",
            severity=severity,
            order=order,
        )

        result = await self._chains["generate_followup_question"].ainvoke({
            "parent_question": parent_question,
            "answer_text": answer_text,
            "missing_concepts": ", ".join(missing_concepts),
            "severity": severity,
            "order": order,
            "cumulative_context": cumulative_context,
            "previous_followups": previous_context,
        }, config=config)

        return result["question_text"]

    async def generate_interview_recommendations(
        self,
        context: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Generate personalized interview recommendations."""
        result = await self._chains["generate_interview_recommendations"].ainvoke({
            "interview_id": context.get("interview_id", ""),
            "total_answers": context.get("total_answers", 0),
            "gap_progression": json.dumps(context.get("gap_progression", {})),
            "evaluations": json.dumps(context.get("evaluations", [])),
        })

        return {
            "strengths": result.get("strengths", []),
            "weaknesses": result.get("weaknesses", []),
            "study_topics": result.get("study_topics", []),
            "technique_tips": result.get("technique_tips", []),
        }

    async def generate_questions_batch(
        self,
        question_specs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[str]:
        """Generate multiple questions in parallel using RunnableParallel."""
        # Build parallel chain for all questions
        parallel_chains = {}
        for i, spec in enumerate(question_specs):
            # Format exemplars for this spec
            exemplar_section = ""
            exemplars = spec.get("exemplars")
            if exemplars:
                exemplar_section = "Similar questions for inspiration (do NOT copy exactly):\n"
                for j, ex in enumerate(exemplars[:3], 1):
                    exemplar_section += f"{j}. \"{ex.get('text', '')}\" ({ex.get('difficulty', 'UNKNOWN')})\n"
                exemplar_section += "\nGenerate a NEW question inspired by the style and structure above.\n"

            # Create chain input for this question
            chain_input = {
                "skill": spec["skill"],
                "difficulty": spec["difficulty"],
                "cv_summary": context.get("cv_summary", "Not provided"),
                "covered_topics": context.get("covered_topics", []),
                "stage": context.get("stage", "early"),
                "exemplar_section": exemplar_section,
            }

            # Add to parallel chains with unique key
            parallel_chains[f"q_{i}"] = self._chains["generate_questions_batch"].ainvoke(chain_input)

        # Execute all in parallel
        results = await RunnableParallel(**parallel_chains).ainvoke({})

        # Extract questions in order
        questions = []
        for i in range(len(question_specs)):
            result = results[f"q_{i}"]
            questions.append(result["question_text"])

        return questions

    async def generate_ideal_answers_batch(
        self,
        question_texts: list[str],
        context: dict[str, Any],
    ) -> list[str]:
        """Generate ideal answers in parallel."""
        # Build parallel chain
        parallel_chains = {}
        for i, question_text in enumerate(question_texts):
            chain_input = {
                "question_text": question_text,
                "cv_summary": context.get("cv_summary", "Not provided"),
                "skill_level": context.get("skill_level", "intermediate"),
            }
            parallel_chains[f"a_{i}"] = self._chains["generate_ideal_answers_batch"].ainvoke(chain_input)

        # Execute all in parallel
        results = await RunnableParallel(**parallel_chains).ainvoke({})

        # Extract answers in order
        answers = []
        for i in range(len(question_texts)):
            result = results[f"a_{i}"]
            answers.append(result["answer_text"])

        return answers

    async def generate_rationales_batch(
        self,
        question_ideal_pairs: list[tuple[str, str]],
    ) -> list[str]:
        """Generate rationales in parallel."""
        # Build parallel chain
        parallel_chains = {}
        for i, (question_text, ideal_answer) in enumerate(question_ideal_pairs):
            chain_input = {
                "question_text": question_text,
                "ideal_answer": ideal_answer,
            }
            parallel_chains[f"r_{i}"] = self._chains["generate_rationales_batch"].ainvoke(chain_input)

        # Execute all in parallel
        results = await RunnableParallel(**parallel_chains).ainvoke({})

        # Extract rationales in order
        rationales = []
        for i in range(len(question_ideal_pairs)):
            result = results[f"r_{i}"]
            rationales.append(result["rationale_text"])

        return rationales

    # Helper methods
    def _format_previous_evaluations(self, evaluations: list[Any]) -> str:
        """Format previous evaluations for context."""
        if not evaluations:
            return "None"

        formatted = []
        for i, eval_obj in enumerate(evaluations, 1):
            formatted.append(f"Attempt {i}: Score {eval_obj.score:.1f}/100")
            # Check if it's an Evaluation (has concept_gaps) or AnswerEvaluation (has improvement_suggestions)
            if hasattr(eval_obj, 'concept_gaps') and eval_obj.concept_gaps:
                gaps = [gap.concept for gap in eval_obj.concept_gaps[:3]]
                formatted.append(f"  Gaps: {', '.join(gaps)}")
            elif hasattr(eval_obj, 'improvement_suggestions') and eval_obj.improvement_suggestions:
                formatted.append(f"  Gaps: {', '.join(eval_obj.improvement_suggestions[:3])}")

        return "\n".join(formatted)

    def _format_questions_answers(
        self, questions: list[Question], answers: list[dict[str, Any]]
    ) -> str:
        """Format questions and answers for report generation."""
        formatted = []
        for i, (q, a) in enumerate(zip(questions, answers), 1):
            formatted.append(f"\n--- Question {i} ---")
            formatted.append(f"Q: {q.text}")
            # Use first skill from skills list, or "General" if empty
            skill = q.skills[0] if q.skills else "General"
            # Convert difficulty enum to string value
            difficulty = q.difficulty.value if hasattr(q.difficulty, 'value') else str(q.difficulty)
            formatted.append(f"Skill: {skill} | Difficulty: {difficulty}")
            formatted.append(f"\nA: {a.get('answer_text', 'No answer provided')[:200]}...")
            formatted.append(f"Score: {a.get('score', 0):.1f}/100")
            formatted.append(f"Feedback: {a.get('feedback', '')[:150]}...")

        return "\n".join(formatted)

    async def _log_execution(
        self,
        prompt_template,
        context: dict[str, Any],
        input_variables: dict,
        output_text: str | None,
        start_time: float,
        success: bool,
        tokens_used: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log prompt execution to database.

        Args:
            prompt_template: The prompt template used
            context: Execution context
            input_variables: Variables passed to prompt
            output_text: LLM output (None if failed)
            start_time: Start timestamp
            success: Whether execution succeeded
            tokens_used: Total tokens (optional, LangChain models may not provide)
            prompt_tokens: Prompt tokens (optional)
            completion_tokens: Completion tokens (optional)
            error_message: Error message if failed (optional)
        """
        try:
            latency_ms = int((time.time() - start_time) * 1000)

            # Get model name from LangChain model
            model_name = getattr(self.model, 'model_name',
                                getattr(self.model, 'model', 'unknown'))

            await self.prompt_repo.log_execution(
                prompt_template_id=prompt_template.id,
                execution_data={
                    "interview_id": context.get("interview_id"),
                    "candidate_id": context.get("candidate_id"),
                    "input_variables": input_variables,
                    "output_text": output_text[:10000] if output_text else None,  # Truncate
                    "tokens_used": tokens_used,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "latency_ms": latency_ms,
                    "model_name": model_name,
                    "success": success,
                    "error_message": error_message,
                },
            )
        except Exception as log_error:
            # Don't fail the main operation if logging fails
            import logging
            logging.getLogger(__name__).error(
                f"Failed to log prompt execution: {log_error}"
            )
