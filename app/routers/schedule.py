"""Schedule router."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import PostDraft, Project, ScheduledPost, User
from app.services.automation import AutomationService
from app.services.project_config import resolve_project_config
from app.template_utils import templates

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("")
def schedule_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    scheduled = (
        db.query(ScheduledPost)
        .join(PostDraft)
        .filter(PostDraft.project_id == project.id)
        .order_by(ScheduledPost.scheduled_at)
        .all()
    )
    config = resolve_project_config(project)
    automation_due = AutomationService(db).should_run(project)
    return templates.TemplateResponse(
        request,
        "schedule.html",
        {
            "request": request,
            "user": user,
            "current_project": project,
            "scheduled": scheduled,
            "config": config,
            "automation_due": automation_due,
            "message": request.query_params.get("msg"),
        },
    )


@router.post("/automation")
def save_automation_settings(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
    automation_enabled: str = Form("false"),
    automation_interval_days: int = Form(1),
    automation_posts_per_run: int = Form(1),
    automation_spacing_days: int = Form(1),
    automation_publish_time: str = Form("10:00"),
    automation_platforms: str = Form("linkedin,facebook"),
    automation_auto_publish: str = Form("false"),
    automation_auto_generate: str = Form("true"),
    automation_require_approval: str = Form("true"),
):
    project.automation_enabled = automation_enabled.lower() in ("true", "1", "on", "yes")
    project.automation_interval_days = max(1, min(automation_interval_days, 365))
    project.automation_posts_per_run = max(1, min(automation_posts_per_run, 10))
    project.automation_spacing_days = max(1, min(automation_spacing_days, 30))
    project.automation_publish_time = automation_publish_time.strip() or "10:00"
    project.automation_platforms = automation_platforms.strip() or "linkedin,facebook"
    project.automation_auto_publish = automation_auto_publish.lower() in ("true", "1", "on", "yes")
    project.automation_auto_generate = automation_auto_generate.lower() in ("true", "1", "on", "yes")
    project.automation_require_approval = automation_require_approval.lower() in ("true", "1", "on", "yes")
    db.commit()
    return RedirectResponse(url="/schedule?msg=Automation+settings+saved", status_code=303)


@router.post("/automation/run")
def run_automation_now(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    result = AutomationService(db).run_for_project(project, force=True)
    if result.get("skipped"):
        msg = f"No+posts+generated:+{result.get('reason', 'unknown').replace(' ', '+')}"
    else:
        msg = f"Generated+{result.get('generated', 0)}+posts+ready+for+review"
    return RedirectResponse(url=f"/schedule?msg={msg}", status_code=303)
