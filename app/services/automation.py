"""Automated content generation — AI idea → draft → review notification."""

import logging
from datetime import datetime, timedelta

import pytz
from sqlalchemy.orm import Session

from app.models import PostDraft, Project, ScheduledPost
from app.services.ai_generator import AIGeneratorService
from app.services.project_config import resolve_project_config
from app.services.scheduler import SchedulerService

logger = logging.getLogger(__name__)


class AutomationService:
    def __init__(self, db: Session):
        self.db = db

    def should_run(self, project: Project, now: datetime | None = None) -> bool:
        if not project.automation_enabled:
            return False

        config = resolve_project_config(project)
        tz = pytz.timezone(config.default_timezone)
        now_local = now or datetime.now(tz)
        if now_local.tzinfo is None:
            now_local = tz.localize(now_local)

        hour, minute = self._parse_time(project.automation_publish_time or "10:00")
        run_moment = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now_local < run_moment:
            return False

        interval = max(1, project.automation_interval_days or 1)
        if not project.automation_last_run_at:
            return True

        last = project.automation_last_run_at
        if last.tzinfo is None:
            last = pytz.UTC.localize(last).astimezone(tz)
        else:
            last = last.astimezone(tz)

        days_since = (now_local.date() - last.date()).days
        return days_since >= interval

    def run_for_project(self, project: Project, force: bool = False) -> dict:
        """
        Default flow (require approval):
          AI generates idea → full draft → Telegram notification → waits for your review.

        Optional legacy flow (require approval off):
          Same generation + auto-schedule publish slots.
        """
        config = resolve_project_config(project)
        tz = pytz.timezone(config.default_timezone)
        now_local = datetime.now(tz)

        if not force and not self.should_run(project, now_local):
            return {"skipped": True, "reason": "Not due yet", "scheduled": 0, "generated": 0}

        posts_needed = max(1, min(project.automation_posts_per_run or 1, 10))
        require_approval = project.automation_require_approval if project.automation_require_approval is not None else True

        generator = AIGeneratorService(self.db, project)
        drafts: list[PostDraft] = []

        for _ in range(posts_needed):
            try:
                draft = generator.generate_post_from_ai_idea()
                drafts.append(draft)
            except Exception:
                logger.exception("Failed to generate post for project %s", project.name)

        if not drafts:
            return {
                "skipped": True,
                "reason": "AI generation failed",
                "scheduled": 0,
                "generated": 0,
            }

        scheduled_count = 0
        if not require_approval:
            scheduled_count = self._auto_schedule_drafts(project, drafts, tz, now_local)

        project.automation_last_run_at = datetime.utcnow()
        self.db.commit()

        return {
            "skipped": False,
            "scheduled": scheduled_count,
            "generated": len(drafts),
            "mode": "review" if require_approval else "auto_schedule",
        }

    def process_all_projects(self) -> int:
        projects = (
            self.db.query(Project)
            .filter(Project.is_active.is_(True), Project.automation_enabled.is_(True))
            .all()
        )
        total = 0
        for project in projects:
            try:
                result = self.run_for_project(project)
                if not result.get("skipped"):
                    total += result.get("generated", 0)
                    logger.info("Automation for %s: %s", project.name, result)
            except Exception:
                logger.exception("Automation failed for project %s", project.name)
        return total

    def _auto_schedule_drafts(
        self,
        project: Project,
        drafts: list[PostDraft],
        tz,
        now_local: datetime,
    ) -> int:
        """Legacy: schedule generated drafts without manual review."""
        spacing = max(1, project.automation_spacing_days or 1)
        platforms = project.automation_platforms or "linkedin,facebook"
        auto_publish = project.automation_auto_publish
        hour, minute = self._parse_time(project.automation_publish_time or "10:00")
        base_date = self._next_slot_base_date(project, tz, now_local, hour, minute, spacing)

        scheduler = SchedulerService(self.db, project)
        scheduled_count = 0
        for i, draft in enumerate(drafts):
            if draft.status == "draft":
                draft.status = "approved"
            slot_date = base_date + timedelta(days=i * spacing)
            scheduled_at = tz.localize(datetime(slot_date.year, slot_date.month, slot_date.day, hour, minute))
            if self._has_active_schedule(draft):
                continue
            scheduler.schedule_draft(draft, scheduled_at, platforms, auto_publish)
            scheduled_count += 1
        return scheduled_count

    def _next_slot_base_date(
        self,
        project: Project,
        tz,
        now_local: datetime,
        hour: int,
        minute: int,
        spacing: int,
    ):
        last_scheduled = (
            self.db.query(ScheduledPost)
            .join(PostDraft)
            .filter(PostDraft.project_id == project.id, ScheduledPost.status == "scheduled")
            .order_by(ScheduledPost.scheduled_at.desc())
            .first()
        )
        if last_scheduled and last_scheduled.scheduled_at:
            last_dt = last_scheduled.scheduled_at
            if last_dt.tzinfo is None:
                last_dt = pytz.UTC.localize(last_dt).astimezone(tz)
            else:
                last_dt = last_dt.astimezone(tz)
            return last_dt.date() + timedelta(days=spacing)

        base = now_local.date()
        if now_local.hour > hour or (now_local.hour == hour and now_local.minute >= minute):
            base = base + timedelta(days=1)
        return base

    def _has_active_schedule(self, draft: PostDraft) -> bool:
        return (
            self.db.query(ScheduledPost)
            .filter(ScheduledPost.draft_id == draft.id, ScheduledPost.status == "scheduled")
            .first()
            is not None
        )

    @staticmethod
    def _parse_time(value: str) -> tuple[int, int]:
        parts = (value or "10:00").split(":")
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
