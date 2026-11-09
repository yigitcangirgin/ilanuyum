"""job description on applications and LLM match analyses

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("job_description", sa.Text(), nullable=True))

    op.create_table(
        "match_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_match_analyses_application_id"), "match_analyses", ["application_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_match_analyses_application_id"), table_name="match_analyses")
    op.drop_table("match_analyses")
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_column("job_description")
