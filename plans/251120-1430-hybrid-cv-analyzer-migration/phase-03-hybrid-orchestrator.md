# Phase 3: Hybrid Orchestrator Adapter

**Phase ID**: 03
**Duration**: 5-6 days
**Risk Level**: High
**Dependencies**: Phase 1 (Rules + Confidence), Phase 2 (spaCy NER)

---

## Context

Implement `HybridCVAnalyzerAdapter` - orchestrator coordinating rule-based, NER, and LLM extractors. Routes extraction by field type, aggregates results, applies confidence thresholds, triggers LLM fallback when confidence < 0.7. Core integration layer implementing CVAnalyzerPort interface.

---

## Overview

**Key Responsibilities**:
1. Orchestrate 3 extraction layers (Rules → NER → LLM)
2. Merge extraction results (conflict resolution)
3. Calculate aggregate confidence scores
4. Trigger selective LLM fallback
5. Map to domain models (CVAnalysis, ExtractedSkill, Candidate)
6. Implement CVAnalyzerPort interface (no breaking changes)

**Routing Strategy** (from research):
- Email, phone, URLs → Rule-based only (98% accuracy)
- Skills, companies, locations → NER first, LLM fallback
- Summaries, topics → LLM only
- Name → NER first, fallback to LLM

---

## Architecture

### Component Interactions
```
HybridCVAnalyzerAdapter (orchestrator)
    ├─ RuleBasedExtractor (Phase 1) → {emails, phones, dates, sections}
    ├─ SpacyNERExtractor (Phase 2) → {name, companies, skills, experience}
    ├─ LLMFallbackExtractor (Phase 4) → {summaries, topics when needed}
    └─ ConfidenceScorer (Phase 1) → aggregate confidence → LLM trigger
```

### Extraction Pipeline
```
CVAnalyzerPort.analyze_cv(cv_file_path, candidate_id)
    ↓
read_cv(cv_file_path) → cv_text
    ↓
[Layer 1] RuleBasedExtractor.extract(cv_text)
    ↓ (parallel)
[Layer 2] SpacyNERExtractor.extract(cv_text)
    ↓
merge_results(rule_results, ner_results)
    ↓
ConfidenceScorer.aggregate_confidence(merged_results)
    ↓
if confidence < 0.7:
    [Layer 3] LLMFallbackExtractor.fill_gaps(merged_results, cv_text)
    ↓
map_to_cv_analysis(final_results) → CVAnalysis model
    ↓
return CVAnalysis
```

---

## Implementation

### HybridCVAnalyzerAdapter (`hybrid_cv_analyzer.py`)

