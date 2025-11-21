# Phase 2: Test Scenarios & Fixtures

**Duration**: 2 days
**Deliverable**: YAML scenarios (15 tests) + CV fixtures (5 PDFs) + answer generator

---

## Overview

Define test scenarios in YAML format, create CV fixtures simulating real candidates, implement answer generator producing predefined responses at different quality levels.

---

## File Structure

```
tests/bot/
├── scenarios/
│   ├── mock_scenarios.yaml          # 10 mock test configs
│   └── real_scenarios.yaml          # 5 real test configs
├── fixtures/
│   ├── cvs/                         # 5 pre-made CVs
│   │   ├── python_senior.pdf
│   │   ├── fullstack_mid.pdf
│   │   ├── backend_junior.pdf
│   │   ├── devops_senior.pdf
│   │   └── frontend_mid.pdf
│   └── baselines/
│       └── baseline_metrics.json    # Performance baselines
├── answer_generator.py              # Answer generation logic
└── cv_generator.py                  # CV PDF generation (one-time use)
```

---

## 1. Mock Scenarios (10 Tests)

**File**: `tests/bot/scenarios/mock_scenarios.yaml`

```yaml
# Mock test scenarios (USE_MOCK_ADAPTERS=true)
# Cost: $0.00, Duration: ~20s total

scenarios:
  # Scenario 1: Basic happy path
  - id: mock_001_basic_flow
    name: "Basic interview flow (3 questions, no follow-ups)"
    description: "Verify happy path: 3 questions answered with good quality, no follow-ups triggered"

    config:
      use_mock: true
      cv_fixture: python_senior.pdf
      expected_questions: 3
      answer_quality: good
      expected_follow_ups: 0
      timeout: 10.0

    assertions:
      # Final state
      - expression: "interview.status == 'COMPLETE'"
        message: "Interview should complete successfully"

      # Question count
      - expression: "len(answers) == 3"
        message: "Should answer all 3 questions"

      # Evaluation scores
      - expression: "all(eval.score >= 80 for eval in evaluations)"
        message: "Good answers should score >=80"

      # No follow-ups
      - expression: "len(follow_ups) == 0"
        message: "No follow-ups for good answers"

      # DB persistence
      - expression: "db.interview_exists(interview_id)"
        message: "Interview persisted to DB"

      - expression: "db.count_answers(interview_id) == 3"
        message: "All answers persisted"

  # Scenario 2: Follow-up trigger
  - id: mock_002_follow_up_trigger
    name: "Follow-up triggered by weak answer"
    description: "Verify follow-up generation when answer has gaps"

    config:
      use_mock: true
      cv_fixture: fullstack_mid.pdf
      expected_questions: 2
      answer_quality: weak
      expected_follow_ups: 1
      timeout: 15.0

    assertions:
      - expression: "interview.status == 'COMPLETE'"
      - expression: "len(follow_ups) >= 1"
        message: "Weak answer should trigger follow-up"
      - expression: "'gap' in follow_ups[0].generated_reason.lower()"
        message: "Follow-up reason should mention gap"
      - expression: "follow_ups[0].order_in_sequence == 1"
        message: "First follow-up has order=1"

  # Scenario 3: State transitions
  - id: mock_003_state_transitions
    name: "State transition validation"
    description: "Track all state transitions, verify no invalid transitions"

    config:
      use_mock: true
      cv_fixture: backend_junior.pdf
      expected_questions: 3
      answer_quality: average
      track_transitions: true
      timeout: 12.0

    assertions:
      - expression: "len(state_transitions) > 0"
        message: "State transitions tracked"
      - expression: "state_transitions[0] == 'IDLE'"
        message: "Start in IDLE state"
      - expression: "state_transitions[-1] == 'COMPLETE'"
        message: "End in COMPLETE state"
      - expression: "no_invalid_transitions(state_transitions)"
        message: "All transitions valid per state machine"
      - expression: "'IDLE' in state_transitions"
      - expression: "'QUESTIONING' in state_transitions"
      - expression: "'EVALUATING' in state_transitions"

  # Scenario 4: Multi-follow-up (3 follow-ups)
  - id: mock_004_multi_follow_up
    name: "Multiple follow-ups (max 3)"
    description: "Verify follow-up limit (max 3 per question)"

    config:
      use_mock: true
      cv_fixture: devops_senior.pdf
      expected_questions: 1
      answer_quality: weak
      force_follow_ups: 3
      expected_follow_ups: 3
      timeout: 20.0

    assertions:
      - expression: "len(follow_ups) == 3"
        message: "Max 3 follow-ups per question"
      - expression: "follow_ups[0].order_in_sequence == 1"
      - expression: "follow_ups[1].order_in_sequence == 2"
      - expression: "follow_ups[2].order_in_sequence == 3"
      - expression: "all(f.parent_question_id == parent_q_id for f in follow_ups)"
        message: "All follow-ups reference same parent"

  # Scenario 5: Error recovery
  - id: mock_005_error_recovery
    name: "Error recovery (timeout retry)"
    description: "Verify timeout error handling and retry logic"

    config:
      use_mock: true
      cv_fixture: frontend_mid.pdf
      expected_questions: 2
      answer_quality: good
      inject_error:
        type: timeout
        at_message_index: 2
        recoverable: true
      timeout: 15.0

    assertions:
      - expression: "len(errors) > 0"
        message: "Error injected and tracked"
      - expression: "errors[0]['code'] == 'TIMEOUT'"
      - expression: "interview.status == 'COMPLETE'"
        message: "Interview completes despite error"

  # Scenario 6: Empty answer handling
  - id: mock_006_empty_answer
    name: "Empty answer edge case"
    description: "Verify empty/whitespace-only answers rejected"

    config:
      use_mock: true
      cv_fixture: python_senior.pdf
      expected_questions: 1
      answer_text: "   "  # Whitespace only
      expect_error: true
      timeout: 5.0

    assertions:
      - expression: "error_occurred == true"
        message: "Empty answer should raise error"
      - expression: "'empty' in error_message.lower() or 'blank' in error_message.lower()"

  # Scenario 7: Long answer handling
  - id: mock_007_long_answer
    name: "Long answer (>2000 chars)"
    description: "Verify system handles long answers without truncation"

    config:
      use_mock: true
      cv_fixture: fullstack_mid.pdf
      expected_questions: 1
      answer_text_length: 2500  # Generate 2500 char answer
      answer_quality: good
      timeout: 10.0

    assertions:
      - expression: "len(answers[0].text) == 2500"
        message: "Long answer not truncated"
      - expression: "answers[0].text == original_answer_text"
        message: "Answer preserved exactly"

  # Scenario 8: WebSocket reconnect
  - id: mock_008_reconnect
    name: "WebSocket reconnect after disconnect"
    description: "Verify reconnect logic (if implemented)"

    config:
      use_mock: true
      cv_fixture: backend_junior.pdf
      expected_questions: 2
      answer_quality: average
      inject_disconnect:
        at_message_index: 3
        reconnect_delay: 1.0
      timeout: 20.0

    skip: true  # Skip for MVP (reconnect not implemented)

    assertions:
      - expression: "reconnect_succeeded == true"
        message: "Reconnect successful"
      - expression: "interview.status == 'COMPLETE'"
        message: "Interview completes after reconnect"

  # Scenario 9: Concurrent interviews
  - id: mock_009_concurrent
    name: "Concurrent interviews (2 bots)"
    description: "Verify multiple bots can run simultaneously"

    config:
      use_mock: true
      concurrent_bots: 2
      cv_fixtures:
        - python_senior.pdf
        - devops_senior.pdf
      expected_questions: 2
      answer_quality: good
      timeout: 15.0

    assertions:
      - expression: "len(completed_interviews) == 2"
        message: "Both interviews complete"
      - expression: "interview_1.id != interview_2.id"
        message: "Separate interview IDs"
      - expression: "no_cross_contamination(interview_1, interview_2)"
        message: "No data leakage between interviews"

  # Scenario 10: Full metrics tracking
  - id: mock_010_metrics
    name: "Metrics collection validation"
    description: "Verify all metrics tracked correctly"

    config:
      use_mock: true
      cv_fixture: frontend_mid.pdf
      expected_questions: 3
      answer_quality: average
      enable_metrics: true
      timeout: 12.0

    assertions:
      - expression: "metrics.latency['connect'] > 0"
        message: "Connection latency tracked"
      - expression: "metrics.latency['send_answer'] is not None"
        message: "Answer send latency tracked"
      - expression: "len(metrics.states) > 0"
        message: "State transitions tracked"
      - expression: "metrics.summary['questions_received'] == 3"
      - expression: "metrics.summary['answers_sent'] == 3"
```

