# Research: spaCy NER Patterns, Regex Techniques & Confidence Scoring for Hybrid CV Analyzer

**Date**: 2025-11-20
**Scope**: Rule-based CV field extraction, multilingual support, confidence scoring algorithms
**Sources**: spaCy docs, GitHub resume-parser, ArXiv (confidence tokens), regex standards

---

## 1. spaCy Matcher & PhraseMatcher for Skill Extraction

### Best Approach: Hybrid Matcher Strategy

**Matcher (Token-Based Rules)**:
- Define linguistic patterns for flexible skill extraction
- Supports quantifiers: `?` (optional), `*` (0+), `+` (1+)
- Example: Extract "years of experience" across variations
```python
pattern = [
  {"LOWER": {"IN": ["python", "java", "go", "rust"]}},
  {"IS_PUNCT": False, "OP": "*"}  # Optional modifiers
]
matcher.add("SKILL", [pattern])
```

**PhraseMatcher (Gazetteer-Based)**:
- Fast exact-match for known skill terminology
- Use case: Pre-compiled skill dictionaries (500+ skills)
- More efficient than token patterns for large lists
```python
terms = [nlp.make_doc(skill) for skill in SKILLS_LIST]
phrase_matcher.add("SKILL", terms, on_match=callback)
```

**Key Rules**:
- Use `LOWER` attribute for case-insensitive matching
- Combine Matcher + PhraseMatcher in same pipeline
- **Note**: Matcher/PhraseMatcher don't align with `doc.ents`, so wrap with `EntityRuler` for proper entity storage
- Support multi-language: Load language-specific models (`en_core_web_md`, `xx_sent_ud_sm`)

---

## 2. Regex Patterns: Multilingual Email, Phone, Date

### Email (Multilingual)
```regex
^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
```
Works across: English, Vietnamese, German, French (characters + domains)

### Phone Numbers (International)
```regex
\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b
```
Handles: `+1-202-555-0123`, `(202) 555 0123`, `+84-9-xxxx-xxxx` (Vietnam)

### Date Extraction (Multiple Formats)
```regex
(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}
```
Matches: "January 2020", "2020-01-15", "01/15/2020", "Present"

### Section Headers (CV Structure)
```regex
^(EXPERIENCE|EDUCATION|SKILLS|SUMMARY|CONTACT|CERTIFICATIONS?)[:]*$
```
Case-insensitive flag: `re.IGNORECASE`

---

## 3. Confidence Scoring: Algorithms & Thresholds

### Confidence Calculation Methods (Ranked by Accuracy)

| Method | Accuracy | Implementation |
|--------|----------|-----------------|
| **Token Logprobs** | Highest | Use LLM's generation probabilities per token |
| **Self-Reflection Tokens** | High | Train LLM with confidence tokens (ArXiv 2410.13284) |
| **Explicit Prompting** | Low | Ask LLM "rate your confidence" (unreliable) |

### Field-Level Confidence Scoring
```python
def calculate_field_confidence(field_type: str, match_quality: float) -> float:
    """
    Weights:
    - Regex match (exact): 0.9
    - Matcher pattern match (fuzzy): 0.7
    - LLM fallback: 0.5 (single output)
    """
    if field_type in ["email", "phone"]:  # Structured
        return 0.95 if regex_match else 0.3
    elif field_type == "skill":  # Unstructured
        return 0.8 * (phrase_matcher_score) + 0.2 * (context_relevance)
    else:
        return 0.5  # LLM fallback default
```

### Aggregated Confidence (All Fields)
```python
confidence = sum(field_scores) / len(field_scores)
# Weighted average if fields have priorities
```

### LLM Fallback Triggers
**Use LLM when**:
- Regex + Matcher confidence < **0.65** (tunable)
- Missing critical fields: `name`, `email`, `phone`, `summary`
- Section parsing fails (malformed CV structure)

**LLM Bypass** (Rule-based only):
- Confidence ≥ **0.85** for name/email/phone
- Confidence ≥ **0.80** for education/experience

---

## 4. Error Handling & Graceful Degradation

### Missing Critical Fields Strategy
```python
CRITICAL_FIELDS = {"name", "email", "phone"}
OPTIONAL_FIELDS = {"summary", "certifications"}

if len(extracted & CRITICAL_FIELDS) < 2:
    # Trigger full LLM fallback
    use_llm_parsing = True
else:
    # Hybrid: rules + selective LLM
    use_llm_parsing = False
```

### Confidence-Based Routing
```
confidence ≥ 0.85  → Accept (rule-based)
0.65 ≤ confidence < 0.85  → LLM review + rank
confidence < 0.65  → Full LLM extraction + manual flag
```

---

## 5. Implementation Architecture

### Pipeline Order (Recommended)
1. **Text preprocessing**: Normalize whitespace, OCR cleanup
2. **Regex extraction**: Email, phone, dates (fast, high-confidence)
3. **spaCy Matcher**: Skills, education keywords (medium confidence)
4. **PhraseMatcher**: Skill gazetteer lookup (fast, exact-match)
5. **Confidence aggregation**: Compute per-field + overall scores
6. **LLM fallback**: Fill gaps if confidence < threshold

### Multilingual Support
- spaCy: Use language-specific models (`en_`, `vi_`, `de_`, etc.)
- Regex: Unicode-aware (`\p{L}` in Python 3.x via `regex` lib)
- Fallback: Always route non-Latin scripts to LLM

---

## 6. Industry Benchmarks & Sources

### Confidence Thresholds (Best Practices)
- **Structured fields** (email, phone): 0.8+ threshold
- **Unstructured fields** (skills, summary): 0.65-0.75 threshold
- **Overall CV**: Accept if avg confidence ≥ 0.75

### Papers & References
- ArXiv 2410.13284: "Learning to Route LLMs with Confidence Tokens" (Self-REF method)
- spaCy Rule-Based Matching docs: https://spacy.io/usage/rule-based-matching
- GitHub: arunppsg/resume-parser (regex + spaCy reference implementation)

### Known Limitations
- Regex confidence varies by CV format (structured vs. unstructured)
- PhraseMatcher requires pre-built skill dictionaries (maintenance burden)
- LLM fallback cost: ~100-500ms per CV (budget accordingly)

---

## 7. Unresolved Questions

1. **Skill taxonomy**: How many skills to maintain in PhraseMatcher? (1K, 5K, 10K+?)
2. **Vietnamese CV parsing**: Are regex patterns sufficient, or LLM-first for non-English?
3. **Threshold calibration**: Recommend A/B testing thresholds on production CVs
4. **Field priority weights**: Which fields most impact hiring decision? (name/skills critical?)

