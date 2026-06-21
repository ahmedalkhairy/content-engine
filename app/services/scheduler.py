"""Publishing orchestration and scheduler."""

import logging
from datetime import datetime

import pytz
from sqlalchemy.orm import Session

from app.models import PostDraft, Project, PublishedPost, ScheduledPost
from app.services.facebook_publisher import FacebookPublisher
from app.services.linkedin_helper import LinkedInHelper
from app.services.notifications import NotificationService
from app.services.project_config import resolve_project_config

logger = logging.getLogger(__name__)


class PublishService:
    def __init__(self, db: Session, project: Project):
        self.db = db
        self.project = project
        self.config = resolve_project_config(project)
        self.facebook = FacebookPublisher(db, project)
        self.linkedin = LinkedInHelper(db, project)
        self.notifications = NotificationService(self.config)

    def can_auto_publish(self, auto_publish: bool) -> bool:
        return self.config.auto_publish_enabled and auto_publish

    def publish_draft(self, draft: PostDraft, platforms: list[str] | None = None) -> list[PublishedPost]:
        if draft.status == "rejected":
            raise ValueError("Cannot publish rejected draft")
        if draft.status not in ("approved", "scheduled", "ready_to_publish", "draft"):
            if draft.status == "published":
                raise ValueError("Draft already published")

        platforms = platforms or ["linkedin", "facebook"]
        results = []

        for platform in platforms:
            platform = platform.strip().lower()
            if platform == "facebook":
                results.append(self.facebook.publish(draft))
            elif platform == "linkedin":
                results.append(self.linkedin.publish(draft))

        all_success = all(r.status in ("published", "ready_to_publish") for r in results)
        if all_success:
            if any(r.status == "published" for r in results):
                draft.status = "published"
            elif any(r.status == "ready_to_publish" for r in results):
                draft.status = "ready_to_publish"
        else:
            draft.status = "failed"

        self.db.commit()
        return results


class SchedulerService:
    def __init__(self, db: Session, project: Project | None = None):
        self.db = db
        self.project = project
        if project:
            self.config = resolve_project_config(project)
            self.publish_service = PublishService(db, project)
            self.notifications = NotificationService(self.config)
            self.tz = pytz.timezone(self.config.default_timezone)
        else:
            from app.config import get_settings
            env = get_settings()
            self.config = None
            self.publish_service = None
            self.notifications = NotificationService()
            self.tz = pytz.timezone(env.default_timezone)

    def schedule_draft(
        self,
        draft: PostDraft,
        scheduled_at: datetime,
        platforms: str = "linkedin,facebook",
        auto_publish: bool = False,
    ) -> ScheduledPost:
        project = draft.project or self.project
        if project:
            config = resolve_project_config(project)
            tz = pytz.timezone(config.default_timezone)
        else:
            tz = self.tz

        if scheduled_at.tzinfo is None:
            scheduled_at = tz.localize(scheduled_at)

        if draft.status == "rejected":
            raise ValueError("Cannot schedule rejected draft")

        scheduled = ScheduledPost(
            draft_id=draft.id,
            platforms=platforms,
            scheduled_at=scheduled_at.astimezone(pytz.UTC).replace(tzinfo=None),
            auto_publish=auto_publish,
            status="scheduled",
        )
        self.db.add(scheduled)
        draft.status = "scheduled"
        self.db.commit()
        self.db.refresh(scheduled)
        return scheduled

    def process_due_posts(self) -> int:
        now = datetime.utcnow()
        due_posts = (
            self.db.query(ScheduledPost)
            .filter(ScheduledPost.status == "scheduled", ScheduledPost.scheduled_at <= now)
            .all()
        )

        processed = 0
        for scheduled in due_posts:
            try:
                self._process_scheduled_post(scheduled)
                processed += 1
            except Exception as e:
                logger.exception("Failed to process scheduled post %s: %s", scheduled.id, e)
                scheduled.status = "failed"
                if scheduled.draft:
                    scheduled.draft.status = "failed"
                self.db.commit()
        return processed

    def _process_scheduled_post(self, scheduled: ScheduledPost):
        draft = scheduled.draft
        if not draft or not draft.project:
            scheduled.status = "failed"
            self.db.commit()
            return

        if draft.status == "rejected":
            scheduled.status = "cancelled"
            self.db.commit()
            return

        publish_service = PublishService(self.db, draft.project)
        notifications = NotificationService(resolve_project_config(draft.project))
        platforms = [p.strip() for p in scheduled.platforms.split(",") if p.strip()]

        if publish_service.can_auto_publish(scheduled.auto_publish):
            publish_service.publish_draft(draft, platforms)
            scheduled.status = "published"
        else:
            draft.status = "ready_to_publish"
            scheduled.status = "ready_to_publish"
            notifications.notify_ready_to_publish(draft.title)

        self.db.commit()

    def run_worker_loop(self, interval_seconds: int = 60):
        import time

        from app.services.automation import AutomationService

        automation = AutomationService(self.db)
        logger.info("Scheduler worker started (interval=%ds)", interval_seconds)
        while True:
            try:
                auto_count = automation.process_all_projects()
                count = self.process_due_posts()
                logger.info(
                    "Worker cycle: automation_generated=%d, scheduled_processed=%d",
                    auto_count,
                    count,
                )
            except Exception:
                logger.exception("Worker loop error")
            time.sleep(interval_seconds)