---

## 2. Real Scenarios (5 Tests)

**File**: `tests/bot/scenarios/real_scenarios.yaml`

```yaml
# Real test scenarios (USE_MOCK_ADAPTERS=false)
# Cost: ~$0.45, Duration: ~60s total

scenarios:
  # Scenario 1: Question generation quality
  - id: real_001_prompt_quality
    name: "Question generation quality (Python senior)"
    description: "Verify generated questions are verbal, appropriate difficulty, CV-aligned"

    config:
      use_mock: false
      cv_fixture: python_senior.pdf
      expected_questions: 3
      answer_quality: good
      cost_budget: 0.15
      timeout: 20.0

    assertions:
      # Question quality
      - expression: "all(is_verbal_question(q.text) for q in questions)"
        message: "All questions verbal (no 'write code', 'draw diagram')"

      - expression: "has_difficulty_distribution(questions, ['EASY', 'MEDIUM', 'HARD'])"
        message: "Difficulty distribution present"

      - expression: "skill_coverage(questions, cv_skills) >= 0.8"
        message: "Questions cover >=80% of CV skills"

      # Constraints validation
      - expression: "no_code_writing_questions(questions)"
        message: "No code-writing questions (constraint violated)"

      - expression: "no_diagram_questions(questions)"
        message: "No diagram questions"

      # Cost
      - expression: "actual_cost <= cost_budget"
        message: "Cost within budget"

  # Scenario 2: Evaluation accuracy
  - id: real_002_evaluation_accuracy
    name: "Evaluation accuracy (weak answer detection)"
    description: "Verify LLM correctly identifies weak answers, triggers follow-ups"

    config:
      use_mock: false
      cv_fixture: devops_senior.pdf
      expected_questions: 2
      answer_quality: weak
      cost_budget: 0.12
      timeout: 20.0

    assertions:
      - expression: "weak_answer_detected == true"
        message: "LLM should detect weak answer"

      - expression: "len(evaluations) == 2"

      - expression: "evaluations[0].score < 60"
        message: "Weak answer should score <60"

      - expression: "len(evaluations[0].gaps) > 0"
        message: "Gaps identified in weak answer"

      - expression: "follow_up_generated == true"
        message: "Follow-up generated for weak answer"

      - expression: "actual_cost <= cost_budget"

  # Scenario 3: Follow-up quality
  - id: real_003_followup_quality
    name: "Follow-up question quality (context-aware)"
    description: "Verify follow-up questions are context-aware, target gaps"

    config:
      use_mock: false
      cv_fixture: backend_junior.pdf
      expected_questions: 2
      answer_quality: average
      expected_follow_ups: 1
      cost_budget: 0.10
      timeout: 25.0

    assertions:
      - expression: "len(follow_ups) >= 1"
        message: "Follow-up generated"

      - expression: "is_context_aware(follow_ups[0], parent_question, answer)"
        message: "Follow-up references parent question/answer"

      - expression: "targets_gaps(follow_ups[0], evaluation.gaps)"
        message: "Follow-up targets identified gaps"

      - expression: "is_verbal_question(follow_ups[0].text)"
        message: "Follow-up is verbal (no code/diagrams)"

      - expression: "actual_cost <= cost_budget"

  # Scenario 4: Skill coverage
  - id: real_004_skill_coverage
    name: "Skill coverage (CV alignment)"
    description: "Verify questions cover diverse skills from CV"

    config:
      use_mock: false
      cv_fixture: fullstack_mid.pdf
      expected_questions: 3
      answer_quality: good
      cost_budget: 0.10
      timeout: 20.0

    assertions:
      - expression: "len(unique_skills(questions)) >= 3"
        message: "Questions cover >=3 different skills"

      - expression: "all(skill in cv_skills for skill in question_skills)"
        message: "All question skills from CV"

      - expression: "skill_diversity(questions) >= 0.7"
        message: "Skill diversity >=70%"

      - expression: "actual_cost <= cost_budget"

  # Scenario 5: Summary generation
  - id: real_005_summary_quality
    name: "Summary generation (comprehensive feedback)"
    description: "Verify final summary is comprehensive, actionable"

    config:
      use_mock: false
      cv_fixture: python_senior.pdf
      expected_questions: 3
      answer_quality: average
      cost_budget: 0.12
      timeout: 25.0

    assertions:
      - expression: "summary is not None"
        message: "Summary generated"

      - expression: "len(summary.strengths) > 0"
        message: "Strengths identified"

      - expression: "len(summary.weaknesses) > 0"
        message: "Weaknesses identified"

      - expression: "len(summary.study_topics) > 0"
        message: "Study topics recommended"

      - expression: "summary.overall_score > 0"
        message: "Overall score calculated"

      - expression: "summary.overall_score == weighted_avg(evaluations)"
        message: "Score matches weighted average"

      - expression: "actual_cost <= cost_budget"
```

