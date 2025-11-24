"""LangSmith tracing configuration with PII filtering.

This module implements privacy-preserving observability for LangChain/LangGraph workflows.
All traces sent to LangSmith are filtered to remove personally identifiable information (PII).
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.tracers.langchain import LangChainTracer
from langchain_core.tracers.context import tracing_v2_enabled

logger = logging.getLogger(__name__)


class PIIFilteringTracer(LangChainTracer):
    """LangChain tracer that filters PII before sending to LangSmith.

    Redacts:
    - Email addresses
    - Phone numbers (US format)
    - SSN/Tax IDs
    - Credit card numbers
    - Names (when detected in specific contexts)
    - CV text (only keeps first 100 chars)

    Preserves:
    - interview_id, candidate_id (UUIDs are safe)
    - question_type, difficulty, skill (metadata)
    - Question text (non-PII)
    - Answer text (first 200 chars only)
    """

    # PII regex patterns
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'  # US phone
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'  # SSN format
    CREDIT_CARD_PATTERN = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    NAME_PATTERN = r'\b(?:My name is|I am|I\'m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'  # "My name is John Doe"

    def __init__(
        self,
        *args: Any,
        max_answer_length: int = 200,
        max_cv_length: int = 100,
        **kwargs: Any,
    ):
        """Initialize PII filtering tracer.

        Args:
            max_answer_length: Max characters to keep from answer text
            max_cv_length: Max characters to keep from CV text
            *args, **kwargs: Passed to LangChainTracer
        """
        super().__init__(*args, **kwargs)
        self.max_answer_length = max_answer_length
        self.max_cv_length = max_cv_length

    def _filter_pii(self, text: str, field_name: str = "") -> str:
        """Redact PII patterns from text.

        Args:
            text: Text to filter
            field_name: Name of field (for context-specific filtering)

        Returns:
            Filtered text with PII redacted
        """
        if not text:
            return text

        # Email redaction
        text = re.sub(self.EMAIL_PATTERN, "[EMAIL_REDACTED]", text)

        # Phone redaction
        text = re.sub(self.PHONE_PATTERN, "[PHONE_REDACTED]", text)

        # SSN redaction
        text = re.sub(self.SSN_PATTERN, "[SSN_REDACTED]", text)

        # Credit card redaction
        text = re.sub(self.CREDIT_CARD_PATTERN, "[CC_REDACTED]", text)

        # Name redaction (when explicitly stated)
        text = re.sub(self.NAME_PATTERN, r"My name is [NAME_REDACTED]", text)

        # Truncate answer text
        if field_name == "answer_text" and len(text) > self.max_answer_length:
            text = text[:self.max_answer_length] + "... [TRUNCATED]"

        # Truncate CV text heavily
        if field_name == "cv_text" and len(text) > self.max_cv_length:
            text = text[:self.max_cv_length] + "... [CV_REDACTED]"

        return text

    def _filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively filter PII from dictionary.

        Args:
            data: Dictionary to filter

        Returns:
            Filtered dictionary
        """
        if not isinstance(data, dict):
            return data

        filtered = {}
        for key, value in data.items():
            if isinstance(value, str):
                filtered[key] = self._filter_pii(value, field_name=key)
            elif isinstance(value, dict):
                filtered[key] = self._filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_dict(item) if isinstance(item, dict)
                    else self._filter_pii(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                # Safe types: UUIDs, numbers, booleans
                filtered[key] = value

        return filtered

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Handle LLM start event with PII filtering.

        Args:
            serialized: LLM configuration
            prompts: List of prompt strings
            **kwargs: Additional arguments
        """
        # Filter prompts
        filtered_prompts = [self._filter_pii(p) for p in prompts]

        # Filter metadata
        if "metadata" in kwargs:
            kwargs["metadata"] = self._filter_dict(kwargs["metadata"])

        super().on_llm_start(serialized, filtered_prompts, **kwargs)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Handle LLM end event with PII filtering.

        Args:
            response: LLM response
            **kwargs: Additional arguments
        """
        # Filter response text
        if hasattr(response, "generations"):
            for generation_list in response.generations:
                for generation in generation_list:
                    if hasattr(generation, "text"):
                        generation.text = self._filter_pii(generation.text)

        super().on_llm_end(response, **kwargs)

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Handle chain start event with PII filtering.

        Args:
            serialized: Chain configuration
            inputs: Chain inputs
            **kwargs: Additional arguments
        """
        # Filter inputs
        filtered_inputs = self._filter_dict(inputs)

        super().on_chain_start(serialized, filtered_inputs, **kwargs)

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Handle chain end event with PII filtering.

        Args:
            outputs: Chain outputs
            **kwargs: Additional arguments
        """
        # Filter outputs
        filtered_outputs = self._filter_dict(outputs)

        super().on_chain_end(filtered_outputs, **kwargs)


def setup_langsmith_tracing(settings: Any) -> Optional[PIIFilteringTracer]:
    """Setup LangSmith tracing with environment variables and PII filtering.

    Args:
        settings: Application settings object

    Returns:
        PIIFilteringTracer if enabled, None otherwise
    """
    if not settings.enable_langsmith:
        logger.info("LangSmith tracing disabled (enable_langsmith=False)")
        return None

    # Set environment variables for LangSmith
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint

        logger.info(
            f"LangSmith tracing enabled: project={settings.langchain_project}, "
            f"pii_filtering={settings.langsmith_filter_pii}, "
            f"sample_rate={settings.langsmith_sample_rate}"
        )

        # Create PII filtering tracer if enabled
        if settings.langsmith_filter_pii:
            tracer = PIIFilteringTracer(
                project_name=settings.langchain_project,
                max_answer_length=200,
                max_cv_length=100,
            )
            return tracer
        else:
            logger.warning("PII filtering disabled - traces may contain sensitive data")
            return None
    else:
        logger.warning("LangSmith enabled but no API key provided")
        return None


def create_pii_filtering_callback(settings: Any) -> List[Any]:
    """Create list of callbacks including PII filtering tracer.

    Args:
        settings: Application settings object

    Returns:
        List of callbacks to pass to LangChain/LangGraph
    """
    callbacks = []

    tracer = setup_langsmith_tracing(settings)
    if tracer:
        callbacks.append(tracer)

    return callbacks


def create_metadata_for_tracing(
    interview_id: UUID | str | None = None,
    candidate_id: UUID | str | None = None,
    question_id: UUID | str | None = None,
    question_type: str | None = None,
    difficulty: str | None = None,
    skill: str | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Create metadata dictionary for LangSmith tracing.

    This function creates a standardized metadata dict for tagging traces.
    All UUID fields are converted to strings.

    Args:
        interview_id: Interview UUID
        candidate_id: Candidate UUID
        question_id: Question UUID
        question_type: Question type (technical, behavioral, etc.)
        difficulty: Question difficulty level
        skill: Skill being evaluated
        **extra: Additional metadata fields

    Returns:
        Metadata dictionary safe for LangSmith
    """
    metadata: Dict[str, Any] = {}

    # Add UUIDs (safe to trace)
    if interview_id:
        metadata["interview_id"] = str(interview_id)
    if candidate_id:
        metadata["candidate_id"] = str(candidate_id)
    if question_id:
        metadata["question_id"] = str(question_id)

    # Add non-PII contextual data
    if question_type:
        metadata["question_type"] = question_type
    if difficulty:
        metadata["difficulty"] = difficulty
    if skill:
        metadata["skill"] = skill

    # Add extra metadata
    metadata.update(extra)

    return metadata
