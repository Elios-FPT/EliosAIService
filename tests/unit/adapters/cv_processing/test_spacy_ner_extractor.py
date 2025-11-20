"""Unit tests for SpacyNERExtractor."""

import pytest
from src.adapters.cv_processing.spacy_ner_extractor import SpacyNERExtractor


class TestSpacyNERExtractor:
    """Test suite for SpacyNERExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        try:
            ext = SpacyNERExtractor()
            # Test that model loads
            _ = ext.nlp_en
            return ext
        except RuntimeError:
            pytest.skip("spaCy English model not installed")

    def test_extract_entities_english_cv(self, extractor):
        """Test entity extraction from English CV text."""
        cv_text = """
        John Doe
        Senior Software Engineer at Google
        Mountain View, California
        January 2020 - Present

        Skills: Python, React, PostgreSQL, Docker, AWS
        """

        result = extractor.extract(cv_text, language="en")

        # Verify name extraction
        assert result["name"] is not None
        assert "John" in result["name"] or "Doe" in result["name"]

        # Verify company extraction
        assert len(result["companies"]) >= 1
        assert any("Google" in company for company in result["companies"])

        # Verify location extraction
        assert len(result["locations"]) >= 1

        # Verify skills extraction
        assert len(result["skills"]) >= 3

        # Verify confidence scores
        assert "confidence" in result
        assert "fields" in result["confidence"]
        assert "overall" in result["confidence"]

    def test_extract_name_person_entity(self, extractor):
        """Test that PERSON entity is extracted as name."""
        cv_text = "Jane Smith is a software developer."

        result = extractor.extract(cv_text)

        assert result["name"] is not None
        # spaCy should recognize "Jane Smith" as PERSON
        assert "Jane" in result["name"] or "Smith" in result["name"]

    def test_extract_companies_org_entity(self, extractor):
        """Test that ORG entities are extracted as companies."""
        cv_text = """
        Work Experience:
        - Microsoft (2018-2020)
        - Amazon (2020-2022)
        - Meta (2022-Present)
        """

        result = extractor.extract(cv_text)

        # Should extract multiple companies
        companies = result["companies"]
        assert len(companies) >= 2

    def test_extract_locations_gpe_entity(self, extractor):
        """Test that GPE/LOC entities are extracted as locations."""
        cv_text = """
        Worked in San Francisco, New York, and London.
        """

        result = extractor.extract(cv_text)

        locations = result["locations"]
        assert len(locations) >= 2

    def test_extract_dates_date_entity(self, extractor):
        """Test that DATE entities are extracted."""
        cv_text = """
        Education: 2014-2018
        Experience: January 2020 - Present
        Project completed in March 2023
        """

        result = extractor.extract(cv_text)

        dates = result["dates"]
        # Should extract multiple date references
        assert len(dates) >= 2

    def test_detect_language_english(self, extractor):
        """Test that English text is detected correctly."""
        text = "This is an English CV with no special characters."

        lang = extractor._detect_language(text)

        assert lang == "en"

    def test_detect_language_vietnamese(self, extractor):
        """Test that Vietnamese text is detected correctly."""
        text = "Tôi là một lập trình viên phần mềm với kinh nghiệm về Python và Django."

        lang = extractor._detect_language(text)

        assert lang == "vi"

    def test_calculate_experience_from_dates(self, extractor):
        """Test experience calculation from date ranges."""
        dates = ["2018", "2020", "2023"]

        experience = extractor._calculate_experience(dates)

        # 2023 - 2018 = 5 years
        assert experience == 5.0

    def test_calculate_experience_insufficient_dates(self, extractor):
        """Test experience calculation with insufficient dates."""
        dates = ["2020"]

        experience = extractor._calculate_experience(dates)

        assert experience is None

    def test_calculate_experience_no_dates(self, extractor):
        """Test experience calculation with no dates."""
        dates = []

        experience = extractor._calculate_experience(dates)

        assert experience is None

    def test_extract_skills_integration(self, extractor):
        """Test that skills are extracted and categorized."""
        cv_text = """
        Technical Skills:
        - Programming: Python, Java, JavaScript
        - Frameworks: React, Django, FastAPI
        - Databases: PostgreSQL, MongoDB
        - Tools: Docker, Kubernetes, Git
        """

        result = extractor.extract(cv_text)

        skills = result["skills"]
        # Should extract multiple skills
        assert len(skills) >= 8

        # Verify skills have categories
        categories = {s.category for s in skills}
        assert len(categories) >= 3

    def test_extract_no_entities(self, extractor):
        """Test extraction on text with no recognizable entities."""
        cv_text = "Some random text without names or companies."

        result = extractor.extract(cv_text)

        assert result["name"] is None
        assert len(result["companies"]) == 0
        assert len(result["locations"]) == 0

    def test_extract_confidence_scores(self, extractor):
        """Test that confidence scores are calculated."""
        cv_text = """
        John Smith
        Software Engineer at Google
        San Francisco
        Skills: Python, React, Docker
        """

        result = extractor.extract(cv_text)

        assert "confidence" in result
        confidence = result["confidence"]

        # Verify field scores
        assert "fields" in confidence
        assert "name" in confidence["fields"]
        assert "companies" in confidence["fields"]
        assert "locations" in confidence["fields"]
        assert "skills" in confidence["fields"]

        # Verify overall score
        assert "overall" in confidence
        assert 0.0 <= confidence["overall"] <= 1.0

    def test_extract_deduplicates_companies(self, extractor):
        """Test that duplicate companies are deduplicated."""
        cv_text = """
        Worked at Google from 2018-2020.
        Returned to Google in 2022.
        Currently at Google.
        """

        result = extractor.extract(cv_text)

        companies = result["companies"]
        # Should deduplicate "Google"
        google_count = sum(1 for c in companies if "Google" in c)
        assert google_count == 1

    def test_extract_deduplicates_locations(self, extractor):
        """Test that duplicate locations are deduplicated."""
        cv_text = """
        Lived in New York.
        Worked in New York.
        Based in New York.
        """

        result = extractor.extract(cv_text)

        locations = result["locations"]
        # Should deduplicate "New York"
        ny_count = sum(1 for loc in locations if "New York" in loc)
        assert ny_count == 1

    def test_model_lazy_loading(self, extractor):
        """Test that spaCy model is loaded lazily."""
        # First access should load the model
        nlp1 = extractor.nlp_en
        assert nlp1 is not None

        # Second access should return same instance
        nlp2 = extractor.nlp_en
        assert nlp1 is nlp2

    def test_extract_with_full_cv(self, extractor):
        """Test extraction on a full CV sample."""
        # Use fixture from Phase 1
        with open(
            "tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8"
        ) as f:
            cv_text = f.read()

        result = extractor.extract(cv_text)

        # Verify comprehensive extraction
        assert result["name"] is not None
        assert len(result["companies"]) >= 1
        assert len(result["locations"]) >= 1
        assert len(result["skills"]) >= 5
        assert result["experience_years"] is not None
        assert result["confidence"]["overall"] > 0.5
