"""Add hypothesis_findings table for Phase 3 investigation agents."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_hypothesis_findings"
down_revision: Union[str, None] = "004_quality_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hypothesis_findings",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column(
            "supporting_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "contradicting_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "relevant_events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "missing_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "assumptions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Text(), nullable=True),
        sa.Column("domain_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rank_score", sa.Float(), nullable=True),
        sa.Column("rank_dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.PrimaryKeyConstraint("finding_id"),
    )
    op.create_index(
        op.f("ix_hypothesis_findings_case_id"), "hypothesis_findings", ["case_id"]
    )
    op.create_index(
        op.f("ix_hypothesis_findings_agent_id"), "hypothesis_findings", ["agent_id"]
    )
    op.create_index(
        op.f("ix_hypothesis_findings_domain"), "hypothesis_findings", ["domain"]
    )
    op.create_index(
        op.f("ix_hypothesis_findings_run_id"), "hypothesis_findings", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_hypothesis_findings_run_id"), table_name="hypothesis_findings")
    op.drop_index(op.f("ix_hypothesis_findings_domain"), table_name="hypothesis_findings")
    op.drop_index(
        op.f("ix_hypothesis_findings_agent_id"), table_name="hypothesis_findings"
    )
    op.drop_index(op.f("ix_hypothesis_findings_case_id"), table_name="hypothesis_findings")
    op.drop_table("hypothesis_findings")
