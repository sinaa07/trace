"""Add events table for Phase 2 event extraction and timeline."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_events"
down_revision: Union[str, None] = "002_profile_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("raw_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corrected_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("temporal_confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("clock_offset_seconds", sa.Float(), nullable=True),
        sa.Column("source_id", sa.String(length=256), nullable=True),
        sa.Column("entity_id", sa.String(length=256), nullable=True),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("timeline_index", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_artifacts.evidence_id"]),
        sa.ForeignKeyConstraint(["record_id"], ["evidence_records.record_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_events_case_id"), "events", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_events_evidence_id"), "events", ["evidence_id"], unique=False
    )
    op.create_index(op.f("ix_events_record_id"), "events", ["record_id"], unique=False)
    op.create_index(op.f("ix_events_event_type"), "events", ["event_type"], unique=False)
    op.create_index(
        op.f("ix_events_corrected_timestamp"),
        "events",
        ["corrected_timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_events_entity_id"), "events", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_events_timeline_index"), "events", ["timeline_index"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_events_timeline_index"), table_name="events")
    op.drop_index(op.f("ix_events_entity_id"), table_name="events")
    op.drop_index(op.f("ix_events_corrected_timestamp"), table_name="events")
    op.drop_index(op.f("ix_events_event_type"), table_name="events")
    op.drop_index(op.f("ix_events_record_id"), table_name="events")
    op.drop_index(op.f("ix_events_evidence_id"), table_name="events")
    op.drop_index(op.f("ix_events_case_id"), table_name="events")
    op.drop_table("events")
