# Hybrid CV Analyzer Migration Plan

**Plan ID**: 251120-1430
**Date Created**: 2025-11-20
**Status**: Draft - Ready for Review
**Estimated Duration**: 22-29 days (3-4 weeks)

---

## Quick Navigation

- **Master Plan**: [`plan.md`](./plan.md) - Executive summary, architecture, success criteria
- **Phase Plans**: Detailed implementation guides
  - [Phase 1: Rule-Based Extractor + Confidence Scorer](./phase-01-rule-based-extractor.md) (3-4 days)
  - [Phase 2: spaCy NER Extractor Integration](./phase-02-spacy-ner-extractor.md) (4-5 days)
  - [Phase 3: Hybrid Orchestrator Adapter](./phase-03-hybrid-orchestrator.md) (5-6 days)
  - [Phase 4: LLM Fallback Integration](./phase-04-llm-fallback.md) (3-4 days)
  - [Phase 5: Configuration & DI Updates](./phase-05-configuration-di.md) (2 days)
  - [Phase 6: Testing & Validation](./phase-06-testing-validation.md) (3-4 days)
  - [Phase 7: Documentation & Migration Guide](./phase-07-documentation-migration.md) (2 days)
- **Research Reports**: Background research and technical analysis
  - [spaCy NER Patterns & Confidence Scoring](./research/researcher-01-spacy-regex-report.md)
  - [Hybrid Architecture & Production Benchmarks](./research/researcher-02-hybrid-architecture-report.md)

---

## Executive Summary

### Problem Statement
Current CV analysis uses 3 LLM calls per CV (~$0.01 cost, 5-8s latency). Cost-prohibitive at scale, slower than competitors.

### Proposed Solution
Migrate to hybrid architecture combining:
1. **Rule-Based Extraction** (Layer 1): Email, phone, dates → 98% accuracy, $0 cost, 50ms
2. **spaCy NER** (Layer 2): Skills, companies, locations → 88-92% accuracy, $0 cost, 300ms
3. **LLM Fallback** (Layer 3): Summaries, low-confidence fields → 95%+ accuracy, only when needed

### Expected Outcomes
- **Cost Reduction**: 70-80% (from $0.01 → $0.002 per CV)
- **Latency Improvement**: 40-60% (from 5-8s → 2-3s avg)
- **Accuracy**: Maintain 90%+ (same or better than legacy)
- **Backwards Compatibility**: No breaking changes to API or domain models

---

## Implementation Overview

### Architecture Diagram
```
┌──────────────────────────────────────────────────────────────┐
│                  CVAnalyzerPort (Interface)                  │
└──────────────────────────────────────────────────────────────┘
                          ↓ implements
┌──────────────────────────────────────────────────────────────┐
│            HybridCVAnalyzerAdapter (Orchestrator)            │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐          │
│  │  Layer 1   │  │  Layer 2   │  │   Layer 3    │          │
│  │   Rules    │→ │  spaCy NER │→ │ LLM Fallback │          │
│  │  (Phase 1) │  │ (Phase 2)  │  │  (Phase 4)   │          │
│  └────────────┘  └────────────┘  └──────────────┘          │
│         ↓                ↓                 ↓                 │
│  ┌─────────────────────────────────────────────┐            │
│  │    ConfidenceScorer (Phase 1)               │            │
│  │    Aggregate confidence → Trigger LLM?      │            │
│  └─────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
                          ↓ returns
┌──────────────────────────────────────────────────────────────┐
│  CVAnalysis (Domain Model) - No breaking changes            │
└──────────────────────────────────────────────────────────────┘
```

