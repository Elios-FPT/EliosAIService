# Phase 2: spaCy NER Extractor Integration

**Phase ID**: 02
**Duration**: 4-5 days
**Risk Level**: Medium
**Dependencies**: Phase 1 (ConfidenceScorer)

---

## Context

Implement spaCy-based Named Entity Recognition (NER) layer for extracting unstructured entities: skills, companies, job titles, locations, education. Uses pre-trained models (`en_core_web_sm`, `vi_core_news_sm`) + custom PhraseMatcher for skill gazetteers.

**Why spaCy NER**: Handles ambiguous entities (companies, skills) better than regex, but cheaper than LLM. Achieves 88-92% accuracy at zero API cost.

---

## Overview

Create three components:
1. **SpacyNERExtractor**: Entity extraction using spaCy pipelines
2. **SkillMatcher**: Custom PhraseMatcher for skill terminology
3. **Enhanced skill_patterns.json**: Add categories + proficiency mapping

**Key Challenge**: Vietnamese CV support requires `vi_core_news_sm` model with lower accuracy than English (~75% vs. 90%).

---

## Requirements

### Functional Requirements
- **FR-1**: Extract person names (PERSON entity)
- **FR-2**: Extract company names (ORG entity)
- **FR-3**: Extract locations (GPE, LOC entities)
- **FR-4**: Extract dates (DATE entity) - supplement Phase 1 regex
- **FR-5**: Extract skills using PhraseMatcher (500+ skill terms)
- **FR-6**: Categorize skills: Programming Languages, Frameworks, Databases, Tools, Soft Skills
- **FR-7**: Calculate NER-specific confidence scores (entity score + context)
- **FR-8**: Support English + Vietnamese languages

### Non-Functional Requirements
- **NFR-1**: Model loading time < 500ms (singleton pattern)
- **NFR-2**: Extraction time < 300ms per CV
- **NFR-3**: Skill matcher hit rate ≥ 60% (on 500-skill gazetteer)
- **NFR-4**: Memory footprint < 500MB (both models loaded)
- **NFR-5**: Unit test coverage ≥ 85%

---

## Architecture

### Class Diagram
```
┌──────────────────────────────────┐
│   SpacyNERExtractor              │
├──────────────────────────────────┤
│ - _nlp_en: spacy.Language (lazy) │
│ - _nlp_vi: spacy.Language (lazy) │
│ - skill_matcher: SkillMatcher    │
│ - confidence_scorer: ConfidenceScorer │
├──────────────────────────────────┤
│ + extract(text, lang) → NERResult│
│ - _detect_language(text) → str   │
│ - _extract_entities(doc) → dict  │
│ - _extract_skills(doc) → list    │
│ - _calculate_experience() → float│
└──────────────────────────────────┘
           ↓ uses
┌──────────────────────────────────┐
│   SkillMatcher                   │
├──────────────────────────────────┤
│ - phrase_matcher: PhraseMatcher  │
│ - skill_patterns: dict           │
├──────────────────────────────────┤
│ + match_skills(doc) → list[Skill]│
│ + load_patterns() → dict         │
│ - _categorize_skill() → str      │
└──────────────────────────────────┘
           ↓ reads
┌──────────────────────────────────┐
│   skill_patterns.json (ENHANCED) │
├──────────────────────────────────┤
│ {                                │
│   "programming_languages": [...],│
│   "frameworks": [...],           │
│   "databases": [...],            │
│   "tools": [...],                │
│   "soft_skills": [...]           │
│ }                                │
└──────────────────────────────────┘
```

### Data Flow
```
CV Text + Language → SpacyNERExtractor.extract()
                      ↓
                 spaCy NLP Pipeline
                      ↓ (parallel)
       ┌──────────────┴──────────────┐
       ↓                              ↓
  Entity Extraction            Skill Matching
  (PERSON, ORG, DATE, LOC)     (PhraseMatcher)
       ↓                              ↓
  {                            [ExtractedSkill(
    "name": "John Doe",          skill="Python",
    "companies": ["Google"],     category="programming_languages",
    "locations": ["NY"],         confidence=0.85
    "dates": ["2020-01"]       ), ...]
  }                                   ↓
       └──────────────┬───────────────┘
                      ↓
            ConfidenceScorer (Phase 1)
                      ↓
            NERResult {
              entities: dict,
              skills: list[ExtractedSkill],
              confidence: 0.88
            }
```

