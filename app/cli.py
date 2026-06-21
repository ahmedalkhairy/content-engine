"""Typer CLI commands."""

import getpass
from datetime import datetime

import pytz
import typer
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import ContentIdea, PostDraft, User
from app.services.ai_generator import AIGeneratorService
from app.services.image_service import ImageGenerationService
from app.services.project_service import ensure_default_project, get_project_by_id_or_slug
from app.services.scheduler import PublishService, SchedulerService
from app.services.seed import seed_database

app = typer.Typer(help="Content Engine CLI")
settings = get_settings()


def get_db() -> Session:
    return SessionLocal()


def resolve_project(db: Session, project_id: int | None, project_slug: str | None):
    project = get_project_by_id_or_slug(db, project_id, project_slug)
    if not project:
        project = ensure_default_project(db)
    return project


@app.command("generate-draft")
def generate_draft(
    idea_id: int = typer.Option(..., "--idea-id"),
    project_id: int | None = typer.Option(None, "--project-id"),
    project_slug: str | None = typer.Option(None, "--project-slug"),
):
    """Generate a post draft from a content idea."""
    init_db()
    db = get_db()
    try:
        idea = db.get(ContentIdea, idea_id)
        if not idea:
            typer.echo(f"Idea {idea_id} not found", err=True)
            raise typer.Exit(1)

        project = resolve_project(db, project_id or idea.project_id, project_slug)
        generator = AIGeneratorService(db, project)
        draft = generator.generate_draft_from_idea(idea)
        typer.echo(f"Draft #{draft.id} created: {draft.title}")
        if draft.quality_warnings:
            typer.echo(f"Quality warnings: {draft.quality_warnings}")
    finally:
        db.close()


@app.command("generate-daily")
def generate_daily(
    count: int = typer.Option(1, "--count"),
    project_id: int | None = typer.Option(None, "--project-id"),
    project_slug: str | None = typer.Option(None, "--project-slug"),
):
    """Generate daily content drafts from pending ideas."""
    init_db()
    db = get_db()
    try:
        project = resolve_project(db, project_id, project_slug)
        generator = AIGeneratorService(db, project)
        drafts = generator.generate_daily(count=count)
        if not drafts:
            typer.echo("No pending ideas found")
            return
        for draft in drafts:
            typer.echo(f"Draft #{draft.id}: {draft.title}")
    finally:
        db.close()


@app.command("schedule")
def schedule_draft_cmd(
    draft_id: int = typer.Option(..., "--draft-id"),
    date: str = typer.Option(..., "--date", help='Format: "2026-06-22 10:00"'),
    platforms: str = typer.Option("linkedin,facebook", "--platforms"),
    auto_publish: bool = typer.Option(False, "--auto-publish"),
):
    """Schedule a draft for publishing."""
    init_db()
    db = get_db()
    try:
        draft = db.get(PostDraft, draft_id)
        if not draft:
            typer.echo(f"Draft {draft_id} not found", err=True)
            raise typer.Exit(1)

        project = draft.project or ensure_default_project(db)
        from app.services.project_config import resolve_project_config

        config = resolve_project_config(project)
        tz = pytz.timezone(config.default_timezone)
        scheduled_at = tz.localize(datetime.strptime(date, "%Y-%m-%d %H:%M"))

        scheduled = SchedulerService(db, project).schedule_draft(
            draft, scheduled_at, platforms, auto_publish
        )
        typer.echo(
            f"Scheduled post #{scheduled.id} for {scheduled_at.isoformat()} "
            f"on {platforms} (auto_publish={auto_publish})"
        )
    finally:
        db.close()


