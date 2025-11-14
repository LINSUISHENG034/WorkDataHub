"""Create core schema management tables for Story 1.7."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

revision = "20251113_000001"
down_revision = None
branch_labels = None
depends_on = None

UUID_TYPE = sa.String(length=36).with_variant(
    sa.dialects.postgresql.UUID(as_uuid=True), "postgresql"
)
JSONB_TYPE = sa.JSON().with_variant(
    sa.dialects.postgresql.JSONB(none_as_null=True), "postgresql"
)


def upgrade() -> None:
    """Create pipeline_executions and data_quality_metrics tables."""
    op.create_table(
        "pipeline_executions",
        sa.Column("execution_id", UUID_TYPE, primary_key=True),
        sa.Column("pipeline_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_file", sa.Text(), nullable=True),
        sa.Column("row_counts", JSONB_TYPE, nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_pipeline_executions_pipeline_name",
        "pipeline_executions",
        ["pipeline_name"],
    )
    op.create_index(
        "ix_pipeline_executions_started_at",
        "pipeline_executions",
        ["started_at"],
    )

    op.create_table(
        "data_quality_metrics",
        sa.Column("metric_id", UUID_TYPE, primary_key=True),
        sa.Column(
            "execution_id",
            UUID_TYPE,
            sa.ForeignKey("pipeline_executions.execution_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pipeline_name", sa.String(length=150), nullable=False),
        sa.Column("metric_type", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", JSONB_TYPE, nullable=True),
    )
    op.create_index(
        "ix_data_quality_metrics_pipeline_name",
        "data_quality_metrics",
        ["pipeline_name"],
    )
    op.create_index(
        "ix_data_quality_metrics_metric_type",
        "data_quality_metrics",
        ["metric_type"],
    )


def downgrade() -> None:
    """Drop tables created for Story 1.7."""
    op.drop_index(
        "ix_data_quality_metrics_metric_type",
        table_name="data_quality_metrics",
    )
    op.drop_index(
        "ix_data_quality_metrics_pipeline_name",
        table_name="data_quality_metrics",
    )
    op.drop_table("data_quality_metrics")

    op.drop_index(
        "ix_pipeline_executions_started_at",
        table_name="pipeline_executions",
    )
    op.drop_index(
        "ix_pipeline_executions_pipeline_name",
        table_name="pipeline_executions",
    )
    op.drop_table("pipeline_executions")
