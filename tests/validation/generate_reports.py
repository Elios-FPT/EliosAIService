"""Generate validation reports from test results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_accuracy_report(
    results: dict[str, Any],
    output_path: Path | str = "validation_reports/accuracy_report.md",
) -> None:
    """Generate accuracy validation report.

    Args:
        results: Dictionary with accuracy results
        output_path: Path to save report
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# Accuracy Validation Report

**Generated**: {datetime.now().isoformat()}

## Summary

This report validates the accuracy of the hybrid CV analyzer against ground truth labels.

## Methodology

- **Dataset**: {results.get('dataset_size', 0)} CVs
- **Languages**: English, Vietnamese
- **Fields Evaluated**: Email, Name, Skills, Experience Years

## Results

### Accuracy Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Overall Accuracy | ≥ 90% | {results.get('hybrid', {}).get('overall', 0.0):.1%} | {'✅' if results.get('hybrid', {}).get('overall', 0.0) >= 0.90 else '❌'} |
| Email Accuracy | ≥ 98% | {results.get('hybrid', {}).get('email', 0.0):.1%} | {'✅' if results.get('hybrid', {}).get('email', 0.0) >= 0.98 else '❌'} |
| Name Accuracy | ≥ 85% | {results.get('hybrid', {}).get('name', 0.0):.1%} | {'✅' if results.get('hybrid', {}).get('name', 0.0) >= 0.85 else '❌'} |
| Skills Accuracy | ≥ 85% | {results.get('hybrid', {}).get('skills', 0.0):.1%} | {'✅' if results.get('hybrid', {}).get('skills', 0.0) >= 0.85 else '❌'} |
| Experience Accuracy | ≥ 90% | {results.get('hybrid', {}).get('experience', 0.0):.1%} | {'✅' if results.get('hybrid', {}).get('experience', 0.0) >= 0.90 else '❌'} |

## Conclusions

- Overall accuracy: **{results.get('hybrid', {}).get('overall', 0.0):.1%}** (target: ≥ 90%)
- Email extraction: **{results.get('hybrid', {}).get('email', 0.0):.1%}** (target: ≥ 98%)
- Skills extraction: **{results.get('hybrid', {}).get('skills', 0.0):.1%}** (target: ≥ 85%)
- Experience calculation: **{results.get('hybrid', {}).get('experience', 0.0):.1%}** (target: ≥ 90%)

## Recommendations

1. {'✅ Accuracy targets met' if results.get('hybrid', {}).get('overall', 0.0) >= 0.90 else '⚠️ Accuracy below target - review extraction logic'}
2. {'✅ Email extraction excellent' if results.get('hybrid', {}).get('email', 0.0) >= 0.98 else '⚠️ Email extraction needs improvement'}
3. {'✅ Skills extraction acceptable' if results.get('hybrid', {}).get('skills', 0.0) >= 0.85 else '⚠️ Skills extraction below target'}
"""

    output_path.write_text(report, encoding="utf-8")
    print(f"Accuracy report saved to {output_path}")


def generate_performance_report(
    results: dict[str, Any],
    output_path: Path | str = "validation_reports/performance_report.md",
) -> None:
    """Generate performance validation report.

    Args:
        results: Dictionary with performance results
        output_path: Path to save report
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    latencies = results.get("latencies", {})
    fallback_rate = results.get("fallback_rate", 0.0)

    report = f"""# Performance Validation Report

**Generated**: {datetime.now().isoformat()}

## Summary

This report analyzes the performance characteristics of the hybrid CV analyzer, including latency, LLM fallback rate, and cost metrics.

## Latency Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Mean Latency | < 3.0s | {latencies.get('mean', 0.0):.3f}s | {'✅' if latencies.get('mean', 0.0) < 3.0 else '❌'} |
| Median (p50) | < 2.5s | {latencies.get('median', 0.0):.3f}s | {'✅' if latencies.get('median', 0.0) < 2.5 else '❌'} |
| p95 Latency | < 3.5s | {latencies.get('p95', 0.0):.3f}s | {'✅' if latencies.get('p95', 0.0) < 3.5 else '❌'} |
| p99 Latency | < 5.0s | {latencies.get('p99', 0.0):.3f}s | {'✅' if latencies.get('p99', 0.0) < 5.0 else '❌'} |

## LLM Fallback Rate

- **Target**: < 30%
- **Actual**: {fallback_rate:.1%}
- **Status**: {'✅' if fallback_rate < 0.30 else '❌'}

## Cost Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Cost per CV | < $0.003 | ${results.get('cost_per_cv', 0.0):.4f} | {'✅' if results.get('cost_per_cv', 0.0) < 0.003 else '❌'} |
| LLM Calls per CV | < 0.3 | {results.get('llm_calls_per_cv', 0.0):.2f} | {'✅' if results.get('llm_calls_per_cv', 0.0) < 0.3 else '❌'} |

## Latency Distribution

- **Min**: {latencies.get('min', 0.0):.3f}s
- **Max**: {latencies.get('max', 0.0):.3f}s
- **Std Dev**: {latencies.get('std', 0.0):.3f}s

## Conclusions

- Average latency: **{latencies.get('mean', 0.0):.3f}s** (target: < 3.0s)
- p95 latency: **{latencies.get('p95', 0.0):.3f}s** (target: < 3.5s)
- LLM fallback rate: **{fallback_rate:.1%}** (target: < 30%)
- Cost per CV: **${results.get('cost_per_cv', 0.0):.4f}** (target: < $0.003)

## Recommendations

1. {'✅ Latency targets met' if latencies.get('mean', 0.0) < 3.0 else '⚠️ Latency optimization needed'}
2. {'✅ Fallback rate acceptable' if fallback_rate < 0.30 else '⚠️ Consider adjusting confidence threshold'}
3. {'✅ Cost targets met' if results.get('cost_per_cv', 0.0) < 0.003 else '⚠️ Cost optimization needed'}
"""

    output_path.write_text(report, encoding="utf-8")
    print(f"Performance report saved to {output_path}")