---

## 3. Answer Generator

**File**: `tests/bot/answer_generator.py`

```python
"""Generate predefined answers at different quality levels."""

import random
import re
from typing import Literal

QualityLevel = Literal["good", "average", "weak"]


class AnswerGenerator:
    """Generate predefined answers matching quality level.

    Uses templates to produce realistic but reproducible answers.
    """

    # Template placeholders
    TEMPLATES = {
        "good": [
            "{topic} is {definition}. Key concepts include {concept_1}, {concept_2}, and {concept_3}. "
            "For example, {example}. In practice, this is important because {importance}.",

            "The main advantage of {topic} is {benefit}. Trade-offs include {tradeoff_1} and {tradeoff_2}. "
            "I would approach this by {approach}, considering factors like {factor_1} and {factor_2}.",

            "From my experience, {topic} involves {aspect_1} and {aspect_2}. "
            "A key principle is {principle}. Best practices include {practice_1}, {practice_2}, and {practice_3}.",
        ],
        "average": [
            "{topic} is used for {purpose}. It involves {vague_concept}. "
            "Some benefits are {generic_benefit}.",

            "I think {topic} helps with {generic_use_case}. "
            "It's similar to {vague_comparison}. Some challenges are {vague_challenge}.",

            "{topic} is important in {domain}. I've worked with it for {duration}. "
            "It has some advantages.",
        ],
        "weak": [
            "{topic} is important.",

            "I've heard of {topic} but don't remember the details.",

            "I'm not very familiar with {topic}. I think it's related to {vague_guess}.",

            "{topic}? That's a good question. I'm not sure.",
        ],
    }

    # Fallback content for placeholders
    PLACEHOLDER_CONTENT = {
        "definition": "a key concept in software development",
        "concept_1": "modularity",
        "concept_2": "scalability",
        "concept_3": "maintainability",
        "example": "in microservices architecture",
        "importance": "it enables better code organization",
        "benefit": "improved performance",
        "tradeoff_1": "increased complexity",
        "tradeoff_2": "higher initial development time",
        "approach": "starting with small iterations",
        "factor_1": "team experience",
        "factor_2": "project constraints",
        "aspect_1": "understanding core principles",
        "aspect_2": "applying best practices",
        "principle": "separation of concerns",
        "practice_1": "thorough testing",
        "practice_2": "code reviews",
        "practice_3": "continuous integration",
        "purpose": "solving common problems",
        "vague_concept": "some technical aspects",
        "generic_benefit": "making things easier",
        "generic_use_case": "general development tasks",
        "vague_comparison": "other similar tools",
        "vague_challenge": "learning curve",
        "domain": "modern software engineering",
        "duration": "some time",
        "vague_guess": "development",
    }

    def generate(
        self,
        question_text: str,
        quality: QualityLevel,
        length_target: int | None = None,
    ) -> str:
        """Generate answer matching quality level.

        Args:
            question_text: The interview question
            quality: Answer quality level (good/average/weak)
            length_target: Target length in chars (optional)

        Returns:
            Generated answer text
        """
        # Extract topic from question
        topic = self._extract_topic(question_text)

        # Select template
        template = random.choice(self.TEMPLATES[quality])

        # Fill template
        answer = self._fill_template(template, topic)

        # Adjust length if needed
        if length_target:
            answer = self._adjust_length(answer, length_target)

        return answer

    def _extract_topic(self, question_text: str) -> str:
        """Extract main topic from question text.

        Args:
            question_text: Question text

        Returns:
            Extracted topic (e.g., "Docker", "async/await")
        """
        # Simple heuristics:
        # - Look for capitalized technical terms
        # - Look for terms in quotes
        # - Fall back to first noun phrase

        # Pattern 1: Technical terms (capitalized, alphanumeric with /)
        technical_terms = re.findall(r'\b[A-Z][a-z]*(?:/[a-z]+)?\b', question_text)
        if technical_terms:
            return technical_terms[0]

        # Pattern 2: Terms in quotes
        quoted = re.findall(r'"([^"]+)"', question_text)
        if quoted:
            return quoted[0]

        # Pattern 3: Terms after "what is", "explain", "describe"
        patterns = [
            r'(?:what is|explain|describe)\s+([A-Za-z/]+)',
            r'(?:how does|how do)\s+([A-Za-z/]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, question_text, re.IGNORECASE)
            if match:
                return match.group(1)

        # Fallback: Generic term
        return "this concept"

    def _fill_template(self, template: str, topic: str) -> str:
        """Fill template with topic and placeholder content.

        Args:
            template: Template string with {placeholders}
            topic: Main topic extracted from question

        Returns:
            Filled template
        """
        # Find all placeholders
        placeholders = re.findall(r'\{(\w+)\}', template)

        # Fill placeholders
        filled = template
        for placeholder in placeholders:
            if placeholder == "topic":
                filled = filled.replace("{topic}", topic)
            else:
                content = self.PLACEHOLDER_CONTENT.get(
                    placeholder,
                    f"[{placeholder}]"
                )
                filled = filled.replace(f"{{{placeholder}}}", content)

        return filled

    def _adjust_length(self, text: str, target: int) -> str:
        """Adjust text to target length.

        Args:
            text: Original text
            target: Target length in characters

        Returns:
            Adjusted text
        """
        current_length = len(text)

        if current_length == target:
            return text
        elif current_length > target:
            # Truncate at sentence boundary
            truncated = text[:target]
            last_period = truncated.rfind('.')
            if last_period > 0:
                return truncated[:last_period + 1]
            return truncated
        else:
            # Pad with additional generic content
            padding = " This is important in many contexts. " * ((target - current_length) // 40 + 1)
            return (text + padding)[:target]


# Helper functions for assertion validation

def is_verbal_question(question_text: str) -> bool:
    """Check if question is verbal (no code/diagram requests).

    Args:
        question_text: Question text

    Returns:
        True if verbal
    """
    code_patterns = [
        r'\bwrite\s+(a\s+)?(function|method|class|code)',
        r'\bimplement\s+(a\s+)?(function|solution|algorithm)',
        r'\bcreate\s+(a\s+)?(class|function|method)',
        r'\bcode\s+(a\s+)?solution',
    ]

    diagram_patterns = [
        r'\bdraw\s+(a\s+)?(diagram|flowchart|chart)',
        r'\bsketch\s+(a\s+)?(diagram|solution)',
        r'\bdiagram\s+(the|a)',
    ]

    whiteboard_patterns = [
        r'\bwhiteboard\s+(exercise|problem|question)',
        r'\bdesign\s+on\s+(the\s+)?whiteboard',
        r'\bshow\s+on\s+(the\s+)?board',
    ]

    all_patterns = code_patterns + diagram_patterns + whiteboard_patterns

    for pattern in all_patterns:
        if re.search(pattern, question_text, re.IGNORECASE):
            return False

    return True


def no_code_writing_questions(questions: list) -> bool:
    """Verify no questions ask for code writing."""
    return all(is_verbal_question(q.text) for q in questions)


def no_diagram_questions(questions: list) -> bool:
    """Verify no questions ask for diagrams."""
    diagram_patterns = [
        r'\bdraw\s+',
        r'\bsketch\s+',
        r'\bdiagram\s+',
        r'\bflowchart\s+',
    ]

    for q in questions:
        for pattern in diagram_patterns:
            if re.search(pattern, q.text, re.IGNORECASE):
                return False

    return True
```

