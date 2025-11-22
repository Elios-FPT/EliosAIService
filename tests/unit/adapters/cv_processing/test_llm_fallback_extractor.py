"""Unit tests for LLMFallbackExtractor."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.cv_processing.llm_fallback_extractor import (
    LLMFallbackExtractor,
    NoOpLLMFallbackExtractor,
)


class TestNoOpLLMFallbackExtractor:
    """Test suite for NoOpLLMFallbackExtractor."""

    @pytest.mark.asyncio
    async def test_fill_gaps_returns_unchanged(self) -> None:
        """Test that no-op extractor returns results unchanged."""
        extractor = NoOpLLMFallbackExtractor()
        merged_results = {"name": "John", "emails": ["john@example.com"]}

        result = await extractor.fill_gaps(merged_results, "CV text")

        assert result == merged_results


class TestLLMFallbackExtractor:
    """Test suite for LLMFallbackExtractor."""

    @pytest.fixture
    def mock_openai_client(self) -> MagicMock:
        """Create mock OpenAI client."""
        client = MagicMock()
        client.chat.completions.create = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_openai_client: MagicMock) -> LLMFallbackExtractor:
        """Create extractor with mocked OpenAI client."""
        with patch("src.adapters.cv_processing.llm_fallback_extractor.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_openai_client
            extractor = LLMFallbackExtractor()
            extractor.client = mock_openai_client
            return extractor


    @pytest.mark.asyncio
    async def test_fill_gaps_missing_name(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that LLM extracts missing name."""
        merged_results = {"emails": ["test@example.com"], "skills": []}
        cv_text = "John Doe is a software engineer."

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "John Doe", "summary": "Test summary", "topics": ["Python"], "education": "Bachelor\'s"}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, cv_text)

        assert result["name"] == "John Doe"
        assert result["summary"] == "Test summary"
        assert result["topics"] == ["Python"]

    @pytest.mark.asyncio
    async def test_fill_gaps_missing_email(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that LLM extracts missing email."""
        merged_results = {"name": "Jane Doe", "skills": []}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"email": "jane@example.com", "summary": "Summary", "topics": [], "education": null}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, "CV text")

        assert result["emails"] == ["jane@example.com"]

    @pytest.mark.asyncio
    async def test_fill_gaps_missing_skills(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that LLM extracts missing skills."""
        merged_results = {"name": "Bob", "emails": ["bob@example.com"]}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"skills": ["Python", "Docker"], "summary": "Summary", "topics": [], "education": null}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, "CV text")

        skills = result["skills"]
        assert len(skills) == 2
        # LLM fallback extractor returns dicts, not ExtractedSkill objects
        assert isinstance(skills[0], dict)
        assert skills[0]["skill"] == "Python"
        assert skills[1]["skill"] == "Docker"

    @pytest.mark.asyncio
    async def test_fill_gaps_generate_summary(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that summary is always generated."""
        merged_results = {"name": "Alice", "emails": ["alice@example.com"], "skills": []}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"summary": "Experienced developer with 5 years", "topics": [], "education": null}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, "CV text")

        assert result["summary"] == "Experienced developer with 5 years"

    @pytest.mark.asyncio
    async def test_fill_gaps_generate_topics(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that topics are always generated."""
        merged_results = {"name": "Charlie", "emails": ["charlie@example.com"], "skills": []}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"topics": ["System Design", "Algorithms", "Python"], "summary": "Summary", "education": null}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, "CV text")

        assert result["topics"] == ["System Design", "Algorithms", "Python"]

    @pytest.mark.asyncio
    async def test_fill_gaps_extract_education(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that education level is extracted."""
        merged_results = {"name": "David", "emails": ["david@example.com"], "skills": []}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"education": "Master\'s", "summary": "Summary", "topics": []}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, "CV text")

        assert result["education_level"] == "Master's"

    @pytest.mark.asyncio
    async def test_fill_gaps_handles_llm_failure(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that extractor handles LLM call failures gracefully."""
        merged_results = {"name": "Eve", "emails": ["eve@example.com"]}
        mock_openai_client.chat.completions.create.side_effect = Exception("API error")

        result = await extractor.fill_gaps(merged_results, "CV text")

        # Should return original results unchanged
        assert result == merged_results

    @pytest.mark.asyncio
    async def test_fill_gaps_empty_cv(
        self,
        extractor: LLMFallbackExtractor,
        mock_openai_client: MagicMock,
    ) -> None:
        """Test that extractor handles empty CV text gracefully."""
        merged_results = {"name": None, "emails": [], "skills": []}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": null, "email": null, "skills": [], "summary": null, "topics": [], "education": null}'
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await extractor.fill_gaps(merged_results, "")

        # Summary is only added if not null, so it may not be in result
        assert result.get("summary") is None or "summary" not in result
        # Topics should be empty list
        assert result.get("topics", []) == []

    def test_build_extraction_prompt_includes_all_fields(self, extractor: LLMFallbackExtractor) -> None:
        """Test that prompt includes all requested fields."""
        fields = ["name", "email", "skills", "summary", "topics"]
        prompt = extractor._build_extraction_prompt("Sample CV text", fields)

        assert "name" in prompt
        assert "email" in prompt
        assert "skills" in prompt
        assert "summary" in prompt
        assert "topics" in prompt
        assert "Sample CV text" in prompt

    def test_build_extraction_prompt_truncates_long_cv(self, extractor: LLMFallbackExtractor) -> None:
        """Test that prompt truncates CV text to 2000 chars."""
        long_cv = "A" * 3000
        prompt = extractor._build_extraction_prompt(long_cv, ["name"])

        # Should truncate and add "..."
        assert len(prompt) < 3000
        assert "..." in prompt

    def test_clean_json_string_removes_code_blocks(self, extractor: LLMFallbackExtractor) -> None:
        """Test that clean_json_string removes markdown code blocks."""
        dirty_json = '```json\n{"name": "Test"}\n```'
        cleaned = extractor._clean_json_string(dirty_json)

        assert cleaned == '{"name": "Test"}'

    def test_clean_json_string_handles_extra_text(self, extractor: LLMFallbackExtractor) -> None:
        """Test that clean_json_string extracts JSON from text with extra content."""
        dirty_json = 'Here is the result: {"name": "Test"} Some extra text'
        cleaned = extractor._clean_json_string(dirty_json)

        assert cleaned == '{"name": "Test"}'

    def test_clean_json_string_handles_empty_string(self, extractor: LLMFallbackExtractor) -> None:
        """Test that clean_json_string handles empty input."""
        cleaned = extractor._clean_json_string("")

        assert cleaned == "{}"

