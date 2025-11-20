# Hybrid CV Parser Architecture Research Report

**Date**: 2025-11-20
**Research Scope**: Production-grade hybrid CV parsing combining rules, NLP, and LLM
**Key Sources**: ArXiv papers, GitHub open-source projects, production systems (Affinda, RChilli, Sovren)

---

## 1. Standard Production Architecture

### Three-Stage Pipeline (Academic + Industry Standard)

```
Stage 1: Layout-Aware Preprocessing
├─ Hybrid Content Extraction (Metadata + OCR)
├─ Layout Reconstruction (YOLO segmentation)
└─ Text Indexing (Sequential line numbers)

Stage 2: Parallelized Field Extraction
├─ Rule Engine (structured fields: email, phone, dates)
├─ NER Layer (spaCy: companies, skills, roles)
└─ LLM Extraction (experience descriptions, summaries)

Stage 3: Post-Processing & Validation
├─ Entity Alignment (Hungarian algorithm)
├─ Field-Specific Matching (dates, entities, descriptions)
├─ Hallucination Pruning
└─ Confidence Scoring
```

**Key Insight**: Modern systems don't choose ONE method—they parallelize complementary approaches, each handling fields where they excel.

---

## 2. Field-Level Routing Strategy

### Extraction Method by Field Type

| Field | Method | Accuracy | Rationale |
|-------|--------|----------|-----------|
| **Email, Phone** | Rules (Regex) | 98%+ | Deterministic patterns |
| **Dates, Locations** | Rules + NER | 95%+ | Format-based + context |
| **Company Names** | NER (spaCy) | 88-92% | Context-aware recognition |
| **Job Titles** | NER + LLM | 85-90% | Ambiguous, requires context |
| **Skills** | Rules + ML | 87-93% | Mix of exact & fuzzy matching |
| **Experience Duration** | Rules + NER | 90%+ | Calculated from dates |
| **Summaries, Descriptions** | LLM only | 92%+ | Requires semantic understanding |

**Decision Logic**: Rules → NER → LLM (fallback cascade)

---

## 3. Comparative Accuracy Analysis

### Baseline Performance (Industry Data)

- **Rule-based Only**: 60-70% (too many false negatives for complex fields)
- **NER Only (spaCy)**: 85-90% (struggles with ambiguous entities, limited context)
- **LLM Only**: 95%+ (expensive, slow, hallucination risk on structured data)
- **Hybrid (Rules + NER + LLM)**: 92-97% (balanced cost/accuracy)

### Real-World Benchmark
GitHub NLP-Resume-Parsing hybrid model: **87.62% precision, 96.91% recall**
Improvement: +17% precision over single methods

---

## 4. Integration Pattern: Ports & Adapters

### Port Interface Design (Clean Architecture)

```python
# Abstract extraction strategy
class ExtractorPort(ABC):
    @abstractmethod
    async def extract(self, pdf_text: str) -> ExtractionResult:
        """Returns field dict with confidence scores"""
        pass

class RuleBasedExtractor(ExtractorPort):
    """Email, phone, dates via regex/patterns"""

class NERExtractor(ExtractorPort):
    """spaCy-based named entity recognition"""

class LLMExtractor(ExtractorPort):
    """OpenAI/Claude for semantic extraction"""

# Hybrid orchestrator
class HybridCVAnalyzer:
    def __init__(self, rule_ex: RuleBasedExtractor,
                 ner_ex: NERExtractor,
                 llm_ex: LLMExtractor):
        self.extractors = [rule_ex, ner_ex, llm_ex]

    async def extract_field(self, text: str, field: str) -> ExtractionResult:
        # Route by field type or cascade through strategies
        for extractor in self._get_extractors_for_field(field):
            result = await extractor.extract(text)
            if result.confidence > THRESHOLD:
                return result
        return None
```

---

## 5. Testing Strategy for Hybrid Systems

### Layer-Level Testing

