from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, User
from app.services.project_service import ensure_default_project


class AuthRedirect(Exception):
    def __init__(self, url: str = "/login"):
        self.url = url


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise AuthRedirect()
    user = db.get(User, user_id)
    if not user:
        raise AuthRedirect()
    return user


def get_current_project(request: Request, db: Session = Depends(get_db)) -> Project:
    project_id = request.session.get("project_id")
    if project_id:
        project = db.get(Project, project_id)
        if project and project.is_active:
            return project
    project = ensure_default_project(db)
    request.session["project_id"] = project.id
    return project


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)
