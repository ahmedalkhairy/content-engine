"""Settings router — redirects to project settings."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.deps import get_current_project, get_current_user
from app.models import Project, User

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def settings_page(
    project: Project = Depends(get_current_project),
    user: User = Depends(get_current_user),
):
    return RedirectResponse(url="/projects", status_code=303)
