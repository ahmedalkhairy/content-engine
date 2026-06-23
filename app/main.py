"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.deps import AuthRedirect
from app.log_config import configure_logging
from app.routers import blog, dashboard, drafts, emails, ideas, notifications, projects, published, schedule, settings as settings_router

settings = get_settings()
configure_logging()

app = FastAPI(title="Content Engine", version="1.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="infra_session",
    max_age=86400 * 7,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(blog.router)
app.include_router(notifications.router)
app.include_router(projects.router)
app.include_router(dashboard.router)
app.include_router(ideas.router)
app.include_router(emails.router)
app.include_router(drafts.router)
app.include_router(schedule.router)
app.include_router(published.router)
app.include_router(settings_router.router)


@app.exception_handler(AuthRedirect)
async def auth_redirect_handler(request: Request, exc: AuthRedirect):
    return RedirectResponse(url=exc.url, status_code=303)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login")
def login_page(request: Request):
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request):
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

    from app.auth import verify_password
    from app.database import SessionLocal
    from app.models import User

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            return templates.TemplateResponse(
                request, "login.html", {"request": request, "error": "Invalid email or password"}
            )
        request.session["user_id"] = user.id
        return RedirectResponse(url="/dashboard", status_code=303)
    finally:
        db.close()


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
