"""LinkedIn publishing helper and API placeholder."""

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import PostDraft, PublishedPost, Project
from app.services.notifications import NotificationService
from app.services.project_config import resolve_project_config


class LinkedInHelper:
    def __init__(self, db: Session, project: Project):
        self.db = db
        self.project = project
        self.config = resolve_project_config(project)
        self.notifications = NotificationService(self.config)

    @property
    def mode(self) -> str:
        return self.config.linkedin_mode

    def get_manual_publish_data(self, draft: PostDraft) -> dict:
        image_exists = bool(draft.image_path and Path(draft.image_path).exists())
        return {
            "platform": "linkedin",
            "mode": "manual",
            "title": draft.title,
            "text": draft.linkedin_text,
            "image_path": draft.image_path if image_exists else None,
            "image_filename": Path(draft.image_path).name if image_exists else None,
            "hashtags": draft.hashtags,
            "cta": draft.cta,
            "checklist": [
                "Open LinkedIn and click 'Start a post'",
                "Copy the post text below and paste it",
                "Click the image icon and upload the generated image",
                "Review formatting and hashtags",
                "Click 'Post' to publish",
                "Mark as published in the dashboard when done",
            ],
        }

    def publish(self, draft: PostDraft) -> PublishedPost:
        if draft.status == "rejected":
            raise ValueError("Cannot publish rejected draft")

        published = PublishedPost(
            draft_id=draft.id,
            platform="linkedin",
            status="pending",
        )
        self.db.add(published)
        self.db.flush()

        if self.mode == "api":
            return self._publish_via_api(draft, published)
        if self.mode == "browser":
            return self._publish_via_browser(draft, published)
        return self._mark_manual_ready(draft, published)

    def _publish_via_browser(self, draft: PostDraft, published: PublishedPost) -> PublishedPost:
        from app.config import get_settings
        from app.services.linkedin_browser import LinkedInBrowserPublisher

        headless = get_settings().linkedin_browser_headless
        try:
            external_url = LinkedInBrowserPublisher(headless=headless).publish_draft(draft)
            published.status = "published"
            published.external_url = external_url
            published.published_at = datetime.utcnow()
            draft.status = "published"
            self.db.commit()
            self.notifications.notify_published("linkedin", draft.title, external_url)
            return published
        except Exception as e:
            published.status = "failed"
            published.error_message = str(e)[:500]
            draft.status = "failed"
            self.db.commit()
            self.notifications.notify_publish_failed("linkedin", draft.title, published.error_message)
            return published

    def _mark_manual_ready(self, draft: PostDraft, published: PublishedPost) -> PublishedPost:
        published.status = "ready_to_publish"
        published.published_at = datetime.utcnow()
        draft.status = "ready_to_publish"
        self.db.commit()
        self.notifications.notify_ready_to_publish(draft.title)
        return published

    def mark_manually_published(self, draft: PostDraft, external_url: str = "") -> PublishedPost:
        published = (
            self.db.query(PublishedPost)
            .filter(PublishedPost.draft_id == draft.id, PublishedPost.platform == "linkedin")
            .order_by(PublishedPost.id.desc())
            .first()
        )
        if not published:
            published = PublishedPost(draft_id=draft.id, platform="linkedin", status="published")
            self.db.add(published)

        published.status = "published"
        published.external_url = external_url
        published.published_at = datetime.utcnow()
        draft.status = "published"
        self.db.commit()
        self.notifications.notify_published("linkedin", draft.title, external_url)
        return published

    def _publish_via_api(self, draft: PostDraft, published: PublishedPost) -> PublishedPost:
        published.status = "failed"
        published.error_message = (
            "LinkedIn API mode is not yet implemented. Use manual mode. "
            "See linkedin_helper.py for setup instructions."
        )
        self.db.commit()
        self.notifications.notify_publish_failed("linkedin", draft.title, published.error_message)
        return published
