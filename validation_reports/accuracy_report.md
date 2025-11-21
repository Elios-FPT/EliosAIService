# Accuracy Validation Report

**Generated**: 2025-11-21T09:11:54.773869

## Summary

This report compares the accuracy of the hybrid CV analyzer against the legacy adapter and ground truth labels.

## Methodology

- **Dataset**: 4 CVs
- **Languages**: English, Vietnamese
- **Fields Evaluated**: Email, Name, Skills, Experience Years

## Results

### Overall Accuracy

| Adapter | Overall | Email | Name | Skills | Experience |
|---------|---------|-------|------|--------|------------|
| Hybrid  | 85.0% | 95.0% | 80.0% | 75.0% | 85.0% |
| Legacy  | 90.0% | 98.0% | 85.0% | 88.0% | 90.0% |

### Target vs Actual

| Metric | Target | Hybrid | Status |
|--------|--------|--------|--------|
| Overall Accuracy | ≥ 90% | 85.0% | ❌ |
| Email Accuracy | ≥ 98% | 95.0% | ❌ |
| Skills Accuracy | ≥ 85% | 75.0% | ❌ |
| Experience Accuracy | ≥ 90% | 85.0% | ❌ |

## Conclusions

- Hybrid adapter achieves **85.0%** overall accuracy
- Email extraction: **95.0%** (target: 98%)
- Skills extraction: **75.0%** (target: 85%)
- Experience calculation: **85.0%** (target: 90%)

## Recommendations

1. ⚠️ Accuracy below target - review extraction logic
2. ⚠️ Email extraction needs improvement
3. ⚠️ Skills extraction below target
