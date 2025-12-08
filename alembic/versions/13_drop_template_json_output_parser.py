"""Drop template_json and output_parser_type from prompt_templates."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "13"
down_revision = "12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove trigger/function if still present
    op.execute("DROP TRIGGER IF EXISTS trg_generate_template_json ON prompt_templates")
    op.execute("DROP FUNCTION IF EXISTS generate_template_json()")

    with op.batch_alter_table("prompt_templates") as batch_op:
        batch_op.drop_column("template_json")
        batch_op.drop_column("output_parser_type")


def downgrade() -> None:
    # Re-add columns
    with op.batch_alter_table("prompt_templates") as batch_op:
        batch_op.add_column(
            sa.Column("output_parser_type", sa.String(length=50), nullable=False, server_default="json_output_parser")
        )
        batch_op.add_column(sa.Column("template_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Recreate trigger/function (minimal recreation)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION generate_template_json()
        RETURNS trigger AS $$
        BEGIN
            NEW.template_json := jsonb_build_object(
                'system_prompt', NEW.system_prompt,
                'user_template', NEW.user_template,
                'input_variables', NEW.input_variables,
                'partial_variables', NEW.partial_variables,
                'output_schema', NEW.output_schema,
                'temperature', NEW.temperature,
                'max_tokens', NEW.max_tokens,
                'top_p', NEW.top_p,
                'frequency_penalty', NEW.frequency_penalty,
                'presence_penalty', NEW.presence_penalty
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_generate_template_json
        BEFORE INSERT OR UPDATE ON prompt_templates
        FOR EACH ROW EXECUTE FUNCTION generate_template_json();
        """
    )