---

## Implementation Details

### File Structure
```
src/adapters/cv_processing/
├── spacy_ner_extractor.py        # NEW - spaCy NER engine
├── skill_matcher.py              # NEW - Skill PhraseMatcher
├── skill_patterns.json           # ENHANCED - Add categories
├── rule_based_extractor.py       # EXISTING (Phase 1)
└── confidence_scorer.py          # EXISTING (Phase 1)
```

### 1. SpacyNERExtractor (`spacy_ner_extractor.py`)

```python
import spacy
from typing import Dict, List, Any
from functools import lru_cache
from .confidence_scorer import ConfidenceScorer
from .skill_matcher import SkillMatcher
from ...domain.models.cv_analysis import ExtractedSkill

class SpacyNERExtractor:
    """Extract entities from CV text using spaCy NER.

    Supports English (en_core_web_sm) and Vietnamese (vi_core_news_sm) models.
    Uses PhraseMatcher for skill extraction (gazetteer-based).
    """

    def __init__(self):
        """Initialize extractor with lazy model loading."""
        self._nlp_en = None
        self._nlp_vi = None
        self.skill_matcher = SkillMatcher()
        self.confidence_scorer = ConfidenceScorer()

    @property
    def nlp_en(self) -> spacy.Language:
        """Lazy load English model (singleton)."""
        if self._nlp_en is None:
            try:
                self._nlp_en = spacy.load("en_core_web_sm")
            except OSError:
                raise RuntimeError(
                    "English model not found. Install: python -m spacy download en_core_web_sm"
                )
        return self._nlp_en

    @property
    def nlp_vi(self) -> spacy.Language:
        """Lazy load Vietnamese model (singleton)."""
        if self._nlp_vi is None:
            try:
                self._nlp_vi = spacy.load("vi_core_news_sm")
            except OSError:
                raise RuntimeError(
                    "Vietnamese model not found. Install: python -m spacy download vi_core_news_sm"
                )
        return self._nlp_vi

    def extract(self, cv_text: str, language: str = "auto") -> Dict[str, Any]:
        """Extract entities and skills from CV text.

        Args:
            cv_text: Full CV text content
            language: "en", "vi", or "auto" (auto-detect)

        Returns:
            {
                "name": str | None,
                "companies": list[str],
                "locations": list[str],
                "dates": list[str],  # Supplements Phase 1 regex
                "skills": list[ExtractedSkill],
                "experience_years": float | None,
                "confidence": dict[str, float]
            }
        """
        # Detect language if auto
        if language == "auto":
            language = self._detect_language(cv_text)

        # Load appropriate model
        nlp = self.nlp_en if language == "en" else self.nlp_vi

        # Process text
        doc = nlp(cv_text)

        # Extract entities
        entities = self._extract_entities(doc)

        # Extract skills (PhraseMatcher)
        skills = self._extract_skills(doc)

        # Calculate experience from dates
        experience_years = self._calculate_experience(entities["dates"])

        # Calculate confidence scores
        confidence_scores = {
            "name": self.confidence_scorer.score_field("name", [entities["name"]], bool(entities["name"])),
            "companies": self.confidence_scorer.score_field("companies", entities["companies"], True),
            "locations": self.confidence_scorer.score_field("locations", entities["locations"], True),
            "skills": self.confidence_scorer.score_field("skills", skills, True),
        }

        # Aggregate confidence
        overall_confidence = self.confidence_scorer.aggregate_confidence(confidence_scores)

        return {
            "name": entities["name"],
            "companies": entities["companies"],
            "locations": entities["locations"],
            "dates": entities["dates"],
            "skills": skills,
            "experience_years": experience_years,
            "confidence": {
                "fields": confidence_scores,
                "overall": overall_confidence,
            }
        }

    def _detect_language(self, text: str) -> str:
        """Auto-detect CV language (en or vi).

        Heuristic: Check for Vietnamese characters (Ă, Ơ, Ư, etc.)
        """
        vietnamese_chars = "ăâđêôơưấầẩẫậắằẳẵặếềểễệốồổỗộớờởỡợứừửữự"
        vietnamese_count = sum(1 for char in text.lower() if char in vietnamese_chars)

        # Threshold: > 10 Vietnamese chars → Vietnamese
        return "vi" if vietnamese_count > 10 else "en"

    def _extract_entities(self, doc: spacy.tokens.Doc) -> Dict[str, Any]:
        """Extract named entities from spaCy doc.

        Entity mapping:
        - PERSON → name (first occurrence)
        - ORG → companies
        - GPE, LOC → locations
        - DATE → dates
        """
        name = None
        companies = []
        locations = []
        dates = []

        for ent in doc.ents:
            if ent.label_ == "PERSON" and name is None:
                name = ent.text
            elif ent.label_ == "ORG":
                companies.append(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                locations.append(ent.text)
            elif ent.label_ == "DATE":
                dates.append(ent.text)

        return {
            "name": name,
            "companies": list(set(companies)),  # Deduplicate
            "locations": list(set(locations)),
            "dates": dates,
        }

    def _extract_skills(self, doc: spacy.tokens.Doc) -> List[ExtractedSkill]:
        """Extract skills using PhraseMatcher."""
        return self.skill_matcher.match_skills(doc)

    def _calculate_experience(self, dates: List[str]) -> float | None:
        """Calculate total work experience from extracted dates.

        Logic:
        - Find earliest and latest dates
        - Calculate difference in years
        - Fallback: None if insufficient data
        """
        if len(dates) < 2:
            return None

        # Parse dates (simplified - use dateparser in production)
        years = []
        for date_str in dates:
            # Extract 4-digit year
            import re
            match = re.search(r'\b(19|20)\d{2}\b', date_str)
            if match:
                years.append(int(match.group()))

        if len(years) < 2:
            return None

        # Experience = latest year - earliest year
        return float(max(years) - min(years))
```

