"""seed initial prompts

Revision ID: 0013_251120_seed_initial_prompts
Revises: 0012_251120_create_prompt_analytics_view
Create Date: 2025-11-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json

# revision identifiers, used by Alembic.
revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed initial prompt templates extracted from openai_adapter.py."""

    # Define initial prompts
    prompts = [
        {
            "name": "question_generation",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer.\nGenerate clear, relevant interview questions based on the context provided.",
                "user_template": """Generate {question_count} interview questions based on the following specifications:

Context:
- Candidate's background: {summary}
- Key Skills: {skills}
- Experience: {experience} years

{questions_section}

**IMPORTANT CONSTRAINTS**:
The questions MUST be verbal/discussion-based. DO NOT generate questions that require:
- Writing code ("write a function", "implement", "create a class", "code a solution")
- Drawing diagrams ("draw", "sketch", "diagram", "visualize", "map out")
- Whiteboard exercises ("design on whiteboard", "show on board", "illustrate")
- Visual outputs ("create a flowchart", "design a schema visually")

Focus on conceptual understanding, best practices, trade-offs, and problem-solving approaches that can be explained verbally.

Return as JSON with this exact format:
{{
    "questions": ["question 1 text", "question 2 text", ...]
}}

The questions array must contain exactly {question_count} questions in the same order as the specifications above.""",
                "variables": ["question_count", "summary", "skills", "experience", "questions_section"],
                "constraints": "VERBAL ONLY - no code/diagrams/whiteboard. Focus on conceptual understanding."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - batch question generation"
        },
        {
            "name": "answer_evaluation",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer evaluating candidate answers.\nProvide objective, constructive feedback with specific scores.",
                "user_template": """Question: {question_text}
Question Type: {question_type}
Difficulty: {difficulty}
Expected Skills: {skills}

Candidate's Answer: {answer_text}

{ideal_answer_section}

{followup_context_section}

Evaluate this answer and provide:
1. Overall score (0-100)
2. Completeness score (0-1)
3. Relevance score (0-1)
4. Sentiment (confident/uncertain/nervous)
5. 2-3 strengths
6. 2-3 weaknesses
7. 2-3 improvement suggestions
8. Brief reasoning for the score
{semantic_similarity_section}

Return as JSON with keys: score, completeness, relevance, sentiment, strengths, weaknesses, improvements, reasoning{semantic_similarity_key}""",
                "variables": ["question_text", "question_type", "difficulty", "skills", "answer_text", "ideal_answer_section", "followup_context_section", "semantic_similarity_section", "semantic_similarity_key"],
                "constraints": "Use JSON mode. Temperature: 0.3 for consistency. Include semantic_similarity (0.0-1.0) if ideal_answer exists."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - answer evaluation with follow-up support"
        },
        {
            "name": "ideal_answer_generation",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer creating reference answers.\nGenerate comprehensive, technically accurate ideal answers.",
                "user_template": """Question: {question_text}

Candidate Background:
- Summary: {summary}
- Key Skills: {key_skills}
- Experience: {experience} years

Generate an ideal answer for this interview question. The answer should:
- Be 150-300 words
- Demonstrate expert-level understanding
- Cover key concepts comprehensively
- Include practical examples if relevant
- Be technically accurate

Output only the ideal answer text.""",
                "variables": ["question_text", "summary", "key_skills", "experience"],
                "constraints": "150-300 words. Temperature: 0.3 for consistency. Max tokens: 500."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - single ideal answer generation"
        },
        {
            "name": "rationale_generation",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer explaining evaluation criteria.\nExplain why an answer demonstrates mastery.",
                "user_template": """Question: {question_text}
Ideal Answer: {ideal_answer}

Explain WHY this is an ideal answer in 50-100 words. Focus on:
- What key concepts are covered
- Why this demonstrates mastery
- What would be missing in a weaker answer

Output only the rationale text.""",
                "variables": ["question_text", "ideal_answer"],
                "constraints": "50-100 words. Temperature: 0.3. Max tokens: 200. Use gpt-3.5-turbo for cost savings."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - rationale generation"
        },
        {
            "name": "gap_detection",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer analyzing completeness.\nIdentify real conceptual gaps, not just missing synonyms.",
                "user_template": """Question: {question_text}
Ideal Answer: {ideal_answer}
Candidate Answer: {answer_text}
Potential missing keywords: {keyword_gaps}

Analyze and identify:
1. Key concepts in ideal answer missing from candidate answer
2. Whether missing keywords represent real conceptual gaps

Return as JSON:
- "concepts": list of missing concepts
- "confirmed": boolean
- "severity": "minor" | "moderate" | "major" """,
                "variables": ["question_text", "ideal_answer", "answer_text", "keyword_gaps"],
                "constraints": "Use JSON mode. Temperature: 0.3. Use gpt-3.5-turbo for cost."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - concept gap detection"
        },
        {
            "name": "follow_up_generation",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer generating adaptive follow-ups.\nAsk questions that probe specific missing concepts while considering the full interview context.",
                "user_template": """Original Question: {parent_question}
Latest Answer: {answer_text}
Current Missing Concepts: {missing_concepts}
Gap Severity: {severity}
{cumulative_context}
{previous_context}

Generate focused follow-up question (#{order}) addressing the most critical missing concepts.
The question should:
- Be specific and concise
- Prioritize concepts: {priority_concepts}
- Avoid repeating previous follow-up questions
- Be progressively more targeted (this is follow-up #{order} of max 3)

Return only the question text.""",
                "variables": ["parent_question", "answer_text", "missing_concepts", "severity", "cumulative_context", "previous_context", "order", "priority_concepts"],
                "constraints": "Temperature: 0.4. Max tokens: 150. Use gpt-3.5-turbo. Concise output."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - adaptive follow-up questions with cumulative context"
        },
        {
            "name": "feedback_report",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert interview coach analyzing candidate performance.\nProvide specific, data-driven recommendations that help candidates improve.",
                "user_template": """Interview Performance Analysis

Total Questions Answered: {total_answers}
Gap Progression:
- Questions with Follow-ups: {questions_with_followups}
- Gaps Filled: {gaps_filled}
- Gaps Remaining: {gaps_remaining}

Detailed Evaluations:
{eval_summary}

Generate personalized interview feedback in JSON format with these exact keys:
{{
    "strengths": ["strength 1", "strength 2", ...],  // 3-5 specific strengths
    "weaknesses": ["weakness 1", "weakness 2", ...],  // 3-5 specific weaknesses
    "study_topics": ["topic 1", "topic 2", ...],  // 3-7 specific topics to study
    "technique_tips": ["tip 1", "tip 2", ...]  // 2-5 interview technique improvements
}}

Make recommendations:
- Specific and actionable (not generic)
- Based on actual performance data
- Prioritized by impact
- Constructive and encouraging

Return ONLY valid JSON.""",
                "variables": ["total_answers", "questions_with_followups", "gaps_filled", "gaps_remaining", "eval_summary"],
                "constraints": "Use JSON mode. Temperature: 0.7. Max tokens: 800. Use gpt-3.5-turbo."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py - comprehensive feedback report generation"
        }
    ]

    # Get table reference
    connection = op.get_bind()

    # Insert prompts
    for prompt in prompts:
        connection.execute(
            sa.text("""
                INSERT INTO prompt_templates
                (name, version, template_json, is_active, is_draft, created_by, notes)
                VALUES
                (:name, :version, CAST(:template_json AS jsonb), :is_active, :is_draft, :created_by, :notes)
            """),
            {
                "name": prompt["name"],
                "version": prompt["version"],
                "template_json": prompt["template_json"],
                "is_active": prompt["is_active"],
                "is_draft": prompt["is_draft"],
                "created_by": prompt["created_by"],
                "notes": prompt["notes"]
            }
        )


def downgrade() -> None:
    """Remove seeded prompt templates."""

    connection = op.get_bind()
    connection.execute(
        sa.text("""
            DELETE FROM prompt_templates
            WHERE created_by = 'system'
            AND version = 1
            AND name IN (
                'question_generation',
                'answer_evaluation',
                'ideal_answer_generation',
                'rationale_generation',
                'gap_detection',
                'follow_up_generation',
                'feedback_report'
            )
        """)
    )