---

## 4. CV Fixtures

**File**: `tests/bot/cv_generator.py` (one-time script to generate PDFs)

```python
"""Generate CV PDF fixtures for testing.

Run once to create CV PDFs:
    python -m tests.bot.cv_generator
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


CV_DATA = {
    "python_senior.pdf": {
        "name": "Alex Chen",
        "title": "Senior Python Developer",
        "email": "alex.chen@example.com",
        "summary": "Experienced Python developer with 5+ years building scalable backend systems.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS", "CI/CD"],
        "experience": [
            {
                "role": "Senior Python Developer",
                "company": "TechCorp Inc.",
                "years": "2020-Present",
                "description": "Built microservices with FastAPI, deployed to AWS ECS.",
            },
            {
                "role": "Backend Engineer",
                "company": "StartupXYZ",
                "years": "2018-2020",
                "description": "Developed REST APIs with Django, optimized PostgreSQL queries.",
            },
        ],
        "education": "B.S. Computer Science, State University (2018)",
    },
    "fullstack_mid.pdf": {
        "name": "Maria Garcia",
        "title": "Full Stack Developer",
        "email": "maria.garcia@example.com",
        "summary": "Full-stack developer with 3 years experience in React and Node.js.",
        "skills": ["React", "Node.js", "MongoDB", "Express", "TypeScript", "GraphQL"],
        "experience": [
            {
                "role": "Full Stack Developer",
                "company": "WebAgency Co.",
                "years": "2021-Present",
                "description": "Built SPAs with React, REST APIs with Node.js/Express.",
            },
        ],
        "education": "B.S. Information Technology, Tech Institute (2021)",
    },
    "backend_junior.pdf": {
        "name": "John Smith",
        "title": "Junior Backend Developer",
        "email": "john.smith@example.com",
        "summary": "Recent graduate with 1 year Java backend development experience.",
        "skills": ["Java", "Spring Boot", "MySQL", "JUnit", "Maven"],
        "experience": [
            {
                "role": "Backend Intern",
                "company": "EnterpriseSoft Ltd.",
                "years": "2023-Present",
                "description": "Developed REST APIs with Spring Boot, wrote unit tests with JUnit.",
            },
        ],
        "education": "B.S. Computer Science, University of Tech (2023)",
    },
    "devops_senior.pdf": {
        "name": "Lisa Nguyen",
        "title": "Senior DevOps Engineer",
        "email": "lisa.nguyen@example.com",
        "summary": "DevOps specialist with 7 years experience in Kubernetes and cloud infrastructure.",
        "skills": ["Kubernetes", "Terraform", "AWS", "Docker", "Jenkins", "Prometheus", "GitOps"],
        "experience": [
            {
                "role": "Senior DevOps Engineer",
                "company": "CloudNative Inc.",
                "years": "2019-Present",
                "description": "Managed K8s clusters, automated deployments with Terraform/ArgoCD.",
            },
            {
                "role": "DevOps Engineer",
                "company": "HostingCorp",
                "years": "2017-2019",
                "description": "Built CI/CD pipelines with Jenkins, containerized apps with Docker.",
            },
        ],
        "education": "B.S. Computer Engineering, Tech University (2017)",
    },
    "frontend_mid.pdf": {
        "name": "David Lee",
        "title": "Frontend Developer",
        "email": "david.lee@example.com",
        "summary": "Frontend developer with 2 years specializing in Vue.js and modern CSS.",
        "skills": ["Vue.js", "TypeScript", "Tailwind CSS", "Vite", "Pinia", "Vitest"],
        "experience": [
            {
                "role": "Frontend Developer",
                "company": "DesignStudio LLC",
                "years": "2022-Present",
                "description": "Built responsive UIs with Vue 3, styled with Tailwind CSS.",
            },
        ],
        "education": "B.S. Web Development, Digital Arts College (2022)",
    },
}


def generate_cv_pdf(filename: str, data: dict, output_dir: Path):
    """Generate CV PDF from data."""
    output_path = output_dir / filename
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Header
    story.append(Paragraph(f"<b>{data['name']}</b>", styles['Title']))
    story.append(Paragraph(data['title'], styles['Heading2']))
    story.append(Paragraph(data['email'], styles['Normal']))
    story.append(Spacer(1, 12))

    # Summary
    story.append(Paragraph("<b>Professional Summary</b>", styles['Heading3']))
    story.append(Paragraph(data['summary'], styles['Normal']))
    story.append(Spacer(1, 12))

    # Skills
    story.append(Paragraph("<b>Technical Skills</b>", styles['Heading3']))
    story.append(Paragraph(", ".join(data['skills']), styles['Normal']))
    story.append(Spacer(1, 12))

    # Experience
    story.append(Paragraph("<b>Work Experience</b>", styles['Heading3']))
    for exp in data['experience']:
        story.append(Paragraph(f"<b>{exp['role']}</b> at {exp['company']}", styles['Heading4']))
        story.append(Paragraph(exp['years'], styles['Normal']))
        story.append(Paragraph(exp['description'], styles['Normal']))
        story.append(Spacer(1, 6))

    # Education
    story.append(Paragraph("<b>Education</b>", styles['Heading3']))
    story.append(Paragraph(data['education'], styles['Normal']))

    # Build PDF
    doc.build(story)
    print(f"Generated {output_path}")


def main():
    """Generate all CV fixtures."""
    output_dir = Path(__file__).parent / "fixtures" / "cvs"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, data in CV_DATA.items():
        generate_cv_pdf(filename, data, output_dir)

    print(f"\nGenerated {len(CV_DATA)} CV PDFs in {output_dir}")


if __name__ == "__main__":
    main()
```

