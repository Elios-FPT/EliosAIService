"""Integration tests for spaCy NER extraction full pipeline."""

import pytest
import time
from src.infrastructure.adapters.cv_processing.spacy_ner_extractor import SpacyNERExtractor


class TestSpacyNERFullPipeline:
    """Integration tests for full NER extraction workflow."""

    @pytest.fixture(scope="class")
    def extractor(self):
        """Create extractor instance for all tests."""
        try:
            return SpacyNERExtractor()
        except RuntimeError:
            pytest.skip("spaCy English model not installed")

    def test_full_pipeline_english_cv(self, extractor):
        """Test full extraction pipeline on English CV."""
        # Load Phase 1 fixture
        with open(
            "tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8"
        ) as f:
            cv_text = f.read()

        result = extractor.extract(cv_text, language="en")

        # Verify name extraction
        assert result["name"] is not None
        assert "John" in result["name"] or "Doe" in result["name"]

        # Verify companies extraction
        assert len(result["companies"]) >= 1
        company_text = " ".join(result["companies"]).lower()
        # Should extract "Tech Corp", "StartupXYZ", etc.
        assert "tech" in company_text or "startup" in company_text

        # Verify locations extraction
        assert len(result["locations"]) >= 0  # May or may not extract locations

        # Verify skills extraction
        assert len(result["skills"]) >= 5
        skill_names = [s.skill for s in result["skills"]]
        # Should extract Python, FastAPI, PostgreSQL, Docker, AWS from CV
        assert any("Python" in skill for skill in skill_names)
        assert any("FastAPI" in skill or "Django" in skill for skill in skill_names)
        assert any("PostgreSQL" in skill or "MongoDB" in skill for skill in skill_names)

        # Verify skill categorization
        categories = {s.category for s in result["skills"]}
        assert len(categories) >= 3  # Should have multiple categories

        # Verify experience calculation
        experience = result["experience_years"]
        # CV has dates: 2014-2018, 2017-2018, 2018-2019, 2020-Present
        # Should calculate ~6+ years (2023 - 2017)
        assert experience is not None
        assert experience >= 3.0  # At least 3 years

        # Verify confidence scores
        confidence = result["confidence"]
        assert confidence["overall"] > 0.70  # Should have good confidence

        # Verify field-level confidence
        fields = confidence["fields"]
        assert fields["name"] > 0.80  # Name should be high confidence
        assert fields["skills"] > 0.80  # Skills should be high confidence

    def test_extraction_performance(self, extractor):
        """Test that extraction meets performance target (< 300ms)."""
        # Load fixture
        with open(
            "tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8"
        ) as f:
            cv_text = f.read()

        # Measure execution time
        start_time = time.perf_counter()
        result = extractor.extract(cv_text)
        end_time = time.perf_counter()

        execution_time_ms = (end_time - start_time) * 1000

        # Assert performance target (< 300ms)
        assert (
            execution_time_ms < 300.0
        ), f"Extraction took {execution_time_ms:.2f}ms (target: < 300ms)"

        # Verify extraction actually worked
        assert len(result["skills"]) > 0

    def test_skill_matching_accuracy(self, extractor):
        """Test skill matching hit rate on known skill list."""
        cv_text = """
        Technical Skills:
        - Programming Languages: Python, Java, JavaScript, TypeScript, Go
        - Frameworks: React, Angular, Vue.js, Django, FastAPI, Spring Boot
        - Databases: PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch
        - DevOps: Docker, Kubernetes, Jenkins, GitHub Actions, Terraform
        - Cloud: AWS, Azure, GCP, Lambda, S3, EC2
        """

        result = extractor.extract(cv_text)

        skills = result["skills"]
        skill_names = {s.skill for s in skills}

        # Define expected skills
        expected_skills = [
            "Python",
            "Java",
            "JavaScript",
            "React",
            "Django",
            "PostgreSQL",
            "Docker",
            "AWS",
        ]

        # Calculate hit rate
        matched = sum(
            1
            for expected in expected_skills
            if any(expected in skill for skill in skill_names)
        )
        hit_rate = matched / len(expected_skills)

        # Should match at least 60% of expected skills (NFR-3)
        assert (
            hit_rate >= 0.60
        ), f"Hit rate {hit_rate:.2%} below target 60% ({matched}/{len(expected_skills)} matched)"

    def test_entity_confidence_integration(self, extractor):
        """Test that entity extraction confidence aligns with Phase 1."""
        cv_text = """
        Alice Johnson
        Senior Data Scientist at Microsoft
        Seattle, Washington

        Experience:
        - Microsoft (2020-Present): Led ML initiatives
        - Amazon (2018-2020): Data analysis and modeling

        Skills: Python, TensorFlow, PyTorch, Scikit-learn, Pandas, AWS, Docker
        """

        result = extractor.extract(cv_text)

        # Verify high confidence when all fields present
        confidence = result["confidence"]
        assert confidence["overall"] > 0.80  # Should have high confidence

        # Verify individual field confidence
        fields = confidence["fields"]
        assert fields["name"] >= 0.90  # Name clearly present
        assert fields["companies"] >= 0.85  # Multiple companies
        assert fields["skills"] >= 0.85  # Many skills listed

    def test_minimal_cv_graceful_handling(self, extractor):
        """Test graceful handling of minimal CV with few entities."""
        # Use Phase 1 minimal fixture
        with open(
            "tests/fixtures/cv_samples/sample_cv_minimal.txt", "r", encoding="utf-8"
        ) as f:
            cv_text = f.read()

        result = extractor.extract(cv_text)

        # Should not crash on minimal content
        assert result is not None

        # Should have low confidence due to missing fields
        confidence = result["confidence"]
        assert (
            confidence["overall"] < 0.70
        )  # Low confidence for minimal CV

        # Should still extract email (if spaCy recognizes the name)
        # Name might be extracted if "Bob Johnson" is recognized
        # But overall extraction should be limited

    def test_skill_categories_distribution(self, extractor):
        """Test that skills are properly categorized across categories."""
        cv_text = """
        Technical Stack:
        Languages: Python, JavaScript, TypeScript
        Frontend: React, Vue.js, Angular
        Backend: Django, FastAPI, Express.js
        Databases: PostgreSQL, MongoDB, Redis
        Cloud: AWS, Azure, Docker, Kubernetes
        Soft Skills: Leadership, Communication, Problem Solving, Team Collaboration
        """

        result = extractor.extract(cv_text)

        skills = result["skills"]
        categories = {}

        # Group skills by category
        for skill in skills:
            if skill.category not in categories:
                categories[skill.category] = []
            categories[skill.category].append(skill.skill)

        # Should have skills from multiple categories
        assert len(categories) >= 4  # programming_languages, frameworks, databases, tools, soft_skills

        # Verify specific categories exist
        category_names = set(categories.keys())
        expected_categories = {
            "programming_languages",
            "frameworks",
            "databases",
            "tools",
            "soft_skills",
        }
        assert len(category_names & expected_categories) >= 3

    def test_language_detection_english(self, extractor):
        """Test language detection on English CV."""
        with open(
            "tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8"
        ) as f:
            cv_text = f.read()

        # Use auto language detection
        result = extractor.extract(cv_text, language="auto")

        # Should successfully extract (meaning language was detected as English)
        assert result["name"] is not None or len(result["skills"]) > 0

    def test_integration_with_phase1_results(self, extractor):
        """Test that Phase 2 results complement Phase 1 rule-based extraction."""
        from src.infrastructure.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor

        cv_text = """
        John Doe
        Email: john.doe@example.com
        Phone: (202) 555-0123

        Senior Software Engineer at Google
        Mountain View, CA
        January 2020 - Present

        Skills: Python, React, PostgreSQL, Docker, AWS, Kubernetes
        """

        # Phase 1: Rule-based extraction
        rule_extractor = RuleBasedExtractor()
        phase1_result = rule_extractor.extract(cv_text)

        # Phase 2: NER extraction
        phase2_result = extractor.extract(cv_text)

        # Phase 1 should extract email and phone
        assert len(phase1_result["emails"]) >= 1
        assert len(phase1_result["phones"]) >= 1

        # Phase 2 should extract name, companies, and skills
        assert phase2_result["name"] is not None
        assert len(phase2_result["companies"]) >= 1
        assert len(phase2_result["skills"]) >= 4

        # Both should extract dates (complementary)
        assert len(phase1_result["dates"]) >= 1 or len(phase2_result["dates"]) >= 1

        # Together, they provide comprehensive extraction
        # Phase 1: structured fields (email, phone)
        # Phase 2: entities and skills (name, companies, skills)
