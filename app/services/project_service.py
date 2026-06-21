"""Project management and migration helpers."""

import re

import yaml
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine
from app.models import ContentCategory, ContentIdea, PostDraft, Project, Setting


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def load_brand_yaml() -> dict:
    brand_file = get_settings().brand_file
    if brand_file.exists():
        with open(brand_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def create_infrapilot_project(db: Session) -> Project:
    brand = load_brand_yaml()
    env = get_settings()

    project = Project(
        name="InfraPilot",
        slug="infrapilot",
        brand_name=brand.get("brand_name", "InfraPilot"),
        website="https://infrapilot.io",
        product_context=(
            "InfraPilot is a SaaS platform for server monitoring and management.\n"
            "Core value: manage and monitor servers without exposing SSH to the internet.\n"
            "Agent connects outbound-only. No shared passwords. Each server has revocable identity.\n"
            "Centralized visibility for health, connectivity, alerts, and automation."
        ),
        brand_tone="\n".join(f"- {t}" for t in brand.get("tone", [])),
        brand_avoid="\n".join(f"- {a}" for a in brand.get("avoid", [])),
        brand_positioning="\n".join(f"- {p}" for p in brand.get("positioning", [])),
        default_target_audience="DevOps engineers, SaaS founders, CTOs, system administrators",
        default_hashtags="DevOps,ServerManagement,InfraPilot,Infrastructure",
        llm_provider=env.llm_provider,
        llm_model=env.gemini_model if env.llm_provider == "gemini" else env.openai_model,
        image_provider=env.image_provider,
        gemini_image_model=env.gemini_image_model,
        linkedin_mode=env.linkedin_mode,
        auto_publish_enabled=env.auto_publish_enabled,
        default_timezone=env.default_timezone,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def ensure_default_project(db: Session) -> Project:
    project = db.query(Project).filter(Project.slug == "infrapilot").first()
    if project:
        return project
    existing = db.query(Project).first()
    if existing:
        return existing
    return create_infrapilot_project(db)


def get_project_by_id_or_slug(db: Session, project_id: int | None = None, slug: str | None = None) -> Project | None:
    if project_id:
        return db.get(Project, project_id)
    if slug:
        return db.query(Project).filter(Project.slug == slug).first()
    return None


def migrate_legacy_data(db: Session) -> None:
    """Assign orphaned records to the default project after schema upgrade."""
    project = ensure_default_project(db)
    pid = project.id

    for idea in db.query(ContentIdea).filter(ContentIdea.project_id.is_(None)).all():
        idea.project_id = pid
    for draft in db.query(PostDraft).filter(PostDraft.project_id.is_(None)).all():
        if draft.idea_id:
            idea = db.get(ContentIdea, draft.idea_id)
            draft.project_id = idea.project_id if idea else pid
        else:
            draft.project_id = pid
    for cat in db.query(ContentCategory).filter(ContentCategory.project_id.is_(None)).all():
        cat.project_id = pid

    db.commit()


def run_schema_migrations() -> None:
    """Add project_id columns to existing SQLite tables if missing."""
    insp = inspect(engine)
    tables = insp.get_table_names()

    if "projects" not in tables:
        return

    migrations = [
        ("content_categories", "project_id INTEGER"),
        ("content_ideas", "project_id INTEGER"),
        ("post_drafts", "project_id INTEGER"),
        ("settings", "project_id INTEGER"),
    ]

    project_automation_cols = [
        ("automation_enabled", "BOOLEAN DEFAULT 0"),
        ("automation_interval_days", "INTEGER DEFAULT 1"),
        ("automation_posts_per_run", "INTEGER DEFAULT 1"),
        ("automation_spacing_days", "INTEGER DEFAULT 1"),
        ("automation_publish_time", "VARCHAR(10) DEFAULT '10:00'"),
        ("automation_platforms", "VARCHAR(100) DEFAULT 'linkedin,facebook'"),
        ("automation_auto_publish", "BOOLEAN DEFAULT 0"),
        ("automation_auto_generate", "BOOLEAN DEFAULT 1"),
        ("automation_require_approval", "BOOLEAN DEFAULT 1"),
        ("automation_last_run_at", "DATETIME"),
    ]

    project_telegram_cols = [
        ("telegram_notify_enabled", "BOOLEAN DEFAULT 1"),
        ("telegram_send_link", "BOOLEAN DEFAULT 1"),
        ("telegram_send_linkedin_text", "BOOLEAN DEFAULT 0"),
        ("telegram_send_linkedin_image", "BOOLEAN DEFAULT 0"),
        ("telegram_send_facebook_text", "BOOLEAN DEFAULT 0"),
    ]

    with engine.begin() as conn:
        for table, column_def in migrations:
            if table not in tables:
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "project_id" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_def}"))

        if "projects" in tables:
            proj_cols = {c["name"] for c in insp.get_columns("projects")}
            for col_name, col_def in project_automation_cols:
                if col_name not in proj_cols:
                    conn.execute(text(f"ALTER TABLE projects ADD COLUMN {col_name} {col_def}"))
            for col_name, col_def in project_telegram_cols:
                if col_name not in proj_cols:
                    conn.execute(text(f"ALTER TABLE projects ADD COLUMN {col_name} {col_def}"))
