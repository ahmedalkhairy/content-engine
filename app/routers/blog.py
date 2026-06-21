"""Public blog routes (SEO landing + post pages)."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.blog_service import (
    canonical_external_url,
    excerpt,
    get_blog_project,
    get_public_post,
    list_public_posts,
    post_body,
)
from app.services.project_service import get_project_by_id_or_slug

router = APIRouter(tags=["blog"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.filters["tojson"] = json.dumps
settings = get_settings()


def _public_context(request: Request, project, **extra) -> dict:
    return {
        "request": request,
        "project": project,
        "site_url": settings.app_public_url.rstrip("/"),
        "brand_name": project.brand_name or project.name,
        "brand_website": project.website or "https://infrapilot.io",
        **extra,
    }


def _blog_project(db: Session):
    project = get_blog_project(db, settings.public_blog_project_slug)
    if not project:
        project = get_project_by_id_or_slug(db, slug=settings.public_blog_project_slug)
    return project


@router.get("/")
def blog_home(request: Request, db: Session = Depends(get_db)):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)

    project = _blog_project(db)
    if not project:
        return RedirectResponse(url="/login", status_code=303)

    posts = list_public_posts(db, project)
    ctx = _public_context(
        request,
        project,
        posts=posts,
        page_title=f"{project.brand_name or project.name} — Insights",
        meta_description=(
            f"Articles on server management, DevOps, and infrastructure from "
            f"{project.brand_name or project.name}."
        ),
    )
    return templates.TemplateResponse(request, "blog_index.html", ctx)


@router.get("/blog/{slug}")
def blog_post(slug: str, request: Request, db: Session = Depends(get_db)):
    project = _blog_project(db)
    if not project:
        raise HTTPException(status_code=404)

    draft = get_public_post(db, project, slug)
    if not draft:
        raise HTTPException(status_code=404)

    body = post_body(draft)
    canonical = canonical_external_url(draft)
    ctx = _public_context(
        request,
        project,
        draft=draft,
        body=body,
        body_excerpt=excerpt(body, 160),
        canonical_url=canonical,
        page_title=draft.title,
        meta_description=excerpt(body, 155),
        image_url=f"{settings.app_public_url.rstrip('/')}/blog/{slug}/image" if draft.image_path else "",
    )
    return templates.TemplateResponse(request, "blog_post.html", ctx)


@router.get("/blog/{slug}/image")
def blog_post_image(slug: str, db: Session = Depends(get_db)):
    project = _blog_project(db)
    if not project:
        raise HTTPException(status_code=404)

    draft = get_public_post(db, project, slug)
    if not draft or not draft.image_path:
        raise HTTPException(status_code=404)

    path = Path(draft.image_path)
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, filename=path.name)


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    base = settings.app_public_url.rstrip("/")
    return PlainTextResponse(
        f"User-agent: *\nAllow: /\nDisallow: /dashboard\nDisallow: /drafts\n"
        f"Disallow: /ideas\nDisallow: /schedule\nDisallow: /published\n"
        f"Disallow: /projects\nDisallow: /notifications\nDisallow: /settings\n"
        f"Disallow: /login\n\nSitemap: {base}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
def sitemap_xml(request: Request, db: Session = Depends(get_db)):
    project = _blog_project(db)
    base = settings.app_public_url.rstrip("/")
    urls = [f"  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>"]

    if project:
        for draft in list_public_posts(db, project, limit=500):
            urls.append(
                f"  <url><loc>{base}/blog/{draft.blog_slug}</loc>"
                f"<changefreq>monthly</changefreq><priority>0.8</priority></url>"
            )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
