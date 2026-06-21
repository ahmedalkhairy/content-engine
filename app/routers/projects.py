"""Projects router."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_project, get_current_user
from app.models import Project, User
from app.services.project_service import slugify
from app.services.seed import seed_database
from app.template_utils import templates

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def projects_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    current_project: Project = Depends(get_current_project),
):
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse(
        request,
        "projects.html",
        {"request": request, "user": user, "current_project": current_project, "projects": projects},
    )


@router.post("/switch")
def switch_project(
    request: Request,
    project_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    if project and project.is_active:
        request.session["project_id"] = project.id
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/create")
def create_project(
    request: Request,
    name: str = Form(...),
    brand_name: str = Form(""),
    website: str = Form(""),
    product_context: str = Form(""),
    default_target_audience: str = Form("Professionals"),
    llm_provider: str = Form("mock"),
    llm_model: str = Form(""),
    image_provider: str = Form("mock"),
    seed_content: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.config import get_settings

    env = get_settings()
    slug = slugify(name)
    base_slug = slug
    counter = 1
    while db.query(Project).filter(Project.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    project = Project(
        name=name,
        slug=slug,
        brand_name=brand_name or name,
        website=website,
        product_context=product_context,
        default_target_audience=default_target_audience,
        llm_provider=llm_provider,
        llm_model=llm_model or (env.gemini_model if llm_provider == "gemini" else env.openai_model),
        image_provider=image_provider,
        gemini_image_model=env.gemini_image_model,
        linkedin_mode="manual",
        default_timezone=env.default_timezone,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    if seed_content in ("true", "True", "on"):
        seed_database(db, project)

    request.session["project_id"] = project.id
    return RedirectResponse(url="/projects", status_code=303)


@router.post("/{project_id}/update")
def update_project(
    project_id: int,
    name: str = Form(...),
    brand_name: str = Form(""),
    website: str = Form(""),
    product_context: str = Form(""),
    brand_tone: str = Form(""),
    brand_avoid: str = Form(""),
    brand_positioning: str = Form(""),
    default_target_audience: str = Form(""),
    default_hashtags: str = Form(""),
    llm_provider: str = Form("mock"),
    llm_model: str = Form(""),
    openai_api_key: str = Form(""),
    gemini_api_key: str = Form(""),
    image_provider: str = Form("mock"),
    gemini_image_model: str = Form(""),
    facebook_page_id: str = Form(""),
    facebook_access_token: str = Form(""),
    linkedin_mode: str = Form("manual"),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    auto_publish_enabled: str = Form("false"),
    default_timezone: str = Form("Asia/Jerusalem"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=303)

    project.name = name
    project.brand_name = brand_name or name
    project.website = website
    project.product_context = product_context
    project.brand_tone = brand_tone
    project.brand_avoid = brand_avoid
    project.brand_positioning = brand_positioning
    project.default_target_audience = default_target_audience
    project.default_hashtags = default_hashtags
    project.llm_provider = llm_provider
    project.llm_model = llm_model
    project.image_provider = image_provider
    project.gemini_image_model = gemini_image_model
    project.facebook_page_id = facebook_page_id
    project.linkedin_mode = linkedin_mode
    project.telegram_chat_id = telegram_chat_id
    project.auto_publish_enabled = auto_publish_enabled in ("true", "True", "on")
    project.default_timezone = default_timezone

    if openai_api_key and openai_api_key != "••••••••":
        project.openai_api_key = openai_api_key
    if gemini_api_key and gemini_api_key != "••••••••":
        project.gemini_api_key = gemini_api_key
    if facebook_access_token and facebook_access_token != "••••••••":
        project.facebook_access_token = facebook_access_token
    if telegram_bot_token and telegram_bot_token != "••••••••":
        project.telegram_bot_token = telegram_bot_token

    db.commit()
    return RedirectResponse(url=f"/projects", status_code=303)
