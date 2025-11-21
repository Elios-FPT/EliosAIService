# Hybrid CV Analyzer - Validation Summary

**Generated**: 2025-11-21T09:11:54.774870

## Executive Summary

The hybrid CV analyzer has been validated against accuracy, performance, and cost targets. Results indicate ⚠️ NEEDS IMPROVEMENT.

## Key Metrics

| Category | Metric | Target | Actual | Status |
|----------|--------|--------|--------|--------|
| **Accuracy** | Overall | ≥ 90% | 85.0% | ❌ |
| **Performance** | Mean Latency | < 3.0s | 0.040s | ✅ |
| **Cost** | Cost per CV | < $0.003 | $0.0003 | ✅ |
| **Efficiency** | LLM Fallback Rate | < 30% | 50.0% | ❌ |

## Detailed Results

### Accuracy Validation
- Overall: 85.0%
- Email: 95.0%
- Skills: 75.0%
- Experience: 85.0%

### Performance Validation
- Mean Latency: 0.040s
- p95 Latency: 0.105s
- p99 Latency: 0.105s

### Cost Validation
- Cost per CV: $0.0003
- LLM Calls per CV: 0.50
- Estimated Savings vs Legacy: 75.0%

## Recommendations

1. ⚠️ Improve extraction accuracy before production
2. ✅ Performance meets requirements
3. ✅ Cost targets achieved
4. ⚠️ Consider adjusting confidence threshold

## Next Steps

1. Review detailed accuracy and performance reports
2. Address identified issues before proceeding
3. Prepare production rollout plan
