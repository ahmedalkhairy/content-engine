"""Image generation orchestration."""

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GenerationLog, PostDraft, Project
from app.services.image_generator import get_image_provider
from app.services.project_config import resolve_project_config


class ImageGenerationService:
    def __init__(self, db: Session, project: Project):
        self.db = db
        self.project = project
        self.config = resolve_project_config(project)
        self.settings = get_settings()

    _INFOGRAPHIC_PREFIX = (
        "Professional flat vector INFOGRAPHIC for social media. "
        "NOT abstract art. Layout: title header + icon sections + optional chart/steps. "
        "Dark navy #0a1628, blue accent #3b82f6, 1:1 square, bold readable headlines only. "
    )

    def _build_image_prompt(self, draft: PostDraft) -> str:
        base = (draft.image_prompt or draft.title).strip()
        if "infographic" in base.lower():
            return base
        return f"{self._INFOGRAPHIC_PREFIX}\n\n{base}"

    def generate_for_draft(self, draft: PostDraft) -> str:
        now = datetime.now()
        rel_path = (
            Path("storage") / "images" / self.project.slug / str(now.year) / f"{now.month:02d}"
        )
        full_dir = self.settings.storage_dir.parent / rel_path
        full_dir.mkdir(parents=True, exist_ok=True)

        filename = f"draft_{draft.id}_{now.strftime('%Y%m%d_%H%M%S')}.png"
        output_path = str(full_dir / filename)

        provider = get_image_provider(self.config)
        provider_name = self.config.image_provider

        try:
            topic = draft.title
            if draft.idea:
                topic = draft.idea.topic or draft.title

            image_path = provider.generate_image(
                prompt=self._build_image_prompt(draft),
                output_path=output_path,
                topic=topic,
                brand_name=self.config.brand_name,
            )

            log = GenerationLog(
                draft_id=draft.id,
                provider=f"image:{provider_name}",
                prompt=draft.image_prompt,
                response=image_path,
                status="success",
            )
            self.db.add(log)
            draft.image_path = image_path
            self.db.commit()
            return image_path

        except Exception as e:
            log = GenerationLog(
                draft_id=draft.id,
                provider=f"image:{provider_name}",
                prompt=draft.image_prompt,
                status="error",
                error_message=str(e),
            )
            self.db.add(log)
            self.db.commit()
            raise
