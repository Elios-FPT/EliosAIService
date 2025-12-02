"""Insert all seed data for a fresh database.

This consolidated migration replaces the old 0002/0004–0009 and 0013–0014
data/seed migrations for new environments. It assumes:
- 01 has run successfully
- The database is otherwise empty
"""

from typing import Sequence, Union
from datetime import datetime, timedelta
import uuid
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, Column, MetaData
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime


# revision identifiers, used by Alembic.
revision: str = "02"
down_revision: Union[str, Sequence[str], None] = "01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed questions, CV analyses, interviews/answers/followups and prompts."""

    conn = op.get_bind()
    metadata = MetaData()
    now = datetime.utcnow()

    # ------------------------------------------------------------------
    # Define lightweight table metadata for bulk inserts
    # (only columns that still exist in the final schema are included)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Seed PROMPT TEMPLATES (authoritative subset from production export)
    # ------------------------------------------------------------------

    prompts = [
        {
            "id": uuid.UUID("5606784e-a978-4ec5-90e9-6f62b967c45d"),
            "name": "cv_summary",
            "version": 1,
            "system_prompt": "You are an expert HR professional and technical recruiter analyzing candidate CVs.\nExtract relevant information accurately and professionally.\"\",\"\"variables\"\":[\"\"cv_text\"\"],\"\"constraints\"\":\"\"100-200 words. JSON output. Estimate years_experience if not explicit in CV.",
            "user_template": "Summarize this CV concisely.\n\nCV Text:\n{cv_text}\n\nCreate a professional summary (100-200 words) highlighting:\n- Years of experience (estimate if not explicit)\n- Key technical skills\n- Notable projects or achievements\n- Education background\n\nReturn in JSON format:\n{{\n    \"summary_text\": \"summary here (100-200 words)\",\n    \"years_experience\": 5\n}}",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-22 12:18:46.430461"),
        },
        {
            "id": uuid.UUID("5ee3df2d-22ab-488b-89ea-7fd2dbaecd8c"),
            "name": "answer_evaluation",
            "version": 1,
            "system_prompt": "You are an expert technical interviewer evaluating candidate answers.\nProvide objective, constructive feedback with specific scores.",
            "user_template": "Question: {question_text}\nQuestion Type: {question_type}\nDifficulty: {difficulty}\nExpected Skills: {skills}\n\nCandidate's Answer: {answer_text}\n\n{ideal_answer_section}\n\n{followup_context_section}\n\nEvaluate this answer and provide:\n1. Overall score (0-100)\n2. Completeness score (0-1)\n3. Relevance score (0-1)\n4. Sentiment (confident/uncertain/nervous)\n5. 2-3 strengths\n6. 2-3 weaknesses\n7. 2-3 improvement suggestions\n8. Brief reasoning for the score\n{semantic_similarity_section}\n\nReturn as JSON with keys: score, completeness, relevance, sentiment, strengths, weaknesses, improvements, reasoning{semantic_similarity_key}",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-19 20:09:04.812156"),
        },
        {
            "id": uuid.UUID("82280ebb-2453-4c61-9d25-c922facb23e7"),
            "name": "generate_question_set",
            "version": 1,
            "system_prompt": "You are an expert technical interviewer designing comprehensive interview materials. For each request you must produce well-crafted questions, authoritative ideal answers, and concise rationales explaining why the question itself is valuable. All output must be professional, technically accurate, and follow the requested format exactly.",
            "user_template": "Generate {question_count} interview question sets (question + ideal answer + question rationale) using the context below.\n\nContext:\n- Candidate's background: {summary}\n- Key Skills: {skills}\n- Experience: {experience} years\n\nSpecifications (one per question to generate):\n{questions_section}\n\nInstructions:\n1. Each question must be verbal/discussion-based. Do NOT require coding, diagrams, whiteboards, or visual artifacts.\n2. Ideal answers must be 150-300 words, demonstrate expert understanding, cover key concepts, and include practical examples or scenarios.\n3. Question rationales must be 50-100 words describing why the question is relevant/valuable and what it tests (do not justify the ideal answer).\n4. Ensure the order of outputs matches the order of the specifications above.\n\nReturn ONLY valid JSON in this exact format:\n{{\n  \"question_sets\": [\n    {{\n      \"question_text\": \"string\",\n      \"ideal_answer\": \"string (150-300 words)\",\n      \"question_rationale\": \"string (50-100 words)\"\n    }}\n  ]\n}}",
            "input_variables": [
                "question_count",
                "summary",
                "skills",
                "experience",
                "questions_section",
            ],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {
                "question_sets": [
                    {
                        "rationale": "string",
                        "ideal_answer": "string",
                        "question_text": "string",
                    }
                ]
            },
            "temperature": 0.70,
            "max_tokens": 2000,
            "top_p": 0.90,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "Admin",
            "created_at": datetime.fromisoformat("2025-11-24 08:34:39.996907"),
        },
        {
            "id": uuid.UUID("aca1f921-4d14-47d3-8d3b-3b4e32a236e9"),
            "name": "feedback_report",
            "version": 1,
            "system_prompt": "You are an expert interview coach analyzing candidate performance.\nProvide specific, data-driven recommendations that help candidates improve.",
            "user_template": "Interview Performance Analysis\n\nTotal Questions Answered: {total_answers}\nGap Progression:\n- Questions with Follow-ups: {questions_with_followups}\n- Gaps Filled: {gaps_filled}\n- Gaps Remaining: {gaps_remaining}\n\nDetailed Evaluations:\n{eval_summary}\n\nGenerate personalized interview feedback in JSON format with these exact keys:\n{{\n    \"strengths\": [\"strength 1\", \"strength 2\", ...],  // 3-5 specific strengths\n    \"weaknesses\": [\"weakness 1\", \"weakness 2\", ...],  // 3-5 specific weaknesses\n    \"study_topics\": [\"topic 1\", \"topic 2\", ...],  // 3-7 specific topics to study\n    \"technique_tips\": [\"tip 1\", \"tip 2\", ...]  // 2-5 interview technique improvements\n}}\n\nMake recommendations:\n- Specific and actionable (not generic)\n- Based on actual performance data\n- Prioritized by impact\n- Constructive and encouraging\n\nReturn ONLY valid JSON.",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-19 20:09:04.812156"),
        },
        {
            "id": uuid.UUID("b4276be2-e4f2-4915-9cd0-4df5fa1ef775"),
            "name": "gap_detection",
            "version": 1,
            "system_prompt": "You are an expert technical interviewer analyzing completeness.\nIdentify real conceptual gaps, not just missing synonyms.",
            "user_template": "Question: {question_text}\nIdeal Answer: {ideal_answer}\nCandidate Answer: {answer_text}\nPotential missing keywords: {keyword_gaps}\n\nAnalyze and identify:\n1. Key concepts in ideal answer missing from candidate answer\n2. Whether missing keywords represent real conceptual gaps\n\nReturn as JSON:\n- \"concepts\": list of missing concepts\n- \"confirmed\": boolean\n- \"severity\": \"minor\" | \"moderate\" | \"major\"",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": False,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-19 20:09:04.812156"),
        },
        {
            "id": uuid.UUID("bd4e41ce-14ab-4a8c-aab6-f749059e65b7"),
            "name": "follow_up_generation",
            "version": 1,
            "system_prompt": "You are an expert technical interviewer generating adaptive follow-ups.\nAsk questions that probe specific missing concepts while considering the full interview context.",
            "user_template": "Original Question: {parent_question}\nLatest Answer: {answer_text}\nCurrent Missing Concepts: {missing_concepts}\nGap Severity: {severity}\n{cumulative_context}\n{previous_context}\n\nGenerate focused follow-up question (#{order}) addressing the most critical missing concepts.\nThe question should:\n- Be specific and concise\n- Prioritize concepts: {priority_concepts}\n- Avoid repeating previous follow-up questions\n- Be progressively more targeted (this is follow-up #{order} of max 3)\n\nReturn only the question text.",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-19 20:09:04.812156"),
        },
        {
            "id": uuid.UUID("caa9e01b-1d98-496d-8864-2d154361d83d"),
            "name": "interview_recommendations",
            "version": 1,
            "system_prompt": "You are an expert technical interviewer evaluating candidate answers.\nProvide fair, constructive feedback focusing on technical accuracy, depth, and communication.",
            "user_template": "Generate personalized interview recommendations.\n\nInterview Context:\n- Interview ID: {interview_id}\n- Total Answers: {total_answers}\n- Gap Progression: {gap_progression}\n- Evaluations: {evaluations}\n\nProvide:\n1. Top 3-5 strengths demonstrated\n2. Top 3-5 weaknesses to address\n3. Specific study topics (be concrete)\n4. Interview technique tips (voice, pacing, structure)\n\nReturn in JSON format:\n{{\n    \"strengths\": [\"strength 1\", \"strength 2\", ...],\n    \"weaknesses\": [\"weakness 1\", \"weakness 2\", ...],\n    \"study_topics\": [\"topic 1\", \"topic 2\", ...],\n    \"technique_tips\": [\"tip 1\", \"tip 2\", ...]\n}}",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-22 12:18:46.430461"),
        },
        {
            "id": uuid.UUID("f0a71774-6007-40c5-a53f-183cebe8fb26"),
            "name": "skill_extraction",
            "version": 1,
            "system_prompt": "You are an expert HR professional and technical recruiter analyzing candidate CVs.\nExtract relevant information accurately and professionally.",
            "user_template": "Extract technical skills from this text.\n\nText:\n{text}\n\nIdentify:\n- Programming languages\n- Frameworks and libraries\n- Databases and tools\n- Methodologies and practices\n\nFor each skill, provide:\n- name: skill name\n- category: type of skill (e.g., \"programming\", \"framework\", \"database\")\n- proficiency: level if mentioned (e.g., \"beginner\", \"intermediate\", \"expert\")\n\nReturn in JSON format:\n{{\n    \"skills\": [\n        {{\"name\": \"Python\", \"category\": \"programming\", \"proficiency\": \"expert\"}},\n        {{\"name\": \"FastAPI\", \"category\": \"framework\", \"proficiency\": \"intermediate\"}}\n    ]\n}}",
            "input_variables": [],
            "partial_variables": {},
            "output_parser_type": "json_output_parser",
            "output_schema": {},
            "temperature": 0.30,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "created_at": datetime.fromisoformat("2025-11-22 12:18:46.430461"),
        },
    ]

    # Insert prompts using decomposed schema; template_json will be filled
    # automatically by the trigger from 01.
    prompt_rows = []
    for p in prompts:
        prompt_rows.append(
            {
                "id": p["id"],
                "name": p["name"],
                "version": p["version"],
                "system_prompt": p["system_prompt"],
                "user_template": p["user_template"],
                "input_variables": p["input_variables"],
                "partial_variables": p.get("partial_variables", {}),
                "output_parser_type": p["output_parser_type"],
                "output_schema": p.get("output_schema", {}),
                "temperature": p["temperature"],
                "max_tokens": p["max_tokens"],
                "top_p": p["top_p"],
                "frequency_penalty": p["frequency_penalty"],
                "presence_penalty": p["presence_penalty"],
                "is_active": p["is_active"],
                "is_draft": p["is_draft"],
                "created_at": p["created_at"],
                "created_by": p["created_by"],
                "template_json": None,
            }
        )

    if prompt_rows:
        op.bulk_insert(prompt_templates_table, prompt_rows)


def downgrade() -> None:
    """Remove seeded data.

    This keeps the schema but deletes records inserted by this migration.
    """

    conn = op.get_bind()

    # Delete prompts seeded by this migration (match by UUIDs for safety)
    conn.execute(
        sa.text(
            """
            DELETE FROM prompt_templates
            WHERE id IN (
                '5606784e-a978-4ec5-90e9-6f62b967c45d',
                '5ee3df2d-22ab-488b-89ea-7fd2dbaecd8c',
                '82280ebb-2453-4c61-9d25-c922facb23e7',
                'aca1f921-4d14-47d3-8d3b-3b4e32a236e9',
                'b4276be2-e4f2-4915-9cd0-4df5fa1ef775',
                'bd4e41ce-14ab-4a8c-aab6-f749059e65b7',
                'caa9e01b-1d98-496d-8864-2d154361d83d',
                'f0a71774-6007-40c5-a53f-183cebe8fb26'
            )
            """
        )
    )