def generate_summary_report(
    accuracy_results: dict[str, Any],
    performance_results: dict[str, Any],
    output_path: Path | str = "validation_reports/summary_report.md",
) -> None:
    """Generate summary validation report.

    Args:
        accuracy_results: Accuracy test results
        performance_results: Performance test results
        output_path: Path to save report
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    hybrid_overall = accuracy_results.get("hybrid", {}).get("overall", 0.0)
    latency_mean = performance_results.get("latencies", {}).get("mean", 0.0)
    cost_per_cv = performance_results.get("cost_per_cv", 0.0)
    fallback_rate = performance_results.get("fallback_rate", 0.0)

    report = f"""# Hybrid CV Analyzer - Validation Summary

**Generated**: {datetime.now().isoformat()}

## Executive Summary

The hybrid CV analyzer has been validated against accuracy, performance, and cost targets. Results indicate {'✅ READY FOR PRODUCTION' if hybrid_overall >= 0.90 and latency_mean < 3.0 and cost_per_cv < 0.003 else '⚠️ NEEDS IMPROVEMENT'}.

## Key Metrics

| Category | Metric | Target | Actual | Status |
|----------|--------|--------|--------|--------|
| **Accuracy** | Overall | ≥ 90% | {hybrid_overall:.1%} | {'✅' if hybrid_overall >= 0.90 else '❌'} |
| **Performance** | Mean Latency | < 3.0s | {latency_mean:.3f}s | {'✅' if latency_mean < 3.0 else '❌'} |
| **Cost** | Cost per CV | < $0.003 | ${cost_per_cv:.4f} | {'✅' if cost_per_cv < 0.003 else '❌'} |
| **Efficiency** | LLM Fallback Rate | < 30% | {fallback_rate:.1%} | {'✅' if fallback_rate < 0.30 else '❌'} |

## Detailed Results

### Accuracy Validation
- Overall: {hybrid_overall:.1%}
- Email: {accuracy_results.get('hybrid', {}).get('email', 0.0):.1%}
- Skills: {accuracy_results.get('hybrid', {}).get('skills', 0.0):.1%}
- Experience: {accuracy_results.get('hybrid', {}).get('experience', 0.0):.1%}

### Performance Validation
- Mean Latency: {latency_mean:.3f}s
- p95 Latency: {performance_results.get('latencies', {}).get('p95', 0.0):.3f}s
- p99 Latency: {performance_results.get('latencies', {}).get('p99', 0.0):.3f}s

### Cost Validation
- Cost per CV: ${cost_per_cv:.4f}
- LLM Calls per CV: {performance_results.get('llm_calls_per_cv', 0.0):.2f}

## Recommendations

1. {'✅ Accuracy meets production standards' if hybrid_overall >= 0.90 else '⚠️ Improve extraction accuracy before production'}
2. {'✅ Performance meets requirements' if latency_mean < 3.0 else '⚠️ Optimize latency before production'}
3. {'✅ Cost targets achieved' if cost_per_cv < 0.003 else '⚠️ Review cost optimization'}
4. {'✅ Fallback rate acceptable' if fallback_rate < 0.30 else '⚠️ Consider adjusting confidence threshold'}

## Next Steps

1. Review detailed accuracy and performance reports
2. {'Proceed to Phase 7: Documentation & Migration Guide' if hybrid_overall >= 0.90 and latency_mean < 3.0 else 'Address identified issues before proceeding'}
3. Prepare production rollout plan
"""

    output_path.write_text(report, encoding="utf-8")
    print(f"Summary report saved to {output_path}")

