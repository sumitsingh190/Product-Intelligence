"""raw operational entities

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-10

Moves raw operational data (reviews, support tickets, github activity, jira issues, 
product events, competitor updates) into Postgres. Previously these tables were only 
in DuckDB, which inverted the intended OLTP/OLAP split: Postgres is now the sole source 
of truth for raw entities, and DuckDB is populated exclusively by the ETL for analytical 
workloads.
"""


from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision= "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.Foreignkey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("rating", sa. Float(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_reviews_workspace_id", "reviews", ["workspace_id"])
    op.create_index("ix_reviews_source", "reviews", ["source"])
    op.create_index("ix_reviews_reviewed_at", "reviews", ["reviewed_at"])

    op.create_table(
        "support tickets",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.Foreignkey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("subject", sa. String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("ticket_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticket_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), 
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index("ix_support_tickets_workspace_id", "support tickets", ["workspace_id"])
    op.create_index("ix_support_tickets_source", "support_tickets", ["source"]) 
    op.create_index("ix_support_tickets_status", "support tickets", ["status"])
    op.create_index("ix_support_tickets_ticket_created_at", "support tickets", ["ticket created_at"])

# github_activity

    op.create_table(
        "github activity",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.Foreignkey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repo", sa.String(255), nullable=False),
        sa.Column("activity type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(1000), nullable=True), 
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(50), nullable=True), 
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("activity_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activity_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_github_activity_workspace_id", "github_activity", ["workspace_id"])
    op.create_index("ix_github_activity_repo", "github_activity", ["repo"]) 
    op.create_Index("ix_github_activity_activity_type", "github_activity", ["activity_type"])
    op.create_index("ix_github_activity_activity_created_at", "github_activity", ["activity_created_at"])

    op.create_table(
        "jira_issues",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.Foreignkey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_key", sa.String(50), nullable=False),
        sa.Column("issue type", sa.String(50), nullable=True),
        sa.Column("summary", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("assignee", sa.String(255), nullable=True),
        sa.Column("reporter", sa.String(255), nullable=True),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=False, server_default="()"),
        sa.Column("issue_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issue updated at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sprint_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jira_issues_workspace_id", "jira_issues", ["workspace_id"])
    op.create_index("ix_jira_issues_project_key", "jira_issues", ["project_key"])
    op.create_index("ix_jira_issues_issue_type", "jira_issues", ["issue_type"])
    op.create_index("ix_jira_issues_status", "jira_issues", ["status"])
    op.create_index("ix_jira_issues_issue_created_at", "jira_issues", ["issue_created_at"])

# product events

    op.create_table(
        "product_events",
        sa.Column("id", sa. String(255), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False), 
            sa.Foreignkey("workspaces.id", ondelete="CASCADE"), 
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("event_name", sa.String(255), nullable=False),
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("platform", sa.String(50), nullable=True), 
        sa.Column("app_version", sa.String(50), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), 
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_events_workspace_id", "product_events", ["workspace_id"])
    op.create_index("ix_product_events_user_id", "product_events", ["user_id"])
    op.create_index("ix_product_events_event_name", "product_events", ["event_name"])
    op.create_index("ix_product_events_event_at", "product_events", ["event_at"])

# competitor_updates

    op.create_table(
        "competitor_updates",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=False),
            sa.Foreignkey("workspaces.id", jondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competitor_name", sa.String(255), nullable=False),
        sa.Column("update_type", sa.String(50), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ) 
    op.create_index("ix_competitor_updates_workspace_id", "competitor_updates", ["workspace_id"])
    op.create_index("ix_competitor_updates_competitor_name", "competitor_updates", ["competitor_name"])
    op.create_index("ix_competitor_updates_published_at", "competitor_updates", ["published_at"])

def downgrade() -> None:
    for tbl in (
        "competitor_updates",
        "product_events",
        "jira_issues",
        "github_activity",
        "support_tickets",
        "reviews",
    ):
        op.drop_table(tbl)