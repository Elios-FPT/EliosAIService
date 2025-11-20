# Phase 7: Documentation & Migration Guide

**Phase ID**: 07
**Duration**: 2 days
**Risk Level**: Low
**Dependencies**: Phase 6 (Testing complete)

---

## Context

Create comprehensive documentation for hybrid CV analyzer. Migration guide for production rollout. Update existing docs (system architecture, codebase summary).

---

## Deliverables

### 1. Hybrid CV Analyzer Documentation (`docs/hybrid-cv-analyzer.md`)

**Contents**:
- Architecture overview (3-layer extraction)
- Component descriptions (RuleBasedExtractor, SpacyNERExtractor, etc.)
- Configuration options (all settings)
- Usage examples (API + code)
- Performance benchmarks (from Phase 6)
- Cost savings analysis
- Troubleshooting guide

**Structure**:
```markdown
# Hybrid CV Analyzer Documentation

## Overview
High-level description of hybrid approach.

## Architecture
- Layer 1: Rule-Based Extraction
- Layer 2: spaCy NER Extraction
- Layer 3: LLM Fallback
- Confidence Scoring

## Components
### RuleBasedExtractor
[Description, API, examples]

### SpacyNERExtractor
[Description, API, examples]

### HybridCVAnalyzerAdapter
[Description, API, examples]

## Configuration
[All settings with explanations]

## Performance
[Benchmarks from Phase 6]

## Migration from Legacy
[Link to migration guide]

## Troubleshooting
[Common issues + solutions]
```

### 2. Migration Guide (`docs/hybrid-cv-analyzer-migration-guide.md`)

**Contents**:
- Prerequisites (spaCy models, config)
- Step-by-step migration instructions
- A/B testing setup
- Rollback procedures
- Monitoring checklist

**Structure**:
```markdown
# Migration Guide: Legacy → Hybrid CV Analyzer

## Prerequisites
1. Install spaCy models
2. Update environment variables
3. Run database migrations (if any)

## Step-by-Step Migration

### Step 1: Enable Hybrid Adapter (10% traffic)
```bash
# .env
USE_HYBRID_CV_ANALYZER=true
```

### Step 2: Monitor Metrics (3 days)
- Latency p95 < 3s
- Error rate < 2%
- Cost reduction ≥ 70%

### Step 3: Increase Traffic (25% → 50% → 100%)
[Gradual rollout schedule]

### Step 4: Deprecate Legacy Adapter (after 2 weeks at 100%)
[Removal timeline]

## Rollback Procedure
1. Set USE_HYBRID_CV_ANALYZER=false
2. Verify legacy adapter working
3. Investigate issue

## Monitoring Checklist
- [ ] Latency dashboard
- [ ] Error rate alerts
- [ ] Cost tracking
- [ ] LLM fallback rate
```

### 3. Update Existing Docs

**Files to Update**:

1. **`docs/system-architecture.md`**:
   - Add section: "Hybrid CV Analyzer Architecture"
   - Update component diagram
   - Add extraction pipeline flow

2. **`docs/codebase-summary.md`**:
   - Add Phase 1-7 implementation files
   - Update file statistics
   - Add dependencies (spaCy)

3. **`README.md`**:
   - Add "Hybrid CV Analyzer" to features list
   - Update development setup (spaCy model installation)
   - Add performance benchmarks

4. **`CLAUDE.md`**:
   - Update "CV Analyzer" section
   - Add configuration examples
   - Add testing instructions

---

## Testing Strategy

### Documentation Tests (Validation)
1. **Completeness**: All components documented
2. **Accuracy**: Code examples tested and working
3. **Clarity**: Technical writer reviews for readability
4. **Up-to-date**: Cross-reference with actual code

### Migration Guide Tests
1. **Dry Run**: Follow guide on staging environment
2. **Rollback Test**: Verify rollback procedure works
3. **Monitoring**: Validate metrics tracking setup

---

## Success Criteria

- [ ] `docs/hybrid-cv-analyzer.md` created (complete)
- [ ] `docs/hybrid-cv-analyzer-migration-guide.md` created
- [ ] `docs/system-architecture.md` updated
- [ ] `docs/codebase-summary.md` updated
- [ ] `README.md` updated
- [ ] `CLAUDE.md` updated
- [ ] All code examples tested and working
- [ ] Technical writer review completed
- [ ] Stakeholder approval obtained

---

## Deliverable Examples

### Example: Configuration Section
```markdown
## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_HYBRID_CV_ANALYZER` | `false` | Enable hybrid analyzer |
| `HYBRID_CONFIDENCE_THRESHOLD` | `0.7` | LLM fallback trigger |
| `HYBRID_ENABLE_LLM_FALLBACK` | `true` | Allow LLM usage |

### Usage Example

```python
from src.infrastructure.config import Settings

settings = Settings(
    use_hybrid_cv_analyzer=True,
    hybrid_confidence_threshold=0.7
)
```
```

### Example: Troubleshooting Section
```markdown
## Troubleshooting

### Issue: spaCy model not found
**Error**: `OSError: Can't find model 'en_core_web_sm'`

**Solution**:
```bash
python -m spacy download en_core_web_sm
python -m spacy download vi_core_news_sm
```

### Issue: High LLM fallback rate (> 50%)
**Symptom**: Most CVs triggering LLM, cost not reduced

**Solution**:
1. Check confidence threshold (try 0.65 instead of 0.7)
2. Verify skill_patterns.json loaded correctly
3. Review NER accuracy on sample CVs
```

---

## Next Steps

After Phase 7:
1. Present complete implementation to stakeholders
2. Schedule production rollout (A/B test)
3. Begin gradual traffic shift (10% → 100%)

---

**Phase 7 Status**: Ready for Execution (after Phase 6)
**Est. Completion**: 2 days

---

## Phase 7 Completion Marks End of Migration

**Total Duration**: 22-29 days (Phases 1-7)
**Final Deliverables**:
- 7 new adapter files
- 50+ unit tests
- 15+ integration tests
- 5 documentation files
- Production-ready hybrid CV analyzer

**Production Rollout**: Ready after Phase 7 sign-off