### 2. SkillMatcher (`skill_matcher.py`)

```python
import json
import os
from typing import List
import spacy
from spacy.matcher import PhraseMatcher
from ...domain.models.cv_analysis import ExtractedSkill

class SkillMatcher:
    """Match skills using spaCy PhraseMatcher and skill gazetteer.

    Uses skill_patterns.json with categorized skills:
    - programming_languages
    - frameworks
    - databases
    - tools
    - soft_skills
    """

    def __init__(self):
        """Initialize matcher with skill patterns."""
        self.skill_patterns = self._load_patterns()
        self.phrase_matcher = None  # Lazy init per language

    def _load_patterns(self) -> dict:
        """Load skill patterns from JSON file."""
        pattern_file = os.path.join(
            os.path.dirname(__file__),
            "skill_patterns.json"
        )
        with open(pattern_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def match_skills(self, doc: spacy.tokens.Doc) -> List[ExtractedSkill]:
        """Match skills in spaCy doc using PhraseMatcher.

        Args:
            doc: spaCy processed document

        Returns:
            List of ExtractedSkill objects with categories
        """
        # Lazy init PhraseMatcher for doc's language
        if self.phrase_matcher is None:
            self.phrase_matcher = self._build_phrase_matcher(doc.vocab)

        # Find matches
        matches = self.phrase_matcher(doc)

        # Convert to ExtractedSkill objects
        skills = []
        seen_skills = set()  # Deduplicate

        for match_id, start, end in matches:
            skill_text = doc[start:end].text
            skill_lower = skill_text.lower()

            if skill_lower not in seen_skills:
                seen_skills.add(skill_lower)
                category = self._categorize_skill(skill_lower)
                skills.append(ExtractedSkill(
                    skill=skill_text,
                    category=category,
                    proficiency=None,  # TODO: Infer from context in Phase 3
                    years=None
                ))

        return skills

    def _build_phrase_matcher(self, vocab: spacy.vocab.Vocab) -> PhraseMatcher:
        """Build PhraseMatcher with all skill patterns."""
        matcher = PhraseMatcher(vocab, attr="LOWER")  # Case-insensitive

        # Add all skills from all categories
        all_skills = []
        for category, skills in self.skill_patterns.items():
            if category != "common":  # Skip metadata
                all_skills.extend(skills)

        # Convert to spaCy patterns
        patterns = [vocab.make_doc(skill) for skill in all_skills]
        matcher.add("SKILL", patterns)

        return matcher

    def _categorize_skill(self, skill: str) -> str:
        """Categorize skill based on patterns."""
        skill_lower = skill.lower()

        for category, skills in self.skill_patterns.items():
            if category == "common":
                continue
            if skill_lower in [s.lower() for s in skills]:
                return category

        return "technical"  # Default category
```