@app.command("publish-now")
def publish_now(
    draft_id: int = typer.Option(..., "--draft-id"),
    platforms: str = typer.Option("linkedin,facebook", "--platforms"),
):
    """Publish a draft immediately."""
    init_db()
    db = get_db()
    try:
        draft = db.get(PostDraft, draft_id)
        if not draft:
            typer.echo(f"Draft {draft_id} not found", err=True)
            raise typer.Exit(1)

        if draft.status == "rejected":
            typer.echo("Cannot publish rejected draft", err=True)
            raise typer.Exit(1)

        project = draft.project or ensure_default_project(db)
        platform_list = [p.strip() for p in platforms.split(",")]
        results = PublishService(db, project).publish_draft(draft, platform_list)
        for r in results:
            typer.echo(f"{r.platform}: {r.status}" + (f" - {r.error_message}" if r.error_message else ""))
    finally:
        db.close()


@app.command("run-automation")
def run_automation_cmd(
    project_id: int | None = typer.Option(None, "--project-id"),
    project_slug: str | None = typer.Option(None, "--project-slug"),
    force: bool = typer.Option(True, "--force/--check-only", help="Force run even if not due"),
):
    """Run content automation (generate + schedule) for a project."""
    init_db()
    db = get_db()
    try:
        from app.services.automation import AutomationService

        project = resolve_project(db, project_id, project_slug)
        service = AutomationService(db)
        if not force and not service.should_run(project):
            typer.echo("Automation not due yet")
            raise typer.Exit(0)
        result = service.run_for_project(project, force=force)
        typer.echo(str(result))
    finally:
        db.close()


@app.command("worker")
def worker(interval: int = typer.Option(60, "--interval", help="Check interval in seconds")):
    """Run the scheduler worker loop."""
    init_db()
    db = get_db()
    try:
        SchedulerService(db).run_worker_loop(interval_seconds=interval)
    finally:
        db.close()


