# Hybrid CV Analyzer Migration - Master Plan

**Date**: 2025-11-20
**Plan ID**: 251120-1430
**Status**: Draft
**Estimated Duration**: 3-4 weeks
**Complexity**: High

---

## Executive Summary

Migrate from pure LLM-based CV analysis (3 GPT-4o-mini calls) to hybrid architecture combining rule-based extraction, spaCy NER, and selective LLM fallback. Target: **70-80% cost reduction** while maintaining **90%+ accuracy**.

**Current System**: CVProcessingAdapter makes 3 LLM calls per CV:
1. `generate_cv_info_from_text()` - Extract name, email, skills, experience (300 tokens)
2. `generate_interview_topics()` - Generate topics (500 tokens)
3. `generate_candidate_from_summary()` - Create candidate (200 tokens)

**Target System**: Hybrid orchestrator routes extraction by field type:
- Layer 1 (Rules): Email, phone, dates → 98% accuracy, 0ms latency, $0 cost
- Layer 2 (spaCy NER): Skills, companies, education → 88-92% accuracy, 50ms, $0 cost
- Layer 3 (LLM Fallback): Summaries, topics (only when confidence < 0.7) → 95%+, 2s, $0.001

**Cost Savings**: From ~$0.01/CV (3 LLM calls) to ~$0.002/CV (0.7 LLM calls avg) = **80% reduction**

---

## Architecture Overview

### Current Flow (Pure LLM)
```
CV Upload → Read PDF → 3x GPT-4o-mini calls → CVAnalysis model
             ↓           ↓                      ↓
          pdfplumber  (300+500+200 tokens)  Store in DB
          Cost: ~$0.01/CV, 5-8s latency
```

### Target Flow (Hybrid)
```
CV Upload → Read PDF → Rule Extraction → spaCy NER → Confidence Score → Selective LLM
             ↓           ↓                 ↓           ↓                  ↓
          pdfplumber  Email/Phone/Dates  Skills/Orgs  Aggregate (0-1)   Fill gaps
          98% fields  Regex patterns     en/vi models  Threshold: 0.7    Only if needed
          Cost: ~$0.002/CV, 2-3s latency
```

### Component Architecture
```
HybridCVAnalyzerAdapter (implements CVAnalyzerPort)
├─ RuleBasedExtractor (email, phone, dates, section headers)
├─ SpacyNERExtractor (skills, companies, locations, dates)
├─ ConfidenceScorer (field-level + aggregate scoring)
└─ LLMFallbackExtractor (summaries, topics when confidence < 0.7)
```

---

## Key Requirements

### Functional
- [x] Support PDF, DOCX, TXT formats (existing)
- [x] Return same CVAnalysis model (no breaking changes)
- [x] Implement CVAnalyzerPort interface (2 methods)
- [ ] Support English + Vietnamese (en_core_web_sm, vi_core_news_sm)
- [ ] Extract: name, email, phone, skills, experience, education
- [ ] Calculate confidence scores (0.0-1.0 per field)
- [ ] Trigger LLM fallback when confidence < 0.7
- [ ] Generate interview topics (via LLM or rules)
- [ ] Generate candidate summary

### Non-Functional
- **Performance**: < 3s per CV (vs. 5-8s current)
- **Accuracy**: ≥ 90% overall (measured against human-annotated gold standard)
- **Cost**: < $0.003/CV avg (vs. $0.01 current)
- **Testability**: 80%+ code coverage, unit + integration tests
- **Maintainability**: Clean Architecture, DRY, SOLID principles

### Architectural Constraints
- **Port Interface**: No changes to CVAnalyzerPort (analyze_cv, generate_candidate_from_summary)
- **Domain Model**: No changes to CVAnalysis, ExtractedSkill, Candidate
- **DI Container**: Support both legacy + hybrid via `use_hybrid_cv_analyzer` flag
- **Backwards Compatibility**: CVProcessingAdapter remains available

