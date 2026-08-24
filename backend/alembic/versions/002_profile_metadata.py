"""Add processing profile selection metadata to evidence_artifacts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_profile_meta"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evidence_artifacts",
        sa.Column("profile_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "evidence_artifacts",
        sa.Column("match_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "evidence_artifacts",
        sa.Column(
            "match_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "evidence_artifacts",
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("evidence_artifacts", "needs_review")
    op.drop_column("evidence_artifacts", "match_reasons")
    op.drop_column("evidence_artifacts", "match_score")
    op.drop_column("evidence_artifacts", "profile_id")
