"""Post drafts router."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import PostDraft, Project, User
from app.services.ai_generator import AIGeneratorService
from app.services.image_service import ImageGenerationService
from app.services.linkedin_helper import LinkedInHelper
from app.services.scheduler import PublishService, SchedulerService
from app.template_utils import templates

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _get_draft(db: Session, draft_id: int, project: Project) -> PostDraft | None:
    draft = db.get(PostDraft, draft_id)
    if draft and draft.project_id == project.id:
        return draft
    return None


@router.get("")
def drafts_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    drafts = (
        db.query(PostDraft)
        .filter(PostDraft.project_id == project.id)
        .order_by(PostDraft.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "drafts.html", {"request": request, "user": user, "current_project": project, "drafts": drafts}
    )


@router.get("/{draft_id}")
def draft_detail(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    draft = _get_draft(db, draft_id, project)
    if not draft:
        return RedirectResponse(url="/drafts", status_code=303)

    linkedin_data = LinkedInHelper(db, project).get_manual_publish_data(draft)
    image_error = request.query_params.get("image_error")
    review_error = request.query_params.get("review_error")
    flash_msg = request.query_params.get("msg")
    return templates.TemplateResponse(
        request,
        "draft_detail.html",
        {
            "request": request,
            "user": user,
            "current_project": project,
            "draft": draft,
            "linkedin_data": linkedin_data,
            "image_error": image_error,
            "review_error": review_error,
            "flash_msg": flash_msg,
        },
    )


@router.post("/{draft_id}/approve")
def approve_draft(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user), project: Project = Depends(get_current_project)):
    draft = _get_draft(db, draft_id, project)
    if draft:
        draft.status = "approved"
        db.commit()
    return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)


@router.post("/{draft_id}/review")
def review_draft(
    draft_id: int,
    action: str = Form("approve_only"),
    scheduled_date: str = Form(""),
    scheduled_time: str = Form("10:00"),
    platforms: str = Form("linkedin,facebook"),
    auto_publish: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from datetime import datetime
    from urllib.parse import quote

    draft = _get_draft(db, draft_id, project)
    if not draft or draft.status in ("rejected", "published"):
        return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)

    draft.status = "approved"
    db.commit()

    if action == "publish_now":
        platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
        PublishService(db, project).publish_draft(draft, platform_list)
        return RedirectResponse(url=f"/drafts/{draft_id}?msg=published", status_code=303)

    if action == "schedule":
        if not scheduled_date:
            msg = quote("Pick a date to schedule publishing")
            return RedirectResponse(url=f"/drafts/{draft_id}?review_error={msg}", status_code=303)
        scheduled_at = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
        SchedulerService(db, project).schedule_draft(draft, scheduled_at, platforms, auto_publish)
        return RedirectResponse(url="/schedule?msg=Post+scheduled+for+publishing", status_code=303)

    return RedirectResponse(url=f"/drafts/{draft_id}?msg=approved", status_code=303)


@router.post("/{draft_id}/reject")
def reject_draft(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user), project: Project = Depends(get_current_project)):
    draft = _get_draft(db, draft_id, project)
    if draft:
        draft.status = "rejected"
        db.commit()
    return RedirectResponse(url="/drafts", status_code=303)


@router.post("/{draft_id}/regenerate-text")
def regenerate_text(draft_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user), project: Project = Depends(get_current_project)):
    draft = _get_draft(db, draft_id, project)
    if draft and draft.idea:
        new_draft = AIGeneratorService(db, project).generate_draft_from_idea(draft.idea)
        return RedirectResponse(url=f"/drafts/{new_draft.id}", status_code=303)
    return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)


@router.post("/{draft_id}/regenerate-image")
def regenerate_image(
    draft_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from urllib.parse import quote

    draft = _get_draft(db, draft_id, project)
    if draft:
        try:
            ImageGenerationService(db, project).generate_for_draft(draft)
        except Exception as e:
            msg = quote(str(e)[:200])
            return RedirectResponse(url=f"/drafts/{draft_id}?image_error={msg}", status_code=303)
    return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)


@router.post("/{draft_id}/edit")
def edit_draft(
    draft_id: int,
    title: str = Form(...),
    linkedin_text: str = Form(""),
    facebook_text: str = Form(""),
    image_prompt: str = Form(""),
    hashtags: str = Form(""),
    cta: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    draft = _get_draft(db, draft_id, project)
    if draft:
        draft.title = title
        draft.linkedin_text = linkedin_text
        draft.facebook_text = facebook_text
        draft.image_prompt = image_prompt
        draft.hashtags = hashtags
        draft.cta = cta
        db.commit()
    return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)


@router.post("/{draft_id}/schedule")
def schedule_draft(
    draft_id: int,
    scheduled_date: str = Form(...),
    scheduled_time: str = Form(...),
    platforms: str = Form("linkedin,facebook"),
    auto_publish: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from datetime import datetime

    draft = _get_draft(db, draft_id, project)
    if draft:
        scheduled_at = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
        SchedulerService(db, project).schedule_draft(draft, scheduled_at, platforms, auto_publish)
    return RedirectResponse(url="/schedule", status_code=303)


@router.post("/{draft_id}/publish")
def publish_draft(
    draft_id: int,
    platforms: str = Form("linkedin,facebook"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    draft = _get_draft(db, draft_id, project)
    if draft and draft.status != "rejected":
        platform_list = [p.strip() for p in platforms.split(",")]
        PublishService(db, project).publish_draft(draft, platform_list)
    return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)


@router.post("/{draft_id}/mark-linkedin-published")
def mark_linkedin_published(
    draft_id: int,
    external_url: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    draft = _get_draft(db, draft_id, project)
    if draft:
        LinkedInHelper(db, project).mark_manually_published(draft, external_url)
    return RedirectResponse(url="/published", status_code=303)


@router.get("/{draft_id}/download-image")
def download_image(
    draft_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    draft = _get_draft(db, draft_id, project)
    if draft and draft.image_path and Path(draft.image_path).exists():
        return FileResponse(draft.image_path, filename=Path(draft.image_path).name)
    return RedirectResponse(url=f"/drafts/{draft_id}", status_code=303)
