"""Facebook Page publishing via Graph API."""

from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.models import PostDraft, PublishedPost, Project
from app.services.notifications import NotificationService
from app.services.project_config import resolve_project_config


class FacebookPublisher:
    GRAPH_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, db: Session, project: Project):
        self.db = db
        self.config = resolve_project_config(project)
        self.notifications = NotificationService(self.config)

    @property
    def configured(self) -> bool:
        return bool(self.config.facebook_page_id and self.config.facebook_access_token)

    def publish(self, draft: PostDraft) -> PublishedPost:
        if draft.status == "rejected":
            raise ValueError("Cannot publish rejected draft")

        published = PublishedPost(
            draft_id=draft.id,
            platform="facebook",
            status="pending",
        )
        self.db.add(published)
        self.db.flush()

        if not self.configured:
            published.status = "failed"
            published.error_message = (
                "Facebook credentials not configured for this project"
            )
            self.db.commit()
            self.notifications.notify_publish_failed("facebook", draft.title, published.error_message)
            return published

        try:
            if draft.image_path and Path(draft.image_path).exists():
                result = self._publish_photo(draft)
            else:
                result = self._publish_text(draft)

            post_id = result.get("id", result.get("post_id", ""))
            published.external_post_id = str(post_id)
            published.external_url = f"https://www.facebook.com/{post_id}" if post_id else ""
            published.published_at = datetime.utcnow()
            published.status = "published"
            self.notifications.notify_published("facebook", draft.title, published.external_url)

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500]
            published.status = "failed"
            published.error_message = f"HTTP {e.response.status_code}: {error_body}"
            self.notifications.notify_publish_failed("facebook", draft.title, published.error_message)
        except Exception as e:
            published.status = "failed"
            published.error_message = str(e)[:500]
            self.notifications.notify_publish_failed("facebook", draft.title, published.error_message)

        self.db.commit()
        return published

    def _publish_text(self, draft: PostDraft) -> dict:
        url = f"{self.GRAPH_URL}/{self.config.facebook_page_id}/feed"
        with httpx.Client(timeout=60) as client:
            response = client.post(
                url,
                data={
                    "message": draft.facebook_text,
                    "access_token": self.config.facebook_access_token,
                },
            )
            response.raise_for_status()
            return response.json()

    def _publish_photo(self, draft: PostDraft) -> dict:
        url = f"{self.GRAPH_URL}/{self.config.facebook_page_id}/photos"
        image_path = Path(draft.image_path)
        with httpx.Client(timeout=120) as client:
            with open(image_path, "rb") as f:
                response = client.post(
                    url,
                    data={
                        "caption": draft.facebook_text,
                        "access_token": self.config.facebook_access_token,
                    },
                    files={"source": (image_path.name, f, "image/png")},
                )
            response.raise_for_status()
            return response.json()
