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
        technical_terms = re.findall(r"\b[A-Z][a-z]*(?:/[a-z]+)?\b", question_text)
        if technical_terms:
            return technical_terms[0]

        # Pattern 2: Terms in quotes
        quoted = re.findall(r'"([^"]+)"', question_text)
        if quoted:
            return quoted[0]

        # Pattern 3: Terms after "what is", "explain", "describe"
        patterns = [
            r"(?:what is|explain|describe)\s+([A-Za-z/]+)",
            r"(?:how does|how do)\s+([A-Za-z/]+)",
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
        placeholders = re.findall(r"\{(\w+)\}", template)

        # Fill placeholders
        filled = template
        for placeholder in placeholders:
            if placeholder == "topic":
                filled = filled.replace("{topic}", topic)
            else:
                content = self.PLACEHOLDER_CONTENT.get(placeholder, f"[{placeholder}]")
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
            last_period = truncated.rfind(".")
            if last_period > 0:
                return truncated[: last_period + 1]
            return truncated
        else:
            # Pad with additional generic content
            padding = " This is important in many contexts. " * (
                (target - current_length) // 40 + 1
            )
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
        r"\bwrite\s+(a\s+)?(function|method|class|code)",
        r"\bimplement\s+(a\s+)?(function|solution|algorithm)",
        r"\bcreate\s+(a\s+)?(class|function|method)",
        r"\bcode\s+(a\s+)?solution",
    ]

    diagram_patterns = [
        r"\bdraw\s+(a\s+)?(diagram|flowchart|chart)",
        r"\bsketch\s+(a\s+)?(diagram|solution)",
        r"\bdiagram\s+(the|a)",
    ]

    whiteboard_patterns = [
        r"\bwhiteboard\s+(exercise|problem|question)",
        r"\bdesign\s+on\s+(the\s+)?whiteboard",
        r"\bshow\s+on\s+(the\s+)?board",
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
        r"\bdraw\s+",
        r"\bsketch\s+",
        r"\bdiagram\s+",
        r"\bflowchart\s+",
    ]

    for q in questions:
        for pattern in diagram_patterns:
            if re.search(pattern, q.text, re.IGNORECASE):
                return False

    return True
