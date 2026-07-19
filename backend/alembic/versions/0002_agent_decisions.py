"""agent_decisions + document_chunks

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04

Adds:
 - agent_decisions: the durable decision log so the planner can learn from
   past accept/reject/defer actions on recommendations.
- document_chunks: chunk-level embeddings for RAG on long documents (PRDS, reports).
  The whole-document embedding stays on documents.embedding.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.config import settings

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None  # type: ignore

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recommendation_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_decisions_workspace_id", "agent_decisions", ["workspace_id"])
    op.create_index("ix_agent_decisions_recommendation_id", "agent_decisions", ["recommendation_id"])
    op.create_index("ix_agent_decisions_decision", "agent_decisions", ["decision"])

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(settings.embedding_dimension), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_workspace_id", "document_chunks", ["workspace_id"])
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding"
        " ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_index("ix_document_chunks_workspace_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_agent_decisions_decision", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_recommendation_id", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_workspace_id", table_name="agent_decisions")
    op.drop_table("agent_decisions")