### Extraction Flow
```
CV Upload (PDF/DOCX/TXT)
    ↓
Read CV Text
    ↓
┌─────────────────────────────────┐
│ Layer 1: Rule-Based Extraction  │ ← 50ms, 98% accuracy
│ - Email, phone, URLs            │
│ - Dates, section headers        │
└─────────────────────────────────┘
    ↓ (parallel)
┌─────────────────────────────────┐
│ Layer 2: spaCy NER Extraction   │ ← 300ms, 88-92% accuracy
│ - Name, companies, locations    │
│ - Skills (PhraseMatcher)        │
│ - Experience calculation        │
└─────────────────────────────────┘
    ↓
Merge Results + Calculate Confidence
    ↓
if confidence < 0.7:
┌─────────────────────────────────┐
│ Layer 3: LLM Fallback           │ ← 2s, 95%+ accuracy
│ - Fill missing critical fields  │
│ - Generate summary & topics     │
│ - Extract education level       │
└─────────────────────────────────┘
    ↓
Map to CVAnalysis Domain Model
    ↓
Return CVAnalysis
```

---

## Phase Breakdown

| Phase | Description | Deliverables | Duration | Risk |
|-------|-------------|--------------|----------|------|
| **Phase 1** | Rule-Based Extractor + Confidence Scorer | 2 files, 12 tests | 3-4 days | Low |
| **Phase 2** | spaCy NER Extractor Integration | 3 files, 10 tests | 4-5 days | Medium |
| **Phase 3** | Hybrid Orchestrator Adapter | 2 files, 15 tests | 5-6 days | High |
| **Phase 4** | LLM Fallback Integration | 2 files, 8 tests | 3-4 days | Low |
| **Phase 5** | Configuration & DI Updates | 3 files, 5 tests | 2 days | Low |
| **Phase 6** | Testing & Validation | Validation reports | 3-4 days | Medium |
| **Phase 7** | Documentation & Migration Guide | 5 docs | 2 days | Low |
| **TOTAL** | | **7 adapters, 50+ tests** | **22-29 days** | - |

---

## Key Deliverables

### New Adapter Files (7 total)
```
src/adapters/cv_processing/
├── rule_based_extractor.py          # Phase 1 - Regex extraction
├── confidence_scorer.py             # Phase 1 - Confidence calculation
├── spacy_ner_extractor.py           # Phase 2 - spaCy NER
├── skill_matcher.py                 # Phase 2 - Skill PhraseMatcher
├── hybrid_cv_analyzer.py            # Phase 3 - Orchestrator
├── llm_fallback_extractor.py        # Phase 4 - LLM fallback
└── skill_patterns.json (ENHANCED)   # Phase 2 - Categorized skills
```

### Test Files (50+ tests)
```
tests/unit/adapters/cv_processing/
├── test_rule_based_extractor.py     # 8 tests
├── test_confidence_scorer.py        # 4 tests
├── test_spacy_ner_extractor.py      # 6 tests
├── test_skill_matcher.py            # 4 tests
├── test_hybrid_cv_analyzer.py       # 15 tests
└── test_llm_fallback_extractor.py   # 8 tests

tests/integration/
├── test_rule_based_extraction.py    # 2 tests
├── test_spacy_ner_full_pipeline.py  # 2 tests
└── test_hybrid_analyzer_e2e.py      # 3 tests
```

### Documentation (5 files)
```
docs/
├── hybrid-cv-analyzer.md                    # Architecture + usage
├── hybrid-cv-analyzer-migration-guide.md    # Migration steps
├── system-architecture.md (UPDATED)         # Add hybrid section
├── codebase-summary.md (UPDATED)            # Add new files
└── README.md (UPDATED)                      # Add features
```

---

## Success Criteria

### Technical Metrics
- [ ] Code coverage ≥ 80% (all phases)
- [ ] All unit tests passing (50+ tests)
- [ ] All integration tests passing (15+ tests)
- [ ] No linting errors (ruff, black, mypy)
- [ ] Type hints complete
- [ ] Docstrings for all public APIs

### Performance Metrics
- [ ] Latency p95 < 3s (vs. 5-8s legacy)
- [ ] Cost per CV < $0.003 (vs. $0.01 legacy)
- [ ] LLM fallback rate 20-30% (calibrated threshold)
- [ ] Memory footprint < 500MB (spaCy models loaded)

### Accuracy Metrics
- [ ] Overall accuracy ≥ 90% (on 50+ human-annotated CVs)
- [ ] Email extraction: ≥ 98%
- [ ] Skills extraction: ≥ 85%
- [ ] Experience calculation: ≥ 90%
- [ ] Vietnamese CV support: ≥ 75%

