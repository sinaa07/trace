"""Initial schema for case ingestion."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("incident_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "ingesting",
                "ready",
                "investigating",
                "closed",
                name="case_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
    )

    op.create_table(
        "evidence_artifacts",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "signal_log",
                "train_telemetry",
                "maintenance",
                "weather",
                "witness",
                "other",
                name="source_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("acquisition_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "processing_status",
            sa.Enum(
                "pending",
                "parsing",
                "cleaning",
                "completed",
                "failed",
                name="processing_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column(
            "custody_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index(
        op.f("ix_evidence_artifacts_case_id"),
        "evidence_artifacts",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_artifacts_sha256"),
        "evidence_artifacts",
        ["sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_artifacts_processing_status"),
        "evidence_artifacts",
        ["processing_status"],
        unique=False,
    )

    op.create_table(
        "evidence_records",
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_index", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "normalized_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "field_provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "parse_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_artifacts.evidence_id"]),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index(
        op.f("ix_evidence_records_evidence_id"),
        "evidence_records",
        ["evidence_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_records_case_id"),
        "evidence_records",
        ["case_id"],
        unique=False,
    )

    op.create_table(
        "audit_log",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        op.f("ix_audit_log_case_id"), "audit_log", ["case_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_case_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_evidence_records_case_id"), table_name="evidence_records")
    op.drop_index(
        op.f("ix_evidence_records_evidence_id"), table_name="evidence_records"
    )
    op.drop_table("evidence_records")
    op.drop_index(
        op.f("ix_evidence_artifacts_processing_status"), table_name="evidence_artifacts"
    )
    op.drop_index(op.f("ix_evidence_artifacts_sha256"), table_name="evidence_artifacts")
    op.drop_index(op.f("ix_evidence_artifacts_case_id"), table_name="evidence_artifacts")
    op.drop_table("evidence_artifacts")
    op.drop_table("cases")