```python
from typing import Dict, Any
from uuid import UUID
import asyncio
import pdfplumber
from ...domain.ports.cv_analyzer_port import CVAnalyzerPort
from ...domain.models.cv_analysis import CVAnalysis, ExtractedSkill
from ...domain.models.candidate import Candidate
from .rule_based_extractor import RuleBasedExtractor
from .spacy_ner_extractor import SpacyNERExtractor
from .confidence_scorer import ConfidenceScorer

class HybridCVAnalyzerAdapter(CVAnalyzerPort):
    """Hybrid CV analyzer orchestrating rules, NER, and selective LLM fallback.

    Implements CVAnalyzerPort interface with no breaking changes.
    Target: 70-80% LLM cost reduction, 90%+ accuracy.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        use_llm_fallback: bool = True
    ):
        """Initialize hybrid analyzer.

        Args:
            confidence_threshold: Min confidence to skip LLM (default 0.7)
            use_llm_fallback: Enable LLM for low-confidence fields
        """
        self.rule_extractor = RuleBasedExtractor()
        self.ner_extractor = SpacyNERExtractor()
        self.confidence_scorer = ConfidenceScorer()
        self.confidence_threshold = confidence_threshold
        self.use_llm_fallback = use_llm_fallback

    async def analyze_cv(
        self,
        cv_file_path: str,
        candidate_id: UUID
    ) -> CVAnalysis:
        """Analyze CV using hybrid extraction strategy.

        Port interface implementation (CVAnalyzerPort).

        Extraction flow:
        1. Read CV → text
        2. Rule-based extraction (emails, phones, dates)
        3. NER extraction (skills, companies, experience)
        4. Merge results + calculate confidence
        5. LLM fallback if confidence < threshold
        6. Map to CVAnalysis domain model
        """
        # Read CV file
        cv_text = self._read_cv(cv_file_path)

        # Layer 1: Rule-based extraction (fast, deterministic)
        rule_results = self.rule_extractor.extract(cv_text)

        # Layer 2: spaCy NER extraction (context-aware, zero cost)
        ner_results = self.ner_extractor.extract(cv_text)

        # Merge results with conflict resolution
        merged_results = self._merge_extraction_results(rule_results, ner_results)

        # Calculate aggregate confidence
        confidence = self.confidence_scorer.aggregate_confidence(
            merged_results["field_confidences"]
        )

        # Layer 3: LLM fallback for low-confidence fields
        if confidence < self.confidence_threshold and self.use_llm_fallback:
            # TODO: Implement in Phase 4
            # merged_results = await self._llm_fallback(merged_results, cv_text)
            pass

        # Map to domain model
        cv_analysis = self._map_to_cv_analysis(
            merged_results,
            cv_file_path,
            candidate_id
        )

        return cv_analysis

    async def generate_candidate_from_summary(
        self,
        summary_info: str,
        cv_file_path: str,
        candidate_id: UUID
    ) -> Candidate:
        """Generate Candidate from summary.

        Port interface implementation (CVAnalyzerPort).
        Uses NER if summary contains CV text, else LLM.
        """
        # Try NER extraction first
        ner_results = self.ner_extractor.extract(summary_info)
        name = ner_results.get("name")

        # Extract email from summary (rule-based)
        rule_results = self.rule_extractor.extract(summary_info)
        emails = rule_results.get("emails", [])
        email = emails[0] if emails else "no-email@example.com"

        # Fallback to defaults if NER fails
        if not name or ner_results["confidence"]["overall"] < 0.5:
            # TODO: Phase 4 - Use LLM to extract name
            name = "Unknown Candidate"

        return Candidate(
            id=candidate_id,
            name=name,
            email=email,
            cv_file_path=cv_file_path
        )

    def _read_cv(self, file_path: str) -> str:
        """Read CV text from PDF or TXT file."""
        if file_path.lower().endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

    def _merge_extraction_results(
        self,
        rule_results: Dict[str, Any],
        ner_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge rule-based and NER results with conflict resolution.

        Conflict resolution strategy:
        - Email, phone, URLs: Prefer rule-based (higher accuracy)
        - Name, companies, locations: Prefer NER (context-aware)
        - Skills: Merge both (union)
        - Dates: Merge (union)
        """
        return {
            # Structured fields: prefer rules
            "emails": rule_results.get("emails", []),
            "phones": rule_results.get("phones", []),
            "urls": rule_results.get("urls", []),
            "sections": rule_results.get("sections", {}),

            # Entity fields: prefer NER
            "name": ner_results.get("name"),
            "companies": ner_results.get("companies", []),
            "locations": ner_results.get("locations", []),

            # Skills: merge (NER PhraseMatcher is primary)
            "skills": ner_results.get("skills", []),

            # Dates: merge both sources
            "dates": list(set(
                rule_results.get("dates", []) +
                ner_results.get("dates", [])
            )),

            # Experience: prefer NER calculation
            "experience_years": ner_results.get("experience_years"),

            # Confidence scores (for aggregate)
            "field_confidences": {
                "email": self.confidence_scorer.score_field("email", rule_results.get("emails", []), True),
                "phone": self.confidence_scorer.score_field("phone", rule_results.get("phones", []), True),
                "name": ner_results["confidence"]["fields"].get("name", 0.0),
                "companies": ner_results["confidence"]["fields"].get("companies", 0.0),
                "skills": ner_results["confidence"]["fields"].get("skills", 0.0),
            }
        }

    def _map_to_cv_analysis(
        self,
        merged_results: Dict[str, Any],
        cv_file_path: str,
        candidate_id: UUID
    ) -> CVAnalysis:
        """Map merged extraction results to CVAnalysis domain model."""
        from datetime import datetime

        # Map skills to ExtractedSkill objects
        skills = merged_results.get("skills", [])

        # Build CV analysis
        return CVAnalysis(
            candidate_id=candidate_id,
            cv_file_path=cv_file_path,
            extracted_text="",  # TODO: Store full text if needed
            skills=skills,
            work_experience_years=merged_results.get("experience_years"),
            education_level=None,  # TODO: Extract in Phase 4
            suggested_topics=[],  # TODO: Generate in Phase 4
            suggested_difficulty=self._calculate_difficulty(
                merged_results.get("experience_years", 0)
            ),
            embedding=None,
            summary=None,  # TODO: Generate in Phase 4
            metadata={
                "extraction_method": "hybrid",
                "confidence": merged_results.get("field_confidences", {}),
                "emails": merged_results.get("emails", []),
                "phones": merged_results.get("phones", []),
                "companies": merged_results.get("companies", []),
            },
            created_at=datetime.now().isoformat()
        )

    def _calculate_difficulty(self, experience_years: float | None) -> str:
        """Calculate suggested interview difficulty from experience."""
        if not experience_years:
            return "medium"
        if experience_years >= 10:
            return "expert"
        elif experience_years >= 5:
            return "advanced"
        elif experience_years >= 2:
            return "medium"
        else:
            return "beginner"
```

