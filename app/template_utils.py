"""Shared Jinja2 templates with project context."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.deps import get_current_project
from app.models import Project, User
from app.services.project_config import resolve_project_config


class AppTemplates(Jinja2Templates):
    def TemplateResponse(self, request: Request, name: str, context: dict, **kwargs):
        db: Session = SessionLocal()
        try:
            if "current_project" not in context:
                try:
                    context["current_project"] = get_current_project(request, db)
                except Exception:
                    from app.services.project_service import ensure_default_project
                    context["current_project"] = ensure_default_project(db)
            context["projects"] = (
                db.query(Project).filter(Project.is_active.is_(True)).order_by(Project.name).all()
            )
            if "config" not in context and context.get("current_project"):
                context["config"] = resolve_project_config(context["current_project"])
        finally:
            db.close()
        return super().TemplateResponse(request, name, context, **kwargs)


templates = AppTemplates(directory=str(Path(__file__).parent / "templates"))