### Production Readiness
- [ ] Feature flag: `use_hybrid_cv_analyzer=false` (safe default)
- [ ] A/B test plan prepared
- [ ] Rollback plan documented
- [ ] Monitoring metrics defined
- [ ] Documentation complete

---

## Risk Management

### High Risks
1. **spaCy Vietnamese NER Accuracy** (Risk: Medium)
   - Mitigation: Test on sample Vietnamese CVs, lower threshold to 0.6
   - Contingency: LLM-first for Vietnamese if accuracy < 70%

2. **Skill Taxonomy Maintenance** (Risk: Medium)
   - Mitigation: Start with 500 skills from existing patterns
   - Contingency: LLM-based extraction if hit rate < 60%

### Medium Risks
1. **Integration Complexity**: Multiple extractors + orchestration
   - Mitigation: Extensive unit testing per extractor
2. **Performance Regression**: spaCy model loading overhead
   - Mitigation: Singleton pattern, benchmark Phase 2

### Low Risks
1. **Backwards Compatibility**: Feature flag + legacy adapter preserved
2. **LLM Fallback Cost**: Only 20-30% CVs trigger fallback

---

## Getting Started

### For Developers

1. **Read Master Plan**: [`plan.md`](./plan.md)
2. **Review Architecture**: `docs/system-architecture.md`
3. **Check Research**: `./research/` folder
4. **Start Phase 1**: [`phase-01-rule-based-extractor.md`](./phase-01-rule-based-extractor.md)

### For QA/Testing

1. **Read Phase 6**: [`phase-06-testing-validation.md`](./phase-06-testing-validation.md)
2. **Prepare Test Data**: 50 CVs (25 English, 25 Vietnamese)
3. **Setup Gold Standard**: Human-annotated labels

### For Product/Business

1. **Review Master Plan**: Cost savings, timeline, risks
2. **Approve Phases**: Sign-off required before Phase 1
3. **Monitor Rollout**: A/B test results, gradual traffic shift

---

## FAQs

### Q: Will this break existing CV analysis API?
**A**: No. HybridCVAnalyzerAdapter implements same CVAnalyzerPort interface, returns same CVAnalysis model. Backwards compatible.

### Q: What if hybrid analyzer fails in production?
**A**: Feature flag `use_hybrid_cv_analyzer=false` instantly rolls back to legacy CVProcessingAdapter. No code deployment needed.

### Q: How do we test Vietnamese CV accuracy?
**A**: Phase 6 includes 25 Vietnamese CVs with human annotations. spaCy `vi_core_news_sm` model provides 75%+ accuracy. LLM fallback covers gaps.

### Q: Can we adjust confidence threshold after deployment?
**A**: Yes. `hybrid_confidence_threshold` is env variable (default 0.7). Adjust without code changes.

### Q: What's the total cost savings at 10,000 CVs/month?
**A**:
- Legacy: 10,000 × $0.01 = **$100/month**
- Hybrid: 10,000 × $0.002 = **$20/month**
- **Savings: $80/month (80% reduction)**

### Q: How long until we see ROI?
**A**: Development cost ~4 weeks. At 10K CVs/month, ROI achieved in < 1 month after production rollout.

---

## Support & Contact

- **Technical Lead**: [TBD]
- **Project Manager**: [TBD]
- **QA Lead**: [TBD]
- **Plan Author**: AI Planner (Claude Code Agent)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2025-11-20 | AI Planner | Initial draft - all 7 phases |

---

## Approval Status

| Stakeholder | Role | Status | Date | Signature |
|-------------|------|--------|------|-----------|
| Tech Lead | Architecture Review | ⏳ Pending | - | - |
| Product Manager | Business Approval | ⏳ Pending | - | - |
| QA Lead | Test Strategy | ⏳ Pending | - | - |
| DevOps Lead | Deployment Plan | ⏳ Pending | - | - |

---

**Next Action**: Schedule review meeting with stakeholders to approve Phase 1 kickoff.

**Target Start Date**: TBD (after approval)
**Target Completion**: TBD + 4 weeks