---

## Phase Breakdown

| Phase | Description | Files | Est. Duration | Risk |
|-------|-------------|-------|---------------|------|
| 1 | Rule-Based Extractor + Confidence Scorer | 3 files, 12 tests | 3-4 days | Low |
| 2 | spaCy NER Extractor Integration | 3 files, 10 tests | 4-5 days | Medium |
| 3 | Hybrid Orchestrator Adapter | 2 files, 15 tests | 5-6 days | High |
| 4 | LLM Fallback Integration | 2 files, 8 tests | 3-4 days | Low |
| 5 | Configuration & DI Updates | 3 files, 5 tests | 2 days | Low |
| 6 | Testing & Validation | N/A (fixtures) | 3-4 days | Medium |
| 7 | Documentation & Migration Guide | 3 docs | 2 days | Low |

**Total**: 22-29 days (calendar), 18-24 days (developer time)

---

## Success Criteria

### Phase Completion Metrics
- [ ] All unit tests passing (80%+ coverage)
- [ ] Integration tests with real CVs (English + Vietnamese)
- [ ] Performance benchmarks: < 3s avg latency, < $0.003 avg cost
- [ ] Accuracy validation: ≥ 90% on 50+ human-annotated CVs
- [ ] No breaking changes to existing API

### Production Readiness
- [ ] A/B test plan prepared (10% traffic to hybrid)
- [ ] Rollback plan documented
- [ ] Monitoring metrics defined (latency, cost, accuracy)
- [ ] Feature flag: `use_hybrid_cv_analyzer=false` (default, safe rollback)

---

## Risk Assessment

### High Risks
1. **spaCy Model Accuracy** (Vietnamese): Risk = Medium
   - Mitigation: Test `vi_core_news_sm` accuracy on sample CVs, fallback to LLM
   - Contingency: Use LLM-first for Vietnamese CVs if NER accuracy < 75%

2. **Skill Taxonomy Maintenance**: Risk = Medium
   - Mitigation: Start with 500 skills from existing `skill_patterns.json`
   - Contingency: LLM-based skill extraction if PhraseMatcher hit rate < 60%

3. **Confidence Threshold Calibration**: Risk = Low
   - Mitigation: A/B test thresholds (0.65, 0.70, 0.75) on production CVs
   - Contingency: Use conservative threshold (0.75) initially

### Medium Risks
1. **Integration Complexity**: Multiple extractors + orchestration logic
   - Mitigation: Extensive unit testing of each extractor independently
2. **Performance Regression**: spaCy model loading overhead
   - Mitigation: Singleton pattern for model loading, benchmark Phase 2

### Low Risks
1. **Backwards Compatibility**: Feature flag + legacy adapter preserved
2. **LLM Fallback Cost**: Only triggers for 20-30% of CVs (calibrated threshold)

---

## Dependencies

### External Libraries
- `spacy>=3.7.0` (already in dependencies)
- `en_core_web_sm` - English NER model (download: `python -m spacy download en_core_web_sm`)
- `vi_core_news_sm` - Vietnamese NER model (download: `python -m spacy download vi_core_news_sm`)
- Python `re` module (regex, built-in)
- Existing: `pdfplumber`, `openai`, `langchain_openai`

### Internal Dependencies
- CVAnalyzerPort (no changes)
- CVAnalysis, ExtractedSkill models (no changes)
- Settings class (add 3 new config fields)
- DI Container (add hybrid adapter injection)

---

## Related Documents

- **Phase Plans**: `phase-01-rule-based-extractor.md` through `phase-07-documentation.md`
- **Research Reports**:
  - `research/researcher-01-spacy-regex-report.md` (NER patterns, confidence scoring)
  - `research/researcher-02-hybrid-architecture-report.md` (production benchmarks)
- **Codebase Standards**: `../../docs/code-standards.md`
- **Architecture**: `../../docs/system-architecture.md`

