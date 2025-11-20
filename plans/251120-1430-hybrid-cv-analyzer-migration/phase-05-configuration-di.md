# Phase 5: Configuration & DI Updates

**Phase ID**: 05
**Duration**: 2 days
**Risk Level**: Low
**Dependencies**: Phase 1-4 (All extractors ready)

---

## Context

Add configuration settings for hybrid CV analyzer, update DI container to support both legacy + hybrid adapters via feature flag. Enable A/B testing and gradual rollout.

---

## Implementation

### 1. Settings Updates (`settings.py`)

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Hybrid CV Analyzer Configuration
    use_hybrid_cv_analyzer: bool = False  # Feature flag (default: legacy)
    hybrid_confidence_threshold: float = 0.7  # LLM fallback trigger
    hybrid_enable_llm_fallback: bool = True  # Allow LLM when confidence low
    hybrid_skill_patterns_path: str = "./src/adapters/cv_processing/skill_patterns.json"

    # spaCy Model Configuration
    spacy_model_en: str = "en_core_web_sm"  # English NER model
    spacy_model_vi: str = "vi_core_news_sm"  # Vietnamese NER model
    spacy_disable_components: list[str] = ["parser", "lemmatizer"]  # Optimize speed
```

### 2. DI Container Updates (`container.py`)

```python
def cv_analyzer_port(self) -> CVAnalyzerPort:
    """Get CV analyzer port implementation.

    Returns:
        Hybrid or legacy adapter based on settings
    """
    if self.settings.use_mock_cv_analyzer:
        return MockCVAnalyzerAdapter()
    elif self.settings.use_hybrid_cv_analyzer:
        # NEW: Hybrid adapter
        from ...adapters.cv_processing.hybrid_cv_analyzer import HybridCVAnalyzerAdapter
        return HybridCVAnalyzerAdapter(
            confidence_threshold=self.settings.hybrid_confidence_threshold,
            use_llm_fallback=self.settings.hybrid_enable_llm_fallback
        )
    else:
        # LEGACY: CVProcessingAdapter (existing)
        return CVProcessingAdapter()
```

### 3. Environment Variables (`.env.example`)

```bash
# Hybrid CV Analyzer
USE_HYBRID_CV_ANALYZER=false  # Enable hybrid analyzer
HYBRID_CONFIDENCE_THRESHOLD=0.7  # LLM fallback trigger
HYBRID_ENABLE_LLM_FALLBACK=true  # Allow LLM usage
SPACY_MODEL_EN=en_core_web_sm
SPACY_MODEL_VI=vi_core_news_sm
```

---

## Testing Strategy

### Unit Tests (5 tests)

1. `test_di_container_legacy_adapter` - use_hybrid=false → CVProcessingAdapter
2. `test_di_container_hybrid_adapter` - use_hybrid=true → HybridCVAnalyzerAdapter
3. `test_di_container_mock_adapter` - use_mock=true → MockCVAnalyzerAdapter
4. `test_settings_default_values` - Verify defaults (hybrid=false)
5. `test_settings_load_from_env` - Load from .env file

### Integration Tests (2 tests)

1. **test_switch_adapters_runtime**:
   - Toggle feature flag
   - Verify correct adapter injected
   - Process same CV with both → compare results

2. **test_confidence_threshold_configuration**:
   - Set threshold=0.6 vs 0.8
   - Process low-confidence CV
   - Verify LLM fallback behavior changes

---

## Success Criteria

- [ ] 3 new settings added to Settings class
- [ ] DI container supports 3 adapters (mock, legacy, hybrid)
- [ ] `.env.example` updated with hybrid settings
- [ ] 5 unit tests passing
- [ ] 2 integration tests passing
- [ ] Default: `use_hybrid_cv_analyzer=false` (safe rollback)
- [ ] Documentation updated with new config options

---

## Rollback Plan

Rollback = set `USE_HYBRID_CV_ANALYZER=false` in environment. No code changes needed.

---

## Next Steps

After Phase 5:
1. Proceed to Phase 6: Testing & Validation
2. Prepare A/B test plan for production

---

**Phase 5 Status**: Ready for Implementation
**Est. Completion**: 2 days
