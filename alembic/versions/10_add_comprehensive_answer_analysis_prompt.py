"""Add comprehensive_answer_analysis prompt (Phase 2: Unified LLM Prompt).

This migration seeds the comprehensive_answer_analysis prompt template
that consolidates 3 LLM calls (evaluate_answer + detect_gaps + follow_up)
into 1 unified call for 46% latency reduction.
"""

from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, Column, MetaData
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime


# revision identifiers, used by Alembic.
revision: str = "10"
down_revision: Union[str, Sequence[str], None] = "09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add comprehensive_answer_analysis prompt template."""

    conn = op.get_bind()
    metadata = MetaData()
    now = datetime.utcnow()

    # Define prompt_templates table structure
    prompt_templates_table = Table(
        "prompt_templates",
        metadata,
        Column("id", UUID(as_uuid=True)),
        Column("name", String),
        Column("version", Integer),
        Column("system_prompt", Text),
        Column("user_template", Text),
        Column("input_variables", ARRAY(String)),
        Column("partial_variables", JSONB),
        Column("output_parser_type", String),
        Column("output_schema", JSONB),
        Column("temperature", sa.Numeric(3, 2)),
        Column("max_tokens", Integer),
        Column("top_p", sa.Numeric(3, 2)),
        Column("frequency_penalty", sa.Numeric(3, 2)),
        Column("presence_penalty", sa.Numeric(3, 2)),
        Column("is_active", Boolean),
        Column("is_draft", Boolean),
        Column("created_at", DateTime),
        Column("created_by", String),
        Column("template_json", JSONB),
    )

    # Comprehensive Answer Analysis prompt (Phase 2)
    comprehensive_prompt = {
        "id": uuid.UUID("3b41977c-99b0-4d84-855b-a09722e9eea0"),
        "name": "comprehensive_answer_analysis",
        "version": 1,
        "system_prompt": """You are an expert technical interviewer. Analyze candidate answers comprehensively using step-by-step reasoning.

CRITICAL: Evaluate each answer independently based on its actual quality. Do not anchor to example scores or default values. Use the full scoring range for each dimension based on merit.

Provide analysis in THREE PARTS:
1. EVALUATION: Multi-dimensional scoring (technical accuracy, depth, clarity, practical application)
2. GAP DETECTION: Identify missing concepts with severity ratings
3. FOLLOW-UP DECISION: Suggest follow-up question if major gaps exist and attempt < 3

Use chain-of-thought reasoning for quality multi-task analysis.""",
        "user_template": """Analyze this answer comprehensively.

QUESTION: {question_text}
IDEAL ANSWER: {ideal_answer}
CANDIDATE'S ANSWER: {answer_text}

CONTEXT:
- Attempt number: {attempt_number}
- Previous scores: {previous_scores}
- Cumulative gaps: {cumulative_gaps}

**PART 1: EVALUATION**
Evaluate answer on 4 dimensions:
- Technical accuracy (0-40 points): Correctness of concepts and implementation details
- Depth of understanding (0-30 points): Level of detail and comprehension shown
- Clarity of communication (0-20 points): Structure, coherence, and articulation
- Practical application (0-10 points): Real-world relevance and examples

For each dimension, provide score + reasoning.
Calculate total score (0-100).

**PART 2: GAP DETECTION**
Compare answer to ideal answer. Identify missing concepts or incomplete explanations.
For each gap, rate severity:
- "minor": Nice-to-know details, doesn't affect core understanding
- "moderate": Important concepts that should be mentioned
- "major": Critical concepts essential for complete answer

**PART 3: FOLLOW-UP DECISION**
Conditions for follow-up:
- If major gaps exist AND attempt < 3: Suggest ONE follow-up question to probe deeper
- If no major gaps OR attempt == 3: Return null for follow_up

Return valid JSON with all three parts.

CRITICAL: Evaluate each answer independently. Base scores on actual answer quality, not on examples. Use the full scoring range (0 to max) for each dimension based on merit.

JSON structure:
{{
    "evaluation": {{
        "dimensions": [
            {{"dimension_name": "technical_accuracy", "score": <number 0-40>, "reasoning": "evaluate correctness of concepts and implementation"}},
            {{"dimension_name": "depth_of_understanding", "score": <number 0-30>, "reasoning": "evaluate level of detail and comprehension"}},
            {{"dimension_name": "clarity_of_communication", "score": <number 0-20>, "reasoning": "evaluate structure, coherence, and articulation"}},
            {{"dimension_name": "practical_application", "score": <number 0-10>, "reasoning": "evaluate real-world relevance and examples"}}
        ],
        "total_score": <number 0-100, sum of dimension scores>,
        "strengths": ["list specific strengths found in answer"],
        "weaknesses": ["list specific weaknesses found in answer"],
        "improvement_suggestions": ["list actionable improvement suggestions"],
        "reasoning": "overall evaluation summary"
    }},
    "gaps": [
        {{"concept": "name of missing concept", "severity": "minor|moderate|major", "explanation": "explain why this is a gap"}}
    ],
    "follow_up": {{
        "question_text": "<follow-up question string> or null",
        "reason": "<reason for follow-up> or null",
        "target_gaps": ["list gap concepts this follow-up addresses"]
    }},
    "confidence": <number 0.0-1.0>
}}""",
        "input_variables": [
            "question_text",
            "ideal_answer",
            "answer_text",
            "attempt_number",
            "previous_scores",
            "cumulative_gaps",
        ],
        "partial_variables": {},
        "output_parser_type": "json_output_parser",
        "output_schema": {
            "type": "object",
            "properties": {
                "evaluation": {
                    "type": "object",
                    "properties": {
                        "dimensions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dimension_name": {"type": "string"},
                                    "score": {"type": "number"},
                                    "reasoning": {"type": "string"},
                                },
                            },
                        },
                        "total_score": {"type": "number"},
                        "strengths": {"type": "array", "items": {"type": "string"}},
                        "weaknesses": {"type": "array", "items": {"type": "string"}},
                        "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
                        "reasoning": {"type": "string"},
                    },
                },
                "gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "concept": {"type": "string"},
                            "severity": {"type": "string", "enum": ["minor", "moderate", "major"]},
                            "explanation": {"type": "string"},
                        },
                    },
                },
                "follow_up": {
                    "type": "object",
                    "properties": {
                        "question_text": {"type": ["string", "null"]},
                        "reason": {"type": ["string", "null"]},
                        "target_gaps": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "confidence": {"type": "number"},
            },
        },
        "temperature": 0.45,  # Lower for multi-task determinism (Phase 2 requirement)
        "max_tokens": 1000,  # Increased from 800 for comprehensive output
        "top_p": 0.95,
        "frequency_penalty": 0.00,
        "presence_penalty": 0.00,
        "is_active": True,
        "is_draft": False,
        "created_by": "system",
        "created_at": now,
    }

    # Insert prompt
    prompt_row = {
        "id": comprehensive_prompt["id"],
        "name": comprehensive_prompt["name"],
        "version": comprehensive_prompt["version"],
        "system_prompt": comprehensive_prompt["system_prompt"],
        "user_template": comprehensive_prompt["user_template"],
        "input_variables": comprehensive_prompt["input_variables"],
        "partial_variables": comprehensive_prompt["partial_variables"],
        "output_parser_type": comprehensive_prompt["output_parser_type"],
        "output_schema": comprehensive_prompt["output_schema"],
        "temperature": comprehensive_prompt["temperature"],
        "max_tokens": comprehensive_prompt["max_tokens"],
        "top_p": comprehensive_prompt["top_p"],
        "frequency_penalty": comprehensive_prompt["frequency_penalty"],
        "presence_penalty": comprehensive_prompt["presence_penalty"],
        "is_active": comprehensive_prompt["is_active"],
        "is_draft": comprehensive_prompt["is_draft"],
        "created_at": comprehensive_prompt["created_at"],
        "created_by": comprehensive_prompt["created_by"],
        "template_json": None,  # Will be filled by trigger
    }

    op.bulk_insert(prompt_templates_table, [prompt_row])


def downgrade() -> None:
    """Remove comprehensive_answer_analysis prompt."""

    conn = op.get_bind()

    # Delete prompt by UUID
    conn.execute(
        sa.text(
            """
            DELETE FROM prompt_templates
            WHERE id = '3b41977c-99b0-4d84-855b-a09722e9eea0'
            """
        )
    )

