from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(255), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    product_context: Mapped[str] = mapped_column(Text, default="")
    brand_tone: Mapped[str] = mapped_column(Text, default="")
    brand_avoid: Mapped[str] = mapped_column(Text, default="")
    brand_positioning: Mapped[str] = mapped_column(Text, default="")
    default_target_audience: Mapped[str] = mapped_column(String(255), default="")
    default_hashtags: Mapped[str] = mapped_column(String(500), default="")

    llm_provider: Mapped[str] = mapped_column(String(50), default="")
    llm_model: Mapped[str] = mapped_column(String(100), default="")
    openai_api_key: Mapped[str] = mapped_column(String(500), default="")
    gemini_api_key: Mapped[str] = mapped_column(String(500), default="")

    image_provider: Mapped[str] = mapped_column(String(50), default="")
    gemini_image_model: Mapped[str] = mapped_column(String(100), default="")

    facebook_page_id: Mapped[str] = mapped_column(String(255), default="")
    facebook_access_token: Mapped[str] = mapped_column(String(500), default="")
    linkedin_mode: Mapped[str] = mapped_column(String(50), default="manual")
    telegram_bot_token: Mapped[str] = mapped_column(String(500), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(100), default="")
    telegram_notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_send_link: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_send_linkedin_text: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_send_linkedin_image: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_send_facebook_text: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    default_timezone: Mapped[str] = mapped_column(String(100), default="")

    # Content automation / recurring schedule
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_interval_days: Mapped[int] = mapped_column(Integer, default=1)
    automation_posts_per_run: Mapped[int] = mapped_column(Integer, default=1)
    automation_spacing_days: Mapped[int] = mapped_column(Integer, default=1)
    automation_publish_time: Mapped[str] = mapped_column(String(10), default="10:00")
    automation_platforms: Mapped[str] = mapped_column(String(100), default="linkedin,facebook")
    automation_auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_auto_generate: Mapped[bool] = mapped_column(Boolean, default=True)
    automation_require_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    automation_last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    ideas: Mapped[list["ContentIdea"]] = relationship("ContentIdea", back_populates="project")
    categories: Mapped[list["ContentCategory"]] = relationship("ContentCategory", back_populates="project")


class ContentCategory(Base):
    __tablename__ = "content_categories"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_category_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="categories")


class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    angle: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(String(255), default="")
    platform_preference: Mapped[str] = mapped_column(String(50), default="both")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(50), default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("content_categories.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="ideas")
    category: Mapped["ContentCategory | None"] = relationship("ContentCategory")
    drafts: Mapped[list["PostDraft"]] = relationship("PostDraft", back_populates="idea")


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    linkedin_text: Mapped[str] = mapped_column(Text, default="")
    facebook_text: Mapped[str] = mapped_column(Text, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str] = mapped_column(String(500), default="")
    hashtags: Mapped[str] = mapped_column(String(500), default="")
    cta: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    quality_warnings: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project")
    idea: Mapped["ContentIdea | None"] = relationship("ContentIdea", back_populates="drafts")
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        "ScheduledPost", back_populates="draft"
    )
    published_posts: Mapped[list["PublishedPost"]] = relationship(
        "PublishedPost", back_populates="draft"
    )
    generation_logs: Mapped[list["GenerationLog"]] = relationship(
        "GenerationLog", back_populates="draft"
    )


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("post_drafts.id"), nullable=False)
    platforms: Mapped[str] = mapped_column(String(100), default="linkedin,facebook")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    draft: Mapped["PostDraft"] = relationship("PostDraft", back_populates="scheduled_posts")


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("post_drafts.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_post_id: Mapped[str] = mapped_column(String(255), default="")
    external_url: Mapped[str] = mapped_column(String(500), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="published")
    error_message: Mapped[str] = mapped_column(Text, default="")

    draft: Mapped["PostDraft"] = relationship("PostDraft", back_populates="published_posts")


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_setting_project_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("post_drafts.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="success")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    draft: Mapped["PostDraft | None"] = relationship("PostDraft", back_populates="generation_logs")
