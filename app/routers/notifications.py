"""Telegram notification settings."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import Project, User
from app.services.notifications import NotificationService
from app.services.project_config import resolve_project_config
from app.template_utils import templates

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def notifications_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    config = resolve_project_config(project)
    return templates.TemplateResponse(
        request,
        "notifications.html",
        {
            "request": request,
            "user": user,
            "current_project": project,
            "config": config,
            "message": request.query_params.get("msg"),
        },
    )


@router.post("")
def save_notifications(
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    telegram_notify_enabled: str = Form("false"),
    telegram_send_link: str = Form("true"),
    telegram_send_linkedin_text: str = Form("false"),
    telegram_send_linkedin_image: str = Form("false"),
    telegram_send_facebook_text: str = Form("false"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    project.telegram_notify_enabled = telegram_notify_enabled.lower() in ("true", "1", "on", "yes")
    project.telegram_send_link = telegram_send_link.lower() in ("true", "1", "on", "yes")
    project.telegram_send_linkedin_text = telegram_send_linkedin_text.lower() in ("true", "1", "on", "yes")
    project.telegram_send_linkedin_image = telegram_send_linkedin_image.lower() in ("true", "1", "on", "yes")
    project.telegram_send_facebook_text = telegram_send_facebook_text.lower() in ("true", "1", "on", "yes")
    project.telegram_chat_id = telegram_chat_id.strip()

    if telegram_bot_token and telegram_bot_token != "••••••••":
        project.telegram_bot_token = telegram_bot_token

    db.commit()
    return RedirectResponse(url="/notifications?msg=Settings+saved", status_code=303)


@router.post("/test")
def test_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from app.models import PostDraft

    config = resolve_project_config(project)
    svc = NotificationService(config)
    draft = (
        db.query(PostDraft)
        .filter(PostDraft.project_id == project.id)
        .order_by(PostDraft.created_at.desc())
        .first()
    )
    if draft:
        svc.notify_draft_ready(draft)
        msg = "Test+sent+using+latest+draft"
    else:
        ok = svc.send("✅ <b>Test notification</b> — Telegram is connected.")
        msg = "Test+sent" if ok else "Test+failed"
    return RedirectResponse(url=f"/notifications?msg={msg}", status_code=303)