---

## 5. Baseline Metrics

**File**: `tests/bot/fixtures/baselines/baseline_metrics.json`

```json
{
  "version": "v0.3.0",
  "date": "2025-11-21",
  "description": "Performance baselines for regression detection",

  "mock_tests": {
    "avg_duration_sec": 2.1,
    "avg_latency_ms": {
      "connect": 45,
      "send_answer": 12,
      "wait_question": 50,
      "wait_evaluation": 80
    },
    "pass_rate": 1.0,
    "total_cost_usd": 0.0
  },

  "real_tests": {
    "avg_duration_sec": 12.3,
    "avg_cost_usd": 0.09,
    "avg_latency_ms": {
      "connect": 50,
      "send_answer": 15,
      "wait_question": 1200,
      "wait_evaluation": 1500
    },
    "pass_rate": 1.0,
    "cost_breakdown": {
      "cv_analysis": 0.03,
      "question_generation": 0.02,
      "answer_evaluation": 0.025,
      "followup_generation": 0.01,
      "summary_generation": 0.005
    }
  }
}
```

---

## Acceptance Criteria

- [ ] 10 mock scenarios defined in YAML
- [ ] 5 real scenarios defined in YAML
- [ ] 5 CV PDFs generated in `fixtures/cvs/`
- [ ] Answer generator implemented (3 quality levels)
- [ ] Helper functions for assertion validation
- [ ] Baseline metrics JSON created
- [ ] CV generator script tested (PDFs viewable)
- [ ] Answer generator tested (outputs realistic text)

---

## Unresolved Questions

1. **Answer Template Diversity**: 3 templates per quality level enough?
   - **Current**: 3 templates × 3 quality levels = 9 templates
   - **Risk**: Repetitive answers if same template used repeatedly
   - **Mitigation**: Add randomness to placeholder selection

2. **CV Parsing**: Will MockCVAnalyzerAdapter correctly parse generated PDFs?
   - **Test**: Upload generated PDF, verify skill extraction
   - **Fallback**: Manually verify skill extraction in integration test

3. **Assertion Validation Logic**: Where to implement helper functions?
   - **Option A**: In `answer_generator.py` (current)
   - **Option B**: Separate `assertion_helpers.py` module
   - **Decision**: Keep in `answer_generator.py` for MVP

---

## Timeline

**Day 1**:
- AM: Define 10 mock scenarios (YAML)
- PM: Define 5 real scenarios (YAML), create baseline metrics JSON

**Day 2**:
- AM: Implement answer generator + helpers
- PM: Generate CV PDFs, validate fixtures (manual inspection)
