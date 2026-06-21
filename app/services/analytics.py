"""Analytics tracking service."""

from sqlalchemy.orm import Session

from app.models import ContentIdea, PostDraft, Project, PublishedPost, ScheduledPost


class AnalyticsService:
    def __init__(self, db: Session, project: Project):
        self.db = db
        self.project = project

    def get_dashboard_stats(self) -> dict:
        pid = self.project.id
        drafts = self.db.query(PostDraft).filter(PostDraft.project_id == pid).all()
        scheduled = (
            self.db.query(ScheduledPost)
            .join(PostDraft)
            .filter(PostDraft.project_id == pid, ScheduledPost.status == "scheduled")
            .order_by(ScheduledPost.scheduled_at)
            .limit(10)
            .all()
        )
        published = (
            self.db.query(PublishedPost)
            .join(PostDraft)
            .filter(PostDraft.project_id == pid)
            .all()
        )

        return {
            "total_drafts": sum(1 for d in drafts if d.status == "draft"),
            "approved": sum(1 for d in drafts if d.status == "approved"),
            "scheduled": sum(1 for d in drafts if d.status == "scheduled"),
            "published": sum(1 for d in drafts if d.status == "published"),
            "failed": sum(1 for d in drafts if d.status == "failed"),
            "ready_to_publish": sum(1 for d in drafts if d.status == "ready_to_publish"),
            "rejected": sum(1 for d in drafts if d.status == "rejected"),
            "upcoming_scheduled": scheduled,
            "total_published_records": len(published),
            "total_ideas": self.db.query(ContentIdea).filter(ContentIdea.project_id == pid).count(),
        }
