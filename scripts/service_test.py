"""Service-level smoke tests."""

from pathlib import Path

from app.auth import verify_password
from app.database import SessionLocal, init_db
from app.models import PostDraft, Project, User
from app.services.image_generator import get_image_provider
from app.services.image_service import ImageGenerationService
from app.services.llm_provider import get_llm_provider
from app.services.project_config import resolve_project_config
from app.services.quality_checker import QualityChecker
from app.services.scheduler import SchedulerService


def main() -> int:
    init_db()
    db = SessionLocal()
    errors: list[str] = []

    user = db.query(User).first()
    if not user or not verify_password("testpass123", user.password_hash):
        errors.append("auth: login credentials invalid")

    project = db.query(Project).first()
    if not project:
        errors.append("no project found")
        db.close()
        return 1

    cfg = resolve_project_config(project)
    if not cfg.brand_name:
        errors.append("project config missing brand_name")

    try:
        llm = get_llm_provider(cfg)
        raw = llm.generate(
            "You are a writer. Respond in JSON only.",
            'Write JSON: {"title":"Test","linkedin_text":"Server security matters for DevOps teams. InfraPilot helps.","hashtags":"DevOps","cta":"Learn more"}',
        )
        if not raw:
            errors.append("llm: empty response")
    except Exception as e:
        errors.append(f"llm: {e}")

    try:
        provider = get_image_provider(cfg)
        out = Path("storage/images/_smoke_test.png")
        path = provider.generate_image(
            "Professional dark navy square SaaS infographic, minimal text",
            str(out),
            topic="Smoke Test",
            brand_name=cfg.brand_name,
        )
        if not Path(path).exists():
            errors.append("image: file not created")
    except Exception as e:
        errors.append(f"image: {e}")

    QualityChecker().check("T", "hello infrapilot server security", "fb", "a,b", cfg.brand_name)
    SchedulerService(db)

    draft = db.query(PostDraft).first()
    if draft:
        try:
            ImageGenerationService(db, project).generate_for_draft(draft)
        except Exception as e:
            errors.append(f"draft image regen: {e}")
    else:
        errors.append("no draft to test")

    db.close()

    if errors:
        print("FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("All service checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