### 3. Enhanced skill_patterns.json

```json
{
  "common": [],
  "programming_languages": [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl",
    "Objective-C", "Dart", "Lua", "Haskell", "Elixir", "Erlang", "Clojure"
  ],
  "frameworks": [
    "React", "Angular", "Vue.js", "Next.js", "FastAPI", "Django", "Flask",
    "Spring Boot", "Express.js", "NestJS", "Laravel", "Ruby on Rails",
    "ASP.NET", "Flutter", "React Native", "Svelte", "Nuxt.js", "Gatsby"
  ],
  "databases": [
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "Oracle", "SQL Server", "SQLite", "DynamoDB", "Firebase", "Neo4j",
    "CouchDB", "MariaDB", "TimescaleDB", "InfluxDB"
  ],
  "tools": [
    "Docker", "Kubernetes", "Git", "Jenkins", "GitHub Actions", "GitLab CI",
    "Terraform", "Ansible", "AWS", "Azure", "GCP", "Linux", "Nginx",
    "Apache", "Webpack", "Vite", "Babel", "ESLint", "Pytest", "Jest"
  ],
  "soft_skills": [
    "Leadership", "Communication", "Problem Solving", "Teamwork", "Agile",
    "Scrum", "Project Management", "Critical Thinking", "Adaptability"
  ],
  "vi": [
    "Lãnh đạo", "Giao tiếp", "Làm việc nhóm", "Giải quyết vấn đề", "Quản lý dự án"
  ]
}
```

---

## Implementation Steps

### Step 1: Setup (1 hour)
1. Install spaCy models:
   ```bash
   python -m spacy download en_core_web_sm
   python -m spacy download vi_core_news_sm
   ```
2. Create files: `spacy_ner_extractor.py`, `skill_matcher.py`
3. Update `skill_patterns.json` with categories

### Step 2: Implement SkillMatcher (2-3 hours)
1. Load skill patterns from JSON
2. Build PhraseMatcher pipeline
3. Implement `match_skills()` with deduplication
4. Implement `_categorize_skill()` lookup
5. Add docstrings

### Step 3: Implement SpacyNERExtractor (4-5 hours)
1. Lazy model loading (singleton pattern)
2. Language detection heuristic
3. Entity extraction (`_extract_entities`)
4. Skill extraction integration
5. Experience calculation from dates
6. Confidence scoring integration (Phase 1)
7. Add docstrings

### Step 4: Unit Tests (5-6 hours)
1. `test_spacy_ner_extractor.py`:
   - Test entity extraction (PERSON, ORG, LOC, DATE)
   - Test language detection (English vs Vietnamese)
   - Test experience calculation
   - Test confidence scoring
2. `test_skill_matcher.py`:
   - Test skill matching (exact + fuzzy)
   - Test categorization
   - Test deduplication
3. Fixtures: Sample CVs with known entities

### Step 5: Integration Test (2-3 hours)
1. Test on real English CV (PDF)
2. Test on real Vietnamese CV (PDF)
3. Compare NER results vs manual annotation
4. Benchmark performance (< 300ms target)

---

## Testing Strategy

### Unit Tests (10 tests total)

