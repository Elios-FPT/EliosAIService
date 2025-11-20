# Phase 6: Testing & Validation

**Phase ID**: 06
**Duration**: 3-4 days
**Risk Level**: Medium
**Dependencies**: Phase 1-5 (Complete implementation)

---

## Context

Comprehensive testing + validation of hybrid CV analyzer. Compare against legacy adapter on real CVs. Measure: accuracy, latency, cost savings. Human validation of 50+ CVs (25 English, 25 Vietnamese).

---

## Testing Strategy

### 1. Accuracy Validation (2 days)

**Dataset**: 50 real CVs (25 English, 25 Vietnamese)
- Source: Public resume datasets + team-collected samples
- Annotation: Human-labeled gold standard (name, email, skills, experience)

**Metrics**:
- Field-level accuracy: Email (98%), Skills (85%), Experience (90%)
- Overall accuracy: ≥ 90% match with human labels
- F1 score per field type

**Test**: `tests/validation/test_accuracy_comparison.py`
```python
async def test_accuracy_on_gold_standard_dataset():
    """Compare hybrid vs legacy vs human labels."""
    dataset = load_gold_standard_cvs()  # 50 CVs

    for cv in dataset:
        hybrid_result = await hybrid_adapter.analyze_cv(cv.path, cv.candidate_id)
        legacy_result = await legacy_adapter.analyze_cv(cv.path, cv.candidate_id)

        # Compare against human labels
        hybrid_accuracy = calculate_accuracy(hybrid_result, cv.labels)
        legacy_accuracy = calculate_accuracy(legacy_result, cv.labels)

        assert hybrid_accuracy >= 0.90
        # Log comparison: hybrid vs legacy
```

### 2. Performance Benchmarks (1 day)

**Metrics**:
- Latency: p50, p95, p99 (target: p95 < 3s)
- LLM fallback rate: % CVs triggering LLM (target: < 30%)
- Cost per CV: Avg LLM API cost (target: < $0.003)

**Test**: `tests/performance/test_latency_benchmark.py`
```python
@pytest.mark.benchmark
async def test_hybrid_adapter_latency(benchmark):
    """Benchmark latency distribution."""
    cvs = load_sample_cvs(count=100)

    def run_analysis():
        return asyncio.run(hybrid_adapter.analyze_cv(cvs[0].path, cvs[0].id))

    result = benchmark(run_analysis)

    assert benchmark.stats.mean < 3.0  # 3s avg
    assert benchmark.stats.percentiles["95"] < 3.5  # p95 < 3.5s
```

### 3. Cost Analysis (1 day)

**Comparison**:
| Adapter | LLM Calls/CV | Avg Tokens | Cost/CV |
|---------|--------------|------------|---------|
| Legacy | 3 | 1000 | $0.010 |
| Hybrid | 0.3 (30% fallback) | 300 | $0.002 |
| **Savings** | **-90%** | **-70%** | **-80%** |

**Test**: `tests/cost/test_cost_comparison.py`
```python
async def test_cost_savings_vs_legacy():
    """Measure cost savings over 100 CVs."""
    cvs = load_sample_cvs(count=100)

    # Track LLM calls
    hybrid_llm_calls = 0
    legacy_llm_calls = 0

    for cv in cvs:
        with mock_llm_call_tracker():
            await hybrid_adapter.analyze_cv(cv.path, cv.id)
            hybrid_llm_calls += get_llm_call_count()

        with mock_llm_call_tracker():
            await legacy_adapter.analyze_cv(cv.path, cv.id)
            legacy_llm_calls += get_llm_call_count()

    # Calculate savings
    savings_pct = (legacy_llm_calls - hybrid_llm_calls) / legacy_llm_calls
    assert savings_pct >= 0.70  # At least 70% reduction
```

---

## Validation Checklist

### Functional Validation
- [ ] All unit tests passing (50+ tests across Phase 1-5)
- [ ] All integration tests passing (15+ tests)
- [ ] Accuracy ≥ 90% on gold standard dataset
- [ ] No regressions: Same CVAnalysis model structure
- [ ] Handles edge cases: empty CVs, malformed PDFs, missing sections

### Performance Validation
- [ ] Latency p95 < 3s (without LLM)
- [ ] Latency p99 < 5s (with LLM fallback)
- [ ] LLM fallback rate 20-30% (calibrated threshold)
- [ ] Cost per CV < $0.003 avg

### Quality Validation (Human Review)
- [ ] 20 summaries reviewed by QA team → 90%+ quality approval
- [ ] 20 skill extractions reviewed → 85%+ accuracy
- [ ] 20 interview topics reviewed → 80%+ relevance

---

## Success Criteria

- [ ] 50 CVs processed by both adapters (hybrid + legacy)
- [ ] Accuracy report generated (per-field metrics)
- [ ] Performance report: latency, cost, fallback rate
- [ ] Cost savings validated: ≥ 70% reduction
- [ ] No critical bugs found
- [ ] Human validation: 90%+ approval on quality

---

## Deliverables

1. **Accuracy Report** (`validation_reports/accuracy_report.md`):
   - Per-field accuracy (email, phone, skills, experience)
   - F1 scores
   - Confusion matrix

2. **Performance Report** (`validation_reports/performance_report.md`):
   - Latency distribution (p50, p95, p99)
   - LLM fallback rate histogram
   - Cost comparison table

3. **Test Coverage Report** (`validation_reports/coverage_report.html`):
   - Line coverage: ≥ 80%
   - Branch coverage: ≥ 75%

---

## Next Steps

After Phase 6:
1. Proceed to Phase 7: Documentation & Migration Guide
2. Present validation results to stakeholders
3. Approve production rollout plan

---

**Phase 6 Status**: Ready for Execution (after Phase 1-5)
**Est. Completion**: 3-4 days
