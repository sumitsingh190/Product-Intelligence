"""retrieval FTS indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-04

Adds GIN indexes on the `to_tsvector('english', title || ' ' || body)`
expressions used by the hybrid search endpoint. Without these Postgres sequential-scans every row on every query. 
Expressions match the SQL in backend/app/api/v1/endpbints/search.py verbatim so the planner will actually pick the index.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_documents_fts_en 
            ON documents
            USING gin (
                to_tsvector('english',
                    coalesce(title, '') || ' ' || coalesce(content_preview, '')
                )
            )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_insights_fts_en
            ON insights 
            USING gin (
                to_tsvector('english',
                    coalesce(title, '') || ' ' || coalesce (summary, '')
                )
            )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_fts_en 
            ON document_chunks
            USING gin (
                to_tsvector('english', coalesce(content,''))
            )
        """
    )

def downgrade() -> None:

    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts_en")
    op.execute("DROP INDEX IF EXISTS ix_insights_fts_en")
    op.execute("DROP INDEX IF EXISTS ix_documents_fts_en")