**SpacyNERExtractor (6 tests)**:
1. `test_extract_entities_english_cv` - Extract PERSON, ORG, LOC
2. `test_extract_entities_vietnamese_cv` - Vietnamese entity extraction
3. `test_detect_language_english` - Auto-detect English
4. `test_detect_language_vietnamese` - Auto-detect Vietnamese (by chars)
5. `test_calculate_experience_from_dates` - 2018-2023 → 5 years
6. `test_extract_no_entities` - Empty CV handling

**SkillMatcher (4 tests)**:
1. `test_match_skills_programming_languages` - Python, Java
2. `test_match_skills_frameworks` - React, FastAPI
3. `test_categorize_skill_correct_category` - "Python" → programming_languages
4. `test_match_skills_deduplication` - "Python" x2 → 1 result

### Integration Tests (2 tests)

1. **test_spacy_ner_full_pipeline_english**:
   - Input: Sample English CV with companies, skills, dates
   - Extract: All entities + skills
   - Assert: Extracted entities match expected, confidence > 0.85

2. **test_spacy_ner_full_pipeline_vietnamese**:
   - Input: Vietnamese CV
   - Extract: Name, companies (Vietnamese names)
   - Assert: Language detected as "vi", entities extracted

---

## Success Criteria

### Phase Completion Checklist
- [ ] SpacyNERExtractor class implemented
- [ ] SkillMatcher class implemented
- [ ] skill_patterns.json enhanced (500+ skills, categorized)
- [ ] 10 unit tests passing
- [ ] 2 integration tests passing
- [ ] Code coverage ≥ 85%
- [ ] Model loading time < 500ms
- [ ] Extraction time < 300ms per CV
- [ ] Docstrings for all public methods
- [ ] Type hints complete
- [ ] No linting errors

### Validation Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Name extraction accuracy | ≥ 85% | 50 CVs manual review |
| Company extraction accuracy | ≥ 80% | 50 CVs |
| Skill matching hit rate | ≥ 60% | % of known skills found |
| Vietnamese support | ≥ 75% | Vietnamese CV accuracy |
| Extraction time | < 300ms | pytest benchmark |
| Model memory | < 500MB | Memory profiler |

---

## Rollback Plan

Phase 2 creates new files only. Rollback = delete 2 files, revert skill_patterns.json.

**Steps**:
1. Remove `spacy_ner_extractor.py`
2. Remove `skill_matcher.py`
3. Revert `skill_patterns.json` to original
4. No impact on Phase 1 or existing functionality

---

## Performance Benchmarks

### Target Metrics
- Model loading (first call): < 500ms
- Entity extraction: < 200ms
- Skill matching: < 100ms
- Total Phase 2: < 300ms

### Optimization Notes
- Use `exclude` parameter in `spacy.load()` to disable unused pipeline components (parser, lemmatizer)
- Example: `spacy.load("en_core_web_sm", exclude=["parser", "lemmatizer"])`
- Reduces memory + speeds up by 30-40%

---

## Known Limitations

### Vietnamese NER Accuracy
- `vi_core_news_sm` has lower entity recognition accuracy (~75%) than English (~90%)
- **Mitigation**: Increase LLM fallback threshold for Vietnamese CVs (0.6 instead of 0.7)

### Skill Gazetteer Maintenance
- 500-skill list requires periodic updates (new frameworks, languages)
- **Mitigation**: Quarterly review + community contributions

### Entity Ambiguity
- "Python" could be language or company (very rare)
- **Mitigation**: Context-based filtering in Phase 3 orchestrator

---

## Next Steps

**After Phase 2 Completion**:
1. Proceed to Phase 3: Hybrid Orchestrator (combines Phase 1 + Phase 2)
2. Benchmark NER accuracy on 100+ real CVs
3. Calibrate confidence thresholds per entity type

**Handoff to Phase 3**:
- SpacyNERExtractor ready for orchestration
- SkillMatcher provides categorized skills
- Confidence scores align with Phase 1 format

---

**Phase 2 Status**: Ready for Implementation (after Phase 1)
**Est. Completion**: 4-5 days
