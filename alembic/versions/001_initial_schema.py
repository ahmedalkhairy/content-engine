"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "content_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
    )

    op.create_table(
        "content_ideas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False, server_default=""),
        sa.Column("angle", sa.Text(), server_default=""),
        sa.Column("target_audience", sa.String(255), server_default="DevOps engineers"),
        sa.Column("platform_preference", sa.String(50), server_default="both"),
        sa.Column("priority", sa.Integer(), server_default="5"),
        sa.Column("status", sa.String(50), server_default="new"),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("content_categories.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "post_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idea_id", sa.Integer(), sa.ForeignKey("content_ideas.id"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("linkedin_text", sa.Text(), server_default=""),
        sa.Column("facebook_text", sa.Text(), server_default=""),
        sa.Column("image_prompt", sa.Text(), server_default=""),
        sa.Column("image_path", sa.String(500), server_default=""),
        sa.Column("hashtags", sa.String(500), server_default=""),
        sa.Column("cta", sa.String(500), server_default=""),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("quality_warnings", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "scheduled_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("post_drafts.id"), nullable=False),
        sa.Column("platforms", sa.String(100), server_default="linkedin,facebook"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("auto_publish", sa.Boolean(), server_default="0"),
        sa.Column("status", sa.String(50), server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "published_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("post_drafts.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("external_post_id", sa.String(255), server_default=""),
        sa.Column("external_url", sa.String(500), server_default=""),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), server_default="published"),
        sa.Column("error_message", sa.Text(), server_default=""),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("value", sa.Text(), server_default=""),
        sa.Column("encrypted", sa.Boolean(), server_default="0"),
    )

    op.create_table(
        "generation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("post_drafts.id"), nullable=True),
        sa.Column("provider", sa.String(100), server_default=""),
        sa.Column("prompt", sa.Text(), server_default=""),
        sa.Column("response", sa.Text(), server_default=""),
        sa.Column("status", sa.String(50), server_default="success"),
        sa.Column("error_message", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("generation_logs")
    op.drop_table("settings")
    op.drop_table("published_posts")
    op.drop_table("scheduled_posts")
    op.drop_table("post_drafts")
    op.drop_table("content_ideas")
    op.drop_table("content_categories")
    op.drop_table("users")
