"""LLM fallback extractor interfaces used by HybridCVAnalyzerAdapter."""

from __future__ import annotations

from datetime import datetime

def debug_print(msg: str):
    """Helper function to print debug messages with timestamps."""
    print(f"DEBUG [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]: {msg}", flush=True)

debug_print("llm_fallback_extractor.py: Starting imports...")

import json
import re
from typing import Any, Protocol

from openai import AsyncOpenAI

# ExtractedSkill no longer needed - using dict format for skills
from ...infrastructure.config import Settings

debug_print("llm_fallback_extractor.py: Imports completed")


class LLMFallbackExtractorProtocol(Protocol):
    """Protocol for LLM fallback extractor implementations."""

    async def fill_gaps(
        self,
        merged_results: dict[str, Any],
        cv_text: str,
    ) -> dict[str, Any]:
        """Fill missing or low-confidence fields via LLM.

        Args:
            merged_results: Current extraction results.
            cv_text: Raw CV text for context.

        Returns:
            Updated results with LLM-enriched fields.
        """


class NoOpLLMFallbackExtractor(LLMFallbackExtractorProtocol):
    """Default fallback extractor used before Phase 4 implementation."""

    async def fill_gaps(
        self,
        merged_results: dict[str, Any],
        cv_text: str,
    ) -> dict[str, Any]:
        """Return results unchanged (no-op)."""

        return merged_results


class LLMFallbackExtractor(LLMFallbackExtractorProtocol):
    """Selective LLM extraction for low-confidence fields.

    Only called when hybrid extraction confidence < 0.7.
    Focuses on: summaries, topics, missing critical fields.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize LLM fallback extractor.

        Args:
            settings: Application settings (defaults to new Settings instance)
        """
        self.settings = settings or Settings()
        self.client = AsyncOpenAI(
            base_url=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
        )
        self.model = "gpt-4o-mini"

    async def fill_gaps(
        self,
        merged_results: dict[str, Any],
        cv_text: str,
    ) -> dict[str, Any]:
        """Fill missing/low-confidence fields using LLM.

        Args:
            merged_results: Results from Phase 1-2 extraction
            cv_text: Full CV text

        Returns:
            Updated results with LLM-extracted fields
        """
        # Identify missing fields
        needs_extraction: list[str] = []
        if not merged_results.get("name"):
            needs_extraction.append("name")
        if not merged_results.get("emails"):
            needs_extraction.append("email")
        if not merged_results.get("skills"):
            needs_extraction.append("skills")

        # Always generate: summary, topics, education
        needs_extraction.extend(["summary", "topics", "education"])

        # Single LLM call for all missing fields
        try:
            llm_results = await self._extract_fields(cv_text, needs_extraction)
        except Exception:
            # If LLM call fails, return merged_results unchanged
            return merged_results

        # Merge LLM results (fill gaps only)
        if not merged_results.get("name") and llm_results.get("name"):
            merged_results["name"] = llm_results["name"]
        if not merged_results.get("emails") and llm_results.get("email"):
            merged_results["emails"] = [llm_results["email"]]
        if not merged_results.get("skills") and llm_results.get("skills"):
            merged_results["skills"] = [
                {"skill": s, "category": "technical"}
                for s in llm_results.get("skills", [])
            ]

        # Always add: summary, topics, education
        if llm_results.get("summary"):
            merged_results["summary"] = llm_results["summary"]
        if llm_results.get("topics"):
            merged_results["topics"] = llm_results.get("topics", [])
        if llm_results.get("education"):
            merged_results["education_level"] = llm_results["education"]

        return merged_results

    async def _extract_fields(
        self,
        cv_text: str,
        fields: list[str],
    ) -> dict[str, Any]:
        """Extract multiple fields in single LLM call.

        Args:
            cv_text: Full CV text content
            fields: List of field names to extract

        Returns:
            Dictionary with extracted fields

        Raises:
            Exception: If LLM call fails or response is invalid
        """
        prompt = self._build_extraction_prompt(cv_text, fields)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            return {}

        # Clean JSON string (handle code blocks, extra text)
        cleaned = self._clean_json_string(content)
        return json.loads(cleaned)

    def _build_extraction_prompt(self, cv_text: str, fields: list[str]) -> str:
        """Build prompt for extracting specified fields.

        Args:
            cv_text: Full CV text content
            fields: List of field names to extract

        Returns:
            Formatted prompt string
        """
        # Truncate CV text to 2000 chars to stay within token limits
        truncated_cv = cv_text[:2000] + ("..." if len(cv_text) > 2000 else "")

        return f"""Extract the following fields from this CV:

CV Text:
{truncated_cv}

Fields to extract: {', '.join(fields)}

Response format (JSON):
{{
  "name": "Full Name" or null,
  "email": "email@example.com" or null,
  "skills": ["Skill1", "Skill2", ...] or [],
  "summary": "3-sentence candidate summary" or null,
  "topics": ["Topic1", "Topic2", ...] (interview topics, 5-7 items),
  "education": "Highest degree (Bachelor's, Master's, PhD)" or null
}}

Rules:
- Only include fields that can be confidently extracted
- If field not found, use null or []
- Summary: Focus on experience, skills, notable achievements (< 200 words)
- Topics: Technical depth, problem-solving, skill-specific
"""

    def _clean_json_string(self, s: str) -> str:
        """Extract JSON from string, handling code blocks and extra text.

        Args:
            s: Raw response string

        Returns:
            Cleaned JSON string
        """
        if not s:
            return "{}"
        s = s.strip()

        # Remove code block markers
        s = re.sub(r"^```json\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"```$", "", s)

        # Find first { and last }
        start = s.find("{")
        end = s.rfind("}") + 1
        if start == -1 or end == 0:
            return "{}"
        return s[start:end]

