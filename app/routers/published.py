"""Published posts router."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import PostDraft, Project, PublishedPost, User
from app.template_utils import templates

router = APIRouter(prefix="/published", tags=["published"])


@router.get("")
def published_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    posts = (
        db.query(PublishedPost)
        .join(PostDraft)
        .filter(PostDraft.project_id == project.id)
        .order_by(PublishedPost.published_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "published.html", {"request": request, "user": user, "current_project": project, "posts": posts}
    )
