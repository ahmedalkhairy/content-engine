"""Dashboard router."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import Project, User
from app.services.analytics import AnalyticsService
from app.template_utils import templates

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    analytics = AnalyticsService(db, project)
    stats = analytics.get_dashboard_stats()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "user": user, "current_project": project, "stats": stats},
    )
