"""Add cv_feedback and code_solution_feedback prompt templates.

This migration seeds:
1. cv_feedback prompt template for analyzing candidate CVs and providing
   comprehensive feedback on structure, content, and market competitiveness.
2. code_solution_feedback prompt template for reviewing code solutions and
   providing feedback on code quality, best practices, and actionable improvements.
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
revision: str = "15"
down_revision: Union[str, Sequence[str], None] = "14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cv_feedback and code_solution_feedback prompt templates."""

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
    )

    # CV Feedback prompt
    cv_feedback_prompt = {
        "id": uuid.UUID("a1b2c3d4-e5f6-7890-1234-567890abcdef"),
        "name": "cv_feedback",
        "version": 1,
        "system_prompt": """You are an expert career coach and technical recruiter with 10+ years of experience reviewing software engineering resumes. Your role is to provide constructive, actionable feedback that helps candidates improve their CVs and increase their chances of landing interviews.

Provide honest, professional feedback that balances encouragement with actionable improvements. Focus on:
- Technical accuracy and relevance
- Clarity and presentation
- Industry best practices
- ATS (Applicant Tracking System) optimization
- Market competitiveness

Be specific, constructive, and prioritize feedback by impact.""",
        "user_template": """Analyze this candidate's CV and provide comprehensive feedback.

CV Data:
{cv_data}

Provide detailed feedback covering the following areas:

1. **Overall Assessment** (overall score and summary)
2. **Professional Summary/Title** (clarity, relevance, impact of job title)
3. **Work Experience** (format, achievements, relevance, quantification)
4. **Projects** (description quality, tech stack presentation, achievements, links)
5. **Skills Section** (organization, relevance, proficiency levels, missing skills)
6. **Actionable Recommendations** (prioritized improvements)
7. **Market Competitiveness** (assessment and target roles)

Return feedback in JSON format:
{{
    "overall_assessment": {{
        "overall_score": <number 0-100>,
        "summary": "2-3 sentence overall assessment"
    }},
    "professional_summary": {{
        "score": <number 0-15>,
        "feedback": "feedback on job title and professional positioning",
        "suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "work_experience": {{
        "score": <number 0-25>,
        "feedback": "feedback on work experience section",
        "suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "projects": {{
        "score": <number 0-25>,
        "feedback": "feedback on projects section",
        "suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "skills": {{
        "score": <number 0-20>,
        "feedback": "feedback on skills organization and presentation",
        "suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "actionable_recommendations": {{
        "high_priority": [
            {{"recommendation": "specific recommendation", "impact": "expected impact", "effort": "low|medium|high"}},
            ...
        ],
        "medium_priority": [
            {{"recommendation": "specific recommendation", "impact": "expected impact", "effort": "low|medium|high"}},
            ...
        ],
        "low_priority": [
            {{"recommendation": "specific recommendation", "impact": "expected impact", "effort": "low|medium|high"}},
            ...
        ]
    }},
    "market_competitiveness": {{
        "assessment": "assessment of how competitive this CV is in the current market",
        "target_roles": ["role 1", "role 2"],
        "improvement_areas": ["area 1", "area 2"]
    }}
}}

Guidelines:
- Be specific and reference actual content from the CV
- Provide actionable, prioritized recommendations
- Consider the candidate's experience level (fresher/junior/mid-level)
- Focus on improvements that will have the most impact
- Balance constructive criticism with encouragement
- Consider industry standards and ATS optimization
- Score each section fairly based on quality and completeness
- Focus on job title quality and professional positioning in the professional_summary section

Return ONLY valid JSON.""",
        "input_variables": ["cv_data"],
        "partial_variables": {},
        "output_schema": {
            "type": "object",
            "properties": {
                "overall_assessment": {
                    "type": "object",
                    "properties": {
                        "overall_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "summary": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "overall_score",
                        "summary"
                    ]
                },
                "professional_summary": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 15
                        },
                        "feedback": {
                            "type": "string"
                        },
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "score",
                        "feedback",
                        "suggestions"
                    ]
                },
                "work_experience": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 25
                        },
                        "feedback": {
                            "type": "string"
                        },
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "score",
                        "feedback",
                        "suggestions"
                    ]
                },
                "projects": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 25
                        },
                        "feedback": {
                            "type": "string"
                        },
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "score",
                        "feedback",
                        "suggestions"
                    ]
                },
                "skills": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 20
                        },
                        "feedback": {
                            "type": "string"
                        },
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "score",
                        "feedback",
                        "suggestions"
                    ]
                },
                "actionable_recommendations": {
                    "type": "object",
                    "properties": {
                        "high_priority": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "recommendation": {
                                        "type": "string"
                                    },
                                    "impact": {
                                        "type": "string"
                                    },
                                    "effort": {
                                        "type": "string",
                                        "enum": [
                                            "low",
                                            "medium",
                                            "high"
                                        ]
                                    }
                                },
                                "required": [
                                    "recommendation",
                                    "impact",
                                    "effort"
                                ]
                            }
                        },
                        "medium_priority": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "recommendation": {
                                        "type": "string"
                                    },
                                    "impact": {
                                        "type": "string"
                                    },
                                    "effort": {
                                        "type": "string",
                                        "enum": [
                                            "low",
                                            "medium",
                                            "high"
                                        ]
                                    }
                                },
                                "required": [
                                    "recommendation",
                                    "impact",
                                    "effort"
                                ]
                            }
                        },
                        "low_priority": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "recommendation": {
                                        "type": "string"
                                    },
                                    "impact": {
                                        "type": "string"
                                    },
                                    "effort": {
                                        "type": "string",
                                        "enum": [
                                            "low",
                                            "medium",
                                            "high"
                                        ]
                                    }
                                },
                                "required": [
                                    "recommendation",
                                    "impact",
                                    "effort"
                                ]
                            }
                        }
                    },
                    "required": [
                        "high_priority",
                        "medium_priority",
                        "low_priority"
                    ]
                },
                "market_competitiveness": {
                    "type": "object",
                    "properties": {
                        "assessment": {
                            "type": "string"
                        },
                        "target_roles": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "improvement_areas": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "assessment",
                        "target_roles",
                        "improvement_areas"
                    ]
                }
            },
            "required": [
                "overall_assessment",
                "professional_summary",
                "work_experience",
                "projects",
                "skills",
                "actionable_recommendations",
                "market_competitiveness"
            ]
        },
        "temperature": 0.4,
        "max_tokens": 3000,
        "top_p": 0.95,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "is_active": False,
        "is_draft": True,
        "created_by": "system",
        "created_at": now,
    }

    # Code Solution Feedback prompt
    code_solution_feedback_prompt = {
        "id": uuid.UUID("b2c3d4e5-f6a7-8901-2345-67890abcdef1"),
        "name": "code_solution_feedback",
        "version": 1,
        "system_prompt": """You are an expert software engineer and code reviewer with 10+ years of experience in multiple programming languages and frameworks. Your role is to provide constructive, actionable feedback on code solutions that helps developers improve their coding skills and write better code.

Provide honest, professional feedback that balances encouragement with actionable improvements. Focus on:
- Code quality and readability
- Best practices and design patterns
- Maintainability and testability

Be specific, constructive, and prioritize feedback by impact. Reference specific lines or sections when possible.""",
        "user_template": """Review this code solution and provide comprehensive feedback.

Problem Description:
{problem_description}

Programming Language:
{language}

User's Code Solution:
{user_code_solution}

Provide detailed feedback covering the following areas:

1. **Overall Assessment** (correctness, approach, overall quality)
2. **Code Quality** (readability, naming, structure, organization)
3. **Best Practices** (SOLID principles, DRY, KISS, design patterns, language idioms)
4. **Actionable Recommendations** (prioritized improvements)

Return feedback in JSON format:
{{
    "overall_assessment": {{
        "overall_score": <number 0-100>,
        "summary": "2-3 sentence overall assessment of the solution"
    }},
    "code_quality": {{
        "score": <number 0-25>,
        "feedback": "feedback on code readability, structure, and organization",
        "suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "best_practices": {{
        "score": <number 0-20>,
        "feedback": "feedback on adherence to best practices and design principles",
        "principles_violated": ["principle 1", "principle 2"],
        "principles_followed": ["principle 1", "principle 2"],
        "suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "actionable_recommendations": {{
        "recommendation": "most important recommendation to improve the code",
        "impact": "expected impact of this recommendation",
        "effort": "low|medium|high",
        "line_reference": "line number or section reference if applicable"
    }}
}}

Guidelines:
- Be specific and reference actual code sections when possible
- Provide actionable, prioritized recommendations
- Consider the problem's complexity and requirements
- Focus on improvements that will have the most impact
- Balance constructive criticism with encouragement
- Consider language-specific best practices and idioms for the given programming language
- Score each section fairly based on quality and completeness
- For actionable_recommendations, provide the single most important recommendation
- Consider edge cases and error handling
- Evaluate code structure and maintainability
- Provide feedback appropriate for the programming language specified

Return ONLY valid JSON.""",
        "input_variables": ["problem_description", "language", "user_code_solution"],
        "partial_variables": {},
        "output_schema": {
            "type": "object",
            "properties": {
                "overall_assessment": {
                    "type": "object",
                    "properties": {
                        "overall_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "summary": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "overall_score",
                        "summary"
                    ]
                },
                "code_quality": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 25
                        },
                        "feedback": {
                            "type": "string"
                        },
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "score",
                        "feedback",
                        "suggestions"
                    ]
                },
                "best_practices": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 20
                        },
                        "feedback": {
                            "type": "string"
                        },
                        "principles_violated": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "principles_followed": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "score",
                        "feedback",
                        "principles_violated",
                        "principles_followed",
                        "suggestions"
                    ]
                },
                "actionable_recommendations": {
                    "type": "object",
                    "properties": {
                        "recommendation": {
                            "type": "string"
                        },
                        "impact": {
                            "type": "string"
                        },
                        "effort": {
                            "type": "string",
                            "enum": [
                                "low",
                                "medium",
                                "high"
                            ]
                        },
                        "line_reference": {
                            "type": "string"
                        }
                    }
                }
            },
            "required": [
                "overall_assessment",
                "code_quality",
                "best_practices",
                "actionable_recommendations"
            ]
        },
        "temperature": 0.4,
        "max_tokens": 3000,
        "top_p": 0.95,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "is_active": False,
        "is_draft": True,
        "created_by": "system",
        "created_at": now,
    }

    # Insert prompts
    cv_prompt_row = {
        "id": cv_feedback_prompt["id"],
        "name": cv_feedback_prompt["name"],
        "version": cv_feedback_prompt["version"],
        "system_prompt": cv_feedback_prompt["system_prompt"],
        "user_template": cv_feedback_prompt["user_template"],
        "input_variables": cv_feedback_prompt["input_variables"],
        "partial_variables": cv_feedback_prompt["partial_variables"],
        "output_schema": cv_feedback_prompt["output_schema"],
        "temperature": cv_feedback_prompt["temperature"],
        "max_tokens": cv_feedback_prompt["max_tokens"],
        "top_p": cv_feedback_prompt["top_p"],
        "frequency_penalty": cv_feedback_prompt["frequency_penalty"],
        "presence_penalty": cv_feedback_prompt["presence_penalty"],
        "is_active": cv_feedback_prompt["is_active"],
        "is_draft": cv_feedback_prompt["is_draft"],
        "created_at": cv_feedback_prompt["created_at"],
        "created_by": cv_feedback_prompt["created_by"],
    }

    code_prompt_row = {
        "id": code_solution_feedback_prompt["id"],
        "name": code_solution_feedback_prompt["name"],
        "version": code_solution_feedback_prompt["version"],
        "system_prompt": code_solution_feedback_prompt["system_prompt"],
        "user_template": code_solution_feedback_prompt["user_template"],
        "input_variables": code_solution_feedback_prompt["input_variables"],
        "partial_variables": code_solution_feedback_prompt["partial_variables"],
        "output_schema": code_solution_feedback_prompt["output_schema"],
        "temperature": code_solution_feedback_prompt["temperature"],
        "max_tokens": code_solution_feedback_prompt["max_tokens"],
        "top_p": code_solution_feedback_prompt["top_p"],
        "frequency_penalty": code_solution_feedback_prompt["frequency_penalty"],
        "presence_penalty": code_solution_feedback_prompt["presence_penalty"],
        "is_active": code_solution_feedback_prompt["is_active"],
        "is_draft": code_solution_feedback_prompt["is_draft"],
        "created_at": code_solution_feedback_prompt["created_at"],
        "created_by": code_solution_feedback_prompt["created_by"],
    }

    op.bulk_insert(prompt_templates_table, [cv_prompt_row, code_prompt_row])


def downgrade() -> None:
    """Remove cv_feedback and code_solution_feedback prompts."""

    conn = op.get_bind()

    # Delete prompts by UUID
    conn.execute(
        sa.text(
            """
            DELETE FROM prompt_templates
            WHERE id IN (
                'a1b2c3d4-e5f6-7890-1234-567890abcdef',
                'b2c3d4e5-f6a7-8901-2345-67890abcdef1'
            )
            """
        )
    )

