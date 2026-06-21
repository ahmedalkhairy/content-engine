"""Public blog helpers."""

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import PostDraft, Project
from app.services.project_service import slugify

PUBLIC_STATUSES = frozenset({"approved", "published", "ready_to_publish", "scheduled"})


def get_blog_project(db: Session, slug: str) -> Project | None:
    return db.query(Project).filter(Project.slug == slug, Project.is_active.is_(True)).first()


def excerpt(text: str, max_len: int = 160) -> str:
    plain = re.sub(r"\s+", " ", (text or "").strip())
    if len(plain) <= max_len:
        return plain
    return plain[: max_len - 1].rsplit(" ", 1)[0] + "…"


def ensure_unique_slug(db: Session, draft: PostDraft, base: str | None = None) -> str:
    candidate = slugify(base or draft.title or f"post-{draft.id}")
    if not candidate:
        candidate = f"post-{draft.id}"

    slug = candidate
    suffix = 2
    while True:
        existing = (
            db.query(PostDraft)
            .filter(PostDraft.blog_slug == slug, PostDraft.id != draft.id)
            .first()
        )
        if not existing:
            return slug
        slug = f"{candidate}-{suffix}"
        suffix += 1


def list_public_posts(db: Session, project: Project, *, limit: int = 50, offset: int = 0) -> list[PostDraft]:
    return (
        db.query(PostDraft)
        .filter(
            PostDraft.project_id == project.id,
            PostDraft.blog_public.is_(True),
            PostDraft.status.in_(tuple(PUBLIC_STATUSES)),
            PostDraft.blog_slug != "",
        )
        .order_by(PostDraft.blog_published_at.desc(), PostDraft.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_public_post(db: Session, project: Project, slug: str) -> PostDraft | None:
    draft = (
        db.query(PostDraft)
        .filter(
            PostDraft.project_id == project.id,
            PostDraft.blog_slug == slug,
            PostDraft.blog_public.is_(True),
            PostDraft.status.in_(tuple(PUBLIC_STATUSES)),
        )
        .first()
    )
    return draft


def post_body(draft: PostDraft) -> str:
    return (draft.linkedin_text or draft.facebook_text or "").strip()


def canonical_external_url(draft: PostDraft) -> str | None:
    for published in draft.published_posts:
        if published.platform == "linkedin" and published.external_url:
            return published.external_url
    return None


def set_blog_visibility(db: Session, draft: PostDraft, *, public: bool) -> PostDraft:
    draft.blog_public = public
    if public:
        if not draft.blog_slug:
            draft.blog_slug = ensure_unique_slug(db, draft)
        if not draft.blog_published_at:
            draft.blog_published_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    return draft