---

## Testing Strategy

### Unit Tests (15 tests)

1. `test_analyze_cv_high_confidence` - All fields extracted, no LLM
2. `test_analyze_cv_low_confidence` - Triggers LLM fallback
3. `test_merge_results_prefer_rules_email` - Email from rules, not NER
4. `test_merge_results_prefer_ner_name` - Name from NER, not rules
5. `test_merge_results_union_skills` - Skills merged
6. `test_merge_results_union_dates` - Dates merged
7. `test_confidence_threshold_trigger` - 0.69 triggers fallback, 0.71 skips
8. `test_generate_candidate_from_summary` - Extract name + email
9. `test_map_to_cv_analysis_all_fields` - Complete mapping
10. `test_calculate_difficulty_experience` - 5 years → "advanced"
11. `test_read_cv_pdf` - PDF parsing
12. `test_read_cv_txt` - TXT parsing
13. `test_empty_cv_handling` - Empty text graceful handling
14. `test_malformed_cv_handling` - Invalid sections
15. `test_confidence_aggregation` - Weighted average

### Integration Tests (3 tests)

1. **test_hybrid_analyzer_english_cv_full_pipeline**:
   - Input: Real English PDF CV
   - Extract: All fields (rules + NER)
   - Assert: CVAnalysis populated, confidence > 0.80

2. **test_hybrid_analyzer_vietnamese_cv**:
   - Input: Vietnamese CV
   - Assert: Language detected, entities extracted, confidence > 0.70

3. **test_hybrid_analyzer_performance_benchmark**:
   - Input: 10 CVs
   - Measure: Avg latency, LLM fallback rate
   - Assert: p95 latency < 3s, fallback < 30%

---

## Success Criteria

- [ ] HybridCVAnalyzerAdapter implements CVAnalyzerPort (2 methods)
- [ ] Returns same CVAnalysis model structure
- [ ] 15 unit tests passing
- [ ] 3 integration tests passing
- [ ] Code coverage ≥ 85%
- [ ] Latency < 3s per CV (without LLM)
- [ ] Confidence calculation accurate
- [ ] Merge logic handles conflicts correctly
- [ ] No breaking changes to existing code

---

## Rollback Plan

Phase 3 adds new adapter only. Rollback = delete file, keep DI container pointing to CVProcessingAdapter.

---

## Next Steps

**After Phase 3**:
1. Proceed to Phase 4: LLM Fallback Integration
2. Test on 50+ real CVs (English + Vietnamese)
3. Benchmark cost savings vs legacy adapter

---

**Phase 3 Status**: Ready for Implementation (after Phase 1-2)
**Est. Completion**: 5-6 days
