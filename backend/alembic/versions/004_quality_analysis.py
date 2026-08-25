"""Add clock_drift_factor to events; anomalies and evidence_conflicts tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_quality_analysis"
down_revision: Union[str, None] = "003_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("clock_drift_factor", sa.Float(), nullable=True),
    )

    op.create_table(
        "anomalies",
        sa.Column("anomaly_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="anomaly_severity",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "affected_event_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.PrimaryKeyConstraint("anomaly_id"),
    )
    op.create_index(op.f("ix_anomalies_case_id"), "anomalies", ["case_id"])
    op.create_index(op.f("ix_anomalies_rule_id"), "anomalies", ["rule_id"])

    op.create_table(
        "evidence_conflicts",
        sa.Column("conflict_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conflict_type", sa.String(length=128), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="conflict_severity",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.PrimaryKeyConstraint("conflict_id"),
    )
    op.create_index(
        op.f("ix_evidence_conflicts_case_id"), "evidence_conflicts", ["case_id"]
    )
    op.create_index(
        op.f("ix_evidence_conflicts_conflict_type"),
        "evidence_conflicts",
        ["conflict_type"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_evidence_conflicts_conflict_type"), table_name="evidence_conflicts"
    )
    op.drop_index(op.f("ix_evidence_conflicts_case_id"), table_name="evidence_conflicts")
    op.drop_table("evidence_conflicts")
    op.drop_index(op.f("ix_anomalies_rule_id"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_case_id"), table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_column("events", "clock_drift_factor")
