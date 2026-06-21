"""Content ideas router."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import ContentIdea, Project, User

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.get("")
def ideas_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from app.template_utils import templates

    ideas = (
        db.query(ContentIdea)
        .filter(ContentIdea.project_id == project.id)
        .order_by(ContentIdea.priority.desc(), ContentIdea.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "ideas.html",
        {
            "request": request,
            "user": user,
            "current_project": project,
            "ideas": ideas,
            "generate_error": request.query_params.get("generate_error"),
        },
    )


@router.post("/create")
def create_idea(
    title: str = Form(...),
    topic: str = Form(""),
    angle: str = Form(""),
    target_audience: str = Form(""),
    platform_preference: str = Form("both"),
    priority: int = Form(5),
    status: str = Form("new"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    idea = ContentIdea(
        project_id=project.id,
        title=title,
        topic=topic,
        angle=angle,
        target_audience=target_audience or project.default_target_audience,
        platform_preference=platform_preference,
        priority=priority,
        status=status,
        notes=notes,
    )
    db.add(idea)
    db.commit()
    return RedirectResponse(url="/ideas", status_code=303)


@router.post("/{idea_id}/update")
def update_idea(
    idea_id: int,
    title: str = Form(...),
    topic: str = Form(""),
    angle: str = Form(""),
    target_audience: str = Form(""),
    platform_preference: str = Form("both"),
    priority: int = Form(5),
    status: str = Form("new"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    idea = db.get(ContentIdea, idea_id)
    if idea and idea.project_id == project.id:
        idea.title = title
        idea.topic = topic
        idea.angle = angle
        idea.target_audience = target_audience
        idea.platform_preference = platform_preference
        idea.priority = priority
        idea.status = status
        idea.notes = notes
        db.commit()
    return RedirectResponse(url="/ideas", status_code=303)


@router.post("/{idea_id}/delete")
def delete_idea(
    idea_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    idea = db.get(ContentIdea, idea_id)
    if idea and idea.project_id == project.id:
        db.delete(idea)
        db.commit()
    return RedirectResponse(url="/ideas", status_code=303)


@router.post("/{idea_id}/generate")
def generate_from_idea(
    idea_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    project: Project = Depends(get_current_project),
):
    from urllib.parse import quote

    from app.services.ai_generator import AIGeneratorService

    idea = db.get(ContentIdea, idea_id)
    if idea and idea.project_id == project.id:
        try:
            generator = AIGeneratorService(db, project)
            draft = generator.generate_draft_from_idea(idea)
            return RedirectResponse(url=f"/drafts/{draft.id}", status_code=303)
        except Exception as e:
            msg = quote(str(e)[:300])
            return RedirectResponse(url=f"/ideas?generate_error={msg}", status_code=303)
    return RedirectResponse(url="/ideas", status_code=303)
