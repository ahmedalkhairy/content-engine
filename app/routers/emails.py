"""Email content generation router."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import EmailDraft, Project, User
from app.services.email_generator import EMAIL_TYPE_LABELS, EmailGeneratorService

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("")
def emails_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from app.template_utils import templates

    emails = (
        db.query(EmailDraft)
        .filter(EmailDraft.project_id == project.id)
        .order_by(EmailDraft.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "emails.html",
        {
            "request": request,
            "user": user,
            "current_project": project,
            "emails": emails,
            "email_types": EMAIL_TYPE_LABELS,
            "generate_error": request.query_params.get("generate_error"),
        },
    )


@router.post("/generate")
def generate_email(
    goal: str = Form(...),
    email_type: str = Form("promotional"),
    target_audience: str = Form(""),
    language: str = Form("ar"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    try:
        generator = EmailGeneratorService(db, project)
        email_draft = generator.generate_email(
            goal=goal,
            email_type=email_type,
            target_audience=target_audience or project.default_target_audience,
            language=language,
            notes=notes,
        )
        return RedirectResponse(url=f"/emails/{email_draft.id}", status_code=303)
    except Exception as e:
        msg = quote(str(e)[:300])
        return RedirectResponse(url=f"/emails?generate_error={msg}", status_code=303)


@router.get("/{email_id}")
def email_detail(
    email_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from app.template_utils import templates

    email_draft = db.get(EmailDraft, email_id)
    if not email_draft or email_draft.project_id != project.id:
        return RedirectResponse(url="/emails", status_code=303)

    return templates.TemplateResponse(
        request,
        "email_detail.html",
        {
            "request": request,
            "user": user,
            "current_project": project,
            "email": email_draft,
            "email_types": EMAIL_TYPE_LABELS,
            "flash_msg": request.query_params.get("msg"),
            "generate_error": request.query_params.get("generate_error"),
        },
    )


@router.post("/{email_id}/edit")
def edit_email(
    email_id: int,
    subject: str = Form(""),
    preview_text: str = Form(""),
    body_html: str = Form(""),
    body_plain: str = Form(""),
    goal: str = Form(""),
    email_type: str = Form("promotional"),
    target_audience: str = Form(""),
    language: str = Form("ar"),
    notes: str = Form(""),
    status: str = Form("draft"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    email_draft = db.get(EmailDraft, email_id)
    if email_draft and email_draft.project_id == project.id:
        email_draft.subject = subject
        email_draft.preview_text = preview_text
        email_draft.body_html = body_html
        email_draft.body_plain = body_plain
        email_draft.goal = goal
        email_draft.email_type = email_type
        email_draft.target_audience = target_audience
        email_draft.language = language
        email_draft.notes = notes
        email_draft.status = status
        db.commit()
    return RedirectResponse(url=f"/emails/{email_id}?msg=saved", status_code=303)


@router.post("/{email_id}/regenerate")
def regenerate_email(
    email_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    email_draft = db.get(EmailDraft, email_id)
    if email_draft and email_draft.project_id == project.id:
        try:
            generator = EmailGeneratorService(db, project)
            generator.regenerate_email(email_draft)
            return RedirectResponse(url=f"/emails/{email_id}?msg=regenerated", status_code=303)
        except Exception as e:
            msg = quote(str(e)[:300])
            return RedirectResponse(url=f"/emails/{email_id}?generate_error={msg}", status_code=303)
    return RedirectResponse(url="/emails", status_code=303)


@router.post("/{email_id}/delete")
def delete_email(
    email_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    email_draft = db.get(EmailDraft, email_id)
    if email_draft and email_draft.project_id == project.id:
        db.delete(email_draft)
        db.commit()
    return RedirectResponse(url="/emails", status_code=303)
