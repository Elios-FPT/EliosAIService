"""Add cv_skill_extraction prompt template.

This migration adds a prompt for extracting technical skills from CVs
using LLM with structured output. Used by LangChainAdapter.analyze_cv_for_skills().

Revision ID: 21
Revises: 20
Create Date: 2025-12-17
"""

from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, Column, MetaData
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy import String, Text, Integer, Boolean, DateTime


# revision identifiers, used by Alembic.
revision: str = "21"
down_revision: Union[str, Sequence[str], None] = "20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cv_skill_extraction prompt template."""

    conn = op.get_bind()
    metadata = MetaData()
    now = datetime.utcnow()

    # Define PromptTemplates table structure
    # Note: Some columns (name, version, temperature) remain lowercase per actual schema
    prompt_templates_table = Table(
        "PromptTemplates",
        metadata,
        Column("Id", UUID(as_uuid=True)),
        Column("name", String),  # lowercase per actual schema
        Column("version", Integer),  # lowercase per actual schema
        Column("SystemPrompt", Text),
        Column("UserTemplate", Text),
        Column("InputVariables", ARRAY(String)),
        Column("PartialVariables", JSONB),
        Column("OutputSchema", JSONB),
        Column("temperature", sa.Numeric(3, 2)),  # lowercase per actual schema
        Column("MaxTokens", Integer),
        Column("TopP", sa.Numeric(3, 2)),
        Column("FrequencyPenalty", sa.Numeric(3, 2)),
        Column("PresencePenalty", sa.Numeric(3, 2)),
        Column("IsActive", Boolean),
        Column("IsDraft", Boolean),
        Column("CreatedAt", DateTime),
        Column("CreatedBy", String),
    )

    cv_skill_extraction_prompt = {
        "Id": uuid.UUID("c3d4e5f6-a7b8-9012-3456-7890abcdef12"),
        "name": "cv_skill_extraction",  # lowercase per actual schema
        "version": 1,  # lowercase per actual schema
        "SystemPrompt": """You are a technical skill extraction expert. Your task is to extract ONLY technical skills relevant for interview question generation from CVs.

RULES:
1. Focus on technical skills: programming languages, frameworks, libraries, tools, databases, cloud platforms, methodologies (Agile, DevOps, etc.)
2. Infer proficiency level from context:
   - beginner: mentioned but limited experience (<1 year, learning projects)
   - intermediate: working knowledge (1-3 years, production use)
   - advanced: strong expertise (3-5 years, lead roles)
   - expert: deep expertise (5+ years, architecture decisions)
3. Mark top 3-5 most prominent skills as is_primary=true
4. Estimate years_of_experience from CV context (job durations, project complexity)
5. Generate a 2-3 sentence summary focusing ONLY on technical capabilities
6. NEVER include personal information (name, email, phone, location, age)
7. Do NOT hallucinate skills not mentioned or implied in the CV
8. If a skill is mentioned but proficiency unclear, default to intermediate

OUTPUT QUALITY:
- Be conservative: only extract skills clearly mentioned or strongly implied
- Prefer specific over generic (e.g., "FastAPI" over "web frameworks")
- Include methodologies and soft technical skills (Agile, CI/CD, TDD)""",

        "UserTemplate": """Extract technical skills and summary from this CV:

{cv_text}

Return a structured response with:
1. skills: Array of technical skills with:
   - skill_name: Specific skill name
   - proficiency_level: beginner/intermediate/advanced/expert
   - years_of_experience: Estimated years (null if unknown)
   - is_primary: true for top 3-5 core skills
2. summary: 2-3 sentence summary of technical capabilities (no personal info)

Focus on skills relevant for technical interview question generation.""",

        "InputVariables": ["cv_text"],
        "PartialVariables": {},
        "OutputSchema": {
            "type": "object",
            "properties": {
                "skills": {
                    "type": "array",
                    "maxItems": 30,
                    "items": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "maxLength": 100
                            },
                            "proficiency_level": {
                                "type": "string",
                                "enum": ["beginner", "intermediate", "advanced", "expert"]
                            },
                            "years_of_experience": {
                                "type": ["number", "null"],
                                "minimum": 0,
                                "maximum": 50
                            },
                            "is_primary": {
                                "type": "boolean"
                            }
                        },
                        "required": ["skill_name", "proficiency_level", "is_primary"]
                    }
                },
                "summary": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 500
                }
            },
            "required": ["skills", "summary"]
        },
        "temperature": 0.3,  # Lower for extraction consistency (lowercase per actual schema)
        "MaxTokens": 2000,
        "TopP": 0.95,
        "FrequencyPenalty": 0.0,
        "PresencePenalty": 0.0,
        "IsActive": True,
        "IsDraft": False,
        "CreatedBy": "system",
        "CreatedAt": now,
    }

    op.bulk_insert(prompt_templates_table, [cv_skill_extraction_prompt])


def downgrade() -> None:
    """Remove cv_skill_extraction prompt."""

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM "PromptTemplates"
            WHERE "Id" = 'c3d4e5f6-a7b8-9012-3456-7890abcdef12'::uuid
            """
        )
    )
