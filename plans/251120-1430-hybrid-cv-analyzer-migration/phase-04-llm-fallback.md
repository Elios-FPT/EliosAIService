# Phase 4: LLM Fallback Integration

**Phase ID**: 04
**Duration**: 3-4 days
**Risk Level**: Low
**Dependencies**: Phase 3 (Hybrid Orchestrator)

---

## Context

Implement selective LLM fallback for low-confidence fields. Triggers when aggregate confidence < 0.7. Extracts: summaries, interview topics, missing name/email, education level. Reuses existing OpenAI/LangChain infrastructure.

**Target**: < 30% LLM fallback rate (70%+ CVs skip LLM entirely)

---

## Implementation

### LLMFallbackExtractor (`llm_fallback_extractor.py`)

```python
from typing import Dict, Any
import json
from ...infrastructure.config import Settings
from openai import AsyncOpenAI

class LLMFallbackExtractor:
    """Selective LLM extraction for low-confidence fields.

    Only called when hybrid extraction confidence < 0.7.
    Focuses on: summaries, topics, missing critical fields.
    """

    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(
            base_url=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key
        )
        self.model = "gpt-4o-mini"

    async def fill_gaps(
        self,
        merged_results: Dict[str, Any],
        cv_text: str
    ) -> Dict[str, Any]:
        """Fill missing/low-confidence fields using LLM.

        Args:
            merged_results: Results from Phase 1-2 extraction
            cv_text: Full CV text

        Returns:
            Updated results with LLM-extracted fields
        """
        # Identify missing fields
        needs_extraction = []
        if not merged_results.get("name"):
            needs_extraction.append("name")
        if not merged_results.get("emails"):
            needs_extraction.append("email")
        if not merged_results.get("skills"):
            needs_extraction.append("skills")

        # Always generate: summary, topics
        needs_extraction.extend(["summary", "topics", "education"])

        # Single LLM call for all missing fields
        llm_results = await self._extract_fields(cv_text, needs_extraction)

        # Merge LLM results (fill gaps only)
        if not merged_results.get("name") and llm_results.get("name"):
            merged_results["name"] = llm_results["name"]
        if not merged_results.get("emails") and llm_results.get("email"):
            merged_results["emails"] = [llm_results["email"]]
        if not merged_results.get("skills") and llm_results.get("skills"):
            from ...domain.models.cv_analysis import ExtractedSkill
            merged_results["skills"] = [
                ExtractedSkill(skill=s, category="technical")
                for s in llm_results.get("skills", [])
            ]

        # Always add: summary, topics, education
        merged_results["summary"] = llm_results.get("summary")
        merged_results["topics"] = llm_results.get("topics", [])
        merged_results["education"] = llm_results.get("education")

        return merged_results

    async def _extract_fields(
        self,
        cv_text: str,
        fields: list[str]
    ) -> Dict[str, Any]:
        """Extract multiple fields in single LLM call."""
        prompt = self._build_extraction_prompt(cv_text, fields)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    def _build_extraction_prompt(self, cv_text: str, fields: list[str]) -> str:
        """Build prompt for extracting specified fields."""
        return f"""
Extract the following fields from this CV:

CV Text:
{cv_text[:2000]}  # Truncate to 2000 chars

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
```

### Integration in HybridCVAnalyzerAdapter

```python
# In phase-03 file, update:
from .llm_fallback_extractor import LLMFallbackExtractor

class HybridCVAnalyzerAdapter(CVAnalyzerPort):
    def __init__(self, ...):
        # ... existing code ...
        self.llm_fallback = LLMFallbackExtractor(Settings())

    async def analyze_cv(self, ...):
        # ... existing code ...

        # Layer 3: LLM fallback
        if confidence < self.confidence_threshold and self.use_llm_fallback:
            merged_results = await self.llm_fallback.fill_gaps(
                merged_results,
                cv_text
            )
```

---

## Testing Strategy

### Unit Tests (8 tests)

1. `test_fill_gaps_missing_name` - LLM extracts name
2. `test_fill_gaps_missing_email` - LLM extracts email
3. `test_fill_gaps_missing_skills` - LLM extracts skills
4. `test_fill_gaps_generate_summary` - Always generates summary
5. `test_fill_gaps_generate_topics` - Always generates topics
6. `test_extract_fields_all_present` - All fields in response
7. `test_build_extraction_prompt` - Prompt includes all fields
8. `test_fill_gaps_empty_cv` - Handles empty text gracefully

### Integration Tests (2 tests)

1. **test_llm_fallback_low_confidence_cv**:
   - Input: CV with missing name/email (low confidence)
   - Trigger: Fallback extracts missing fields
   - Assert: All fields populated, summary generated

2. **test_llm_fallback_cost_tracking**:
   - Input: 10 CVs (mix of high/low confidence)
   - Measure: LLM fallback rate
   - Assert: < 30% fallback rate

---

## Success Criteria

- [ ] LLMFallbackExtractor implemented
- [ ] Integrated with HybridCVAnalyzerAdapter
- [ ] 8 unit tests passing
- [ ] 2 integration tests passing
- [ ] LLM fallback rate < 30% (measured on 50 CVs)
- [ ] Cost per CV < $0.003 avg
- [ ] Summary quality validates (human review 20 samples)

---

## Next Steps

After Phase 4:
1. Proceed to Phase 5: Configuration & DI Updates
2. Measure actual cost savings vs legacy adapter

---

**Phase 4 Status**: Ready for Implementation
**Est. Completion**: 3-4 days
