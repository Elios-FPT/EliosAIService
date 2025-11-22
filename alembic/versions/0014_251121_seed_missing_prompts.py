"""seed missing prompts for LangChain adapter

Revision ID: 0014_251121_seed_missing_prompts
Revises: 0013_251120_seed_initial_prompts
Create Date: 2025-11-21

Seeds 3 prompts required for complete LangChainAdapter DB migration:
- cv_summary (SUMMARIZE_CV_PROMPT)
- skill_extraction (EXTRACT_SKILLS_PROMPT)
- interview_recommendations (RECOMMENDATIONS_PROMPT)
"""

import json

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed 3 missing prompt templates."""

    prompts = [
        {
            "name": "cv_summary",
            "version": 1,
            "template_json": json.dumps(
                {
                    "system": "You are an expert HR professional and technical recruiter analyzing candidate CVs.\nExtract relevant information accurately and professionally.",
                    "user_template": """Summarize this CV concisely.

CV Text:
{cv_text}

Create a professional summary (100-200 words) highlighting:
- Years of experience (estimate if not explicit)
- Key technical skills
- Notable projects or achievements
- Education background

Return in JSON format:
{{
    "summary_text": "summary here (100-200 words)",
    "years_experience": 5
}}""",
                    "variables": ["cv_text"],
                    "constraints": "100-200 words. JSON output. Estimate years_experience if not explicit in CV.",
                }
            ),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Migrated from SUMMARIZE_CV_PROMPT in prompts/__init__.py",
        },
        {
            "name": "skill_extraction",
            "version": 1,
            "template_json": json.dumps(
                {
                    "system": "You are an expert HR professional and technical recruiter analyzing candidate CVs.\nExtract relevant information accurately and professionally.",
                    "user_template": """Extract technical skills from this text.

Text:
{text}

Identify:
- Programming languages
- Frameworks and libraries
- Databases and tools
- Methodologies and practices

For each skill, provide:
- name: skill name
- category: type of skill (e.g., "programming", "framework", "database")
- proficiency: level if mentioned (e.g., "beginner", "intermediate", "expert")

Return in JSON format:
{{
    "skills": [
        {{"name": "Python", "category": "programming", "proficiency": "expert"}},
        {{"name": "FastAPI", "category": "framework", "proficiency": "intermediate"}}
    ]
}}""",
                    "variables": ["text"],
                    "constraints": "JSON output. Extract all technical skills mentioned. Infer proficiency from context (years, project complexity).",
                }
            ),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Migrated from EXTRACT_SKILLS_PROMPT in prompts/__init__.py",
        },
        {
            "name": "interview_recommendations",
            "version": 1,
            "template_json": json.dumps(
                {
                    "system": "You are an expert technical interviewer evaluating candidate answers.\nProvide fair, constructive feedback focusing on technical accuracy, depth, and communication.",
                    "user_template": """Generate personalized interview recommendations.

Interview Context:
- Interview ID: {interview_id}
- Total Answers: {total_answers}
- Gap Progression: {gap_progression}
- Evaluations: {evaluations}

Provide:
1. Top 3-5 strengths demonstrated
2. Top 3-5 weaknesses to address
3. Specific study topics (be concrete)
4. Interview technique tips (voice, pacing, structure)

Return in JSON format:
{{
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "study_topics": ["topic 1", "topic 2", ...],
    "technique_tips": ["tip 1", "tip 2", ...]
}}""",
                    "variables": [
                        "interview_id",
                        "total_answers",
                        "gap_progression",
                        "evaluations",
                    ],
                    "constraints": "JSON output. 3-5 strengths/weaknesses, 3-7 study topics, 2-5 technique tips. Be specific (not generic advice).",
                }
            ),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Migrated from RECOMMENDATIONS_PROMPT in prompts/__init__.py",
        },
    ]

    # Get database connection
    connection = op.get_bind()

    # Insert prompts
    for prompt in prompts:
        connection.execute(
            sa.text(
                """
                INSERT INTO prompt_templates
                (name, version, template_json, is_active, is_draft, created_by, notes)
                VALUES
                (:name, :version, CAST(:template_json AS jsonb), :is_active, :is_draft, :created_by, :notes)
            """
            ),
            {
                "name": prompt["name"],
                "version": prompt["version"],
                "template_json": prompt["template_json"],
                "is_active": prompt["is_active"],
                "is_draft": prompt["is_draft"],
                "created_by": prompt["created_by"],
                "notes": prompt["notes"],
            },
        )


def downgrade() -> None:
    """Remove seeded prompt templates."""

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM prompt_templates
            WHERE created_by = 'system'
            AND version = 1
            AND name IN (
                'cv_summary',
                'skill_extraction',
                'interview_recommendations'
            )
        """
        )
    )