@app.command("seed")
def seed(
    project_id: int | None = typer.Option(None, "--project-id"),
    project_slug: str | None = typer.Option(None, "--project-slug"),
):
    """Seed database with categories and sample ideas."""
    init_db()
    db = get_db()
    try:
        project = resolve_project(db, project_id, project_slug)
        stats = seed_database(db, project)
        typer.echo(
            f"Seeded project '{stats['project']}': "
            f"{stats['categories']} categories, {stats['ideas']} ideas"
        )
    finally:
        db.close()


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(None, "--email"),
    password: str = typer.Option(None, "--password"),
):
    """Create an admin user."""
    init_db()
    db = get_db()
    try:
        if not email:
            email = typer.prompt("Email")
        if not password:
            password = getpass.getpass("Password: ")

        existing = db.query(User).filter(User.email == email).first()
        if existing:
            typer.echo(f"User {email} already exists", err=True)
            raise typer.Exit(1)

        user = User(email=email, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        typer.echo(f"Admin user created: {email}")
    finally:
        db.close()


@app.command("telegram-info")
def telegram_info(
    project_id: int | None = typer.Option(None, "--project-id"),
    project_slug: str | None = typer.Option(None, "--project-slug"),
):
    """Show Telegram config and discover chat IDs from recent bot messages."""
    import httpx

    from app.services.project_config import resolve_project_config

    init_db()
    db = get_db()
    try:
        project = resolve_project(db, project_id, project_slug)
        cfg = resolve_project_config(project)
        typer.echo(f"Project: {project.name}")
        typer.echo(f"Bot token: {'set' if cfg.telegram_bot_token else 'MISSING'}")
        typer.echo(f"Chat ID:   {cfg.telegram_chat_id or 'MISSING'}")

        if not cfg.telegram_bot_token:
            typer.echo("\nSet TELEGRAM_BOT_TOKEN in .env or project settings.", err=True)
            raise typer.Exit(1)

        if cfg.telegram_chat_id and cfg.telegram_chat_id.endswith("_bot"):
            typer.echo(
                "\nWARNING: TELEGRAM_CHAT_ID looks like a bot username, not your chat ID.",
                err=True,
            )

        typer.echo("\n1) Open Telegram, find your bot, press Start (or send /start)")
        typer.echo("2) Then run this command again to see your numeric chat ID.\n")

        url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/getUpdates"
        with httpx.Client(timeout=30) as client:
            resp = client.get(url)
            data = resp.json()

        if not data.get("ok"):
            typer.echo(f"getUpdates failed: {data}", err=True)
            raise typer.Exit(1)

        updates = data.get("result", [])
        if not updates:
            typer.echo("No messages yet — send /start to your bot first.")
            raise typer.Exit(0)

        seen: set[str] = set()
        typer.echo("Available chat IDs:")
        for item in updates:
            msg = item.get("message") or item.get("channel_post") or item.get("my_chat_member", {}).get("chat")
            if not msg:
                continue
            chat = msg if "id" in msg else msg.get("chat", {})
            cid = str(chat.get("id", ""))
            if not cid or cid in seen:
                continue
            seen.add(cid)
            label = chat.get("title") or chat.get("username") or chat.get("first_name") or "chat"
            typer.echo(f"  TELEGRAM_CHAT_ID={cid}  ({label}, type={chat.get('type')})")

        typer.echo("\nCopy the numeric ID into .env and restart the server.")
    finally:
        db.close()


@app.command("telegram-test")
def telegram_test(
    project_id: int | None = typer.Option(None, "--project-id"),
    project_slug: str | None = typer.Option(None, "--project-slug"),
):
    """Send a test Telegram notification using current project config."""
    from app.services.notifications import NotificationService
    from app.services.project_config import resolve_project_config

    init_db()
    db = get_db()
    try:
        project = resolve_project(db, project_id, project_slug)
        cfg = resolve_project_config(project)
        svc = NotificationService(cfg)
        if not svc.enabled:
            typer.echo("Telegram not configured (token + chat ID required).", err=True)
            raise typer.Exit(1)
        ok = svc.send("✅ <b>Test notification</b> from Content Engine — Telegram is working.")
        if ok:
            typer.echo("Test message sent successfully.")
        else:
            typer.echo("Failed to send. Run: python -m app telegram-info", err=True)
            raise typer.Exit(1)
    finally:
        db.close()


@app.command("linkedin-login")
def linkedin_login():
    """Open LinkedIn in a browser to save your login session (one-time setup)."""
    from app.services.linkedin_browser import LinkedInBrowserPublisher

    typer.echo("Opening LinkedIn — log in, then close the browser window.")
    LinkedInBrowserPublisher(headless=False).login_interactive()
    typer.echo("Session saved. You can now use LINKEDIN_MODE=browser")


@app.command("linkedin-publish")
def linkedin_publish_cmd(
    draft_id: int = typer.Option(..., "--draft-id"),
    headless: bool = typer.Option(False, "--headless/--visible"),
):
    """Publish a draft to LinkedIn via browser automation."""
    init_db()
    db = get_db()
    try:
        draft = db.get(PostDraft, draft_id)
        if not draft:
            typer.echo(f"Draft {draft_id} not found", err=True)
            raise typer.Exit(1)
        project = draft.project or ensure_default_project(db)
        if resolve_project_config(project).linkedin_mode != "browser":
            typer.echo("Set LINKEDIN_MODE=browser in .env or project settings first.", err=True)
            raise typer.Exit(1)
        result = LinkedInHelper(db, project).publish(draft)
        typer.echo(f"LinkedIn publish result: {result.status}" + (f" — {result.error_message}" if result.error_message else ""))
    finally:
        db.close()


@app.command("regenerate-image")
def regenerate_image_cmd(draft_id: int = typer.Option(..., "--draft-id")):
    """Regenerate image for a draft."""
    init_db()
    db = get_db()
    try:
        draft = db.get(PostDraft, draft_id)
        if not draft:
            typer.echo(f"Draft {draft_id} not found", err=True)
            raise typer.Exit(1)

        project = draft.project or ensure_default_project(db)
        path = ImageGenerationService(db, project).generate_for_draft(draft)
        typer.echo(f"Image generated: {path}")
    finally:
        db.close()


if __name__ == "__main__":
    app()