1. **Unit Tests**: Each extractor independently
   - Rule engine: regex pattern coverage
   - NER: spaCy model entity accuracy on fixture data
   - LLM: prompt engineering validation

2. **Integration Tests**: Extraction pipeline
   - Mock extractors to verify routing logic
   - Test fallback chain (rule → NER → LLM)
   - Verify confidence scoring

3. **End-to-End Tests**: Real resumes
   - Use open datasets (e.g., GitHubResume collection)
   - Compare outputs against human-annotated gold standard
   - Track accuracy per field type

### Test Example
```python
@pytest.mark.asyncio
async def test_email_field_rule_extractor():
    extractor = RuleBasedExtractor()
    text = "Contact: john.doe@example.com"
    result = await extractor.extract(text)
    assert result.email == "john.doe@example.com"
    assert result.confidence > 0.99  # Rules very confident

@pytest.mark.asyncio
async def test_company_field_ner_fallback():
    text = "Worked at Google as SWE"
    result = await hybrid_analyzer.extract_field(text, "companies")
    # Should use NER extractor, skip rules (no pattern match)
    assert result.value == "Google"
```

---

## 6. Production Cost/Performance Trade-offs

### Cost Model (API pricing as of 2025)

| Component | Cost | Latency | Use Case |
|-----------|------|---------|----------|
| Rules + spaCy | $0 | ~500ms | All structured fields |
| Add LLM (Claude 3.5 Haiku) | ~$0.001/resume | +2-3s | Summaries, ambiguous fields |
| Full LLM-only | ~$0.01/resume | +3-5s | Maximum accuracy, cost-insensitive |

**Recommendation**: Use hybrid for most fields; LLM only for descriptions/summaries.

---

## 7. Open-Source Reference Implementations

### Recommended GitHub Projects

1. **JennyTan5522/NLP-Resume-Parsing**
   - Hybrid architecture: rule-based + ML + spaCy
   - Demonstrates fallback strategy
   - Reference: 87.62% precision implementation

2. **OmkarPathak/pyresparser**
   - Production-grade spaCy + NLTK
   - Available as pip package
   - Good baseline for NER layer

3. **ArXiv 2510.09722 (Layout-Aware Parsing)**
   - Three-stage pipeline with LLM
   - Index-based pointer mechanism (reduces hallucinations)
   - YOLO-based layout reconstruction

---

## 8. Key Architecture Decisions

### Decision Tree: Which Extractor for Field X?

```
Is field structured (email, phone, date)?
  → YES: Use Rules (regex patterns) first
         Fallback: NER if complex format detected

Is field entity-based (company, person, location)?
  → YES: Use NER first (spaCy pre-trained)
         Fallback: LLM if confidence < 0.7

Is field semantic/descriptive (experience, summary)?
  → YES: Use LLM directly
         Cache results (expensive)
```

### Why NOT Pure LLM?
- **Cost**: 10-100x more expensive than hybrid
- **Hallucination**: Generates false data on structured fields
- **Latency**: 3-5s vs 500ms for rules + NER
- **Determinism**: Rules provide reproducible extraction

---

## 9. Integration Checklist for Elios Service

- [ ] Create `RuleBasedCVExtractor` (regex + patterns)
- [ ] Wrap `spaCy` as `NERCVExtractor` port
- [ ] Implement `LLMCVExtractor` with Claude API
- [ ] Build `HybridCVAnalyzer` orchestrator (routing logic)
- [ ] Add field-level confidence scoring
- [ ] Implement fallback chain + caching
- [ ] Unit test each layer independently
- [ ] Integration test routing logic with fixtures
- [ ] E2E test on 50+ public resumes
- [ ] Benchmark: latency + cost per resume

---

## Unresolved Questions

1. **Caching Strategy**: Should we cache LLM results per resume hash?
2. **Model Versioning**: How to handle spaCy model updates in production?
3. **Custom Skills Taxonomy**: Should we maintain proprietary skills list or use dynamic extraction?
4. **International Support**: Plan for non-English resumes (RChilli supports 40+ languages)?
