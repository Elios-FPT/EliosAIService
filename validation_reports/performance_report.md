# Performance Validation Report

**Generated**: 2025-11-21T09:11:54.774870

## Summary

This report analyzes the performance characteristics of the hybrid CV analyzer, including latency, LLM fallback rate, and cost metrics.

## Latency Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Mean Latency | < 3.0s | 0.040s | ✅ |
| Median (p50) | < 2.5s | 0.024s | ✅ |
| p95 Latency | < 3.5s | 0.105s | ✅ |
| p99 Latency | < 5.0s | 0.105s | ✅ |

## LLM Fallback Rate

- **Target**: < 30%
- **Actual**: 50.0%
- **Status**: ❌

## Cost Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Cost per CV | < $0.003 | $0.0003 | ✅ |
| LLM Calls per CV | < 0.3 | 0.50 | ❌ |

## Latency Distribution

- **Min**: 0.020s
- **Max**: 0.110s
- **Std Dev**: 0.035s

## Conclusions

- Average latency: **0.040s** (target: < 3.0s)
- p95 latency: **0.105s** (target: < 3.5s)
- LLM fallback rate: **50.0%** (target: < 30%)
- Cost per CV: **$0.0003** (target: < $0.003)

## Recommendations

1. ✅ Latency targets met
2. ⚠️ Consider adjusting confidence threshold
3. ✅ Cost targets met
