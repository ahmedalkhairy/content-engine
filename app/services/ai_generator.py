"""AI content generation service."""

import json
import re

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ContentIdea, GenerationLog, PostDraft, Project
from app.services.image_service import ImageGenerationService
from app.services.llm_provider import get_llm_provider
from app.services.notifications import NotificationService
from app.services.post_branding import finalize_post_text, normalize_website
from app.services.project_config import ProjectConfig, resolve_project_config
from app.services.quality_checker import QualityChecker


class AIGeneratorService:
    def __init__(self, db: Session, project: Project):
        self.db = db
        self.project = project
        self.config = resolve_project_config(project)
        self.settings = get_settings()
        self.quality_checker = QualityChecker()
        self.image_service = ImageGenerationService(db, project)
        self.notifications = NotificationService(self.config)
        self.llm = get_llm_provider(self.config)

    def _load_prompt(self, name: str) -> str:
        path = self.settings.prompts_dir / f"{name}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _parse_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Failed to parse LLM response as JSON: {text[:200]}")

    def _prompt_context(self, idea: ContentIdea) -> dict:
        positioning = self.config.brand_positioning
        one_liner = positioning[0] if positioning else f"{self.config.brand_name} for modern teams"
        website = normalize_website(self.config.website)
        return {
            "brand_name": self.config.brand_name,
            "brand_website": website,
            "brand_positioning_one_liner": one_liner,
            "title": idea.title,
            "topic": idea.topic or idea.title,
            "angle": idea.angle or "",
            "target_audience": idea.target_audience or self.config.default_target_audience,
            "notes": idea.notes or "",
        }

    def _build_system_prompt(self, idea: ContentIdea) -> str:
        ctx = self._prompt_context(idea)
        template = self._load_prompt("system")
        return template.format(
            brand_name=ctx["brand_name"],
            brand_website=ctx["brand_website"],
            brand_tone="\n".join(f"- {t}" for t in self.config.brand_tone) or "- clear and professional",
            brand_avoid="\n".join(f"- {a}" for a in self.config.brand_avoid) or "- hype and overpromising",
            product_context=self.config.product_context or f"{self.config.brand_name} product and services.",
            brand_positioning="\n".join(f"- {p}" for p in self.config.brand_positioning) or "- practical value",
            target_audience=ctx["target_audience"],
        )

    def generate_draft_from_idea(self, idea: ContentIdea) -> PostDraft:
        system_prompt = self._build_system_prompt(idea)
        context = self._prompt_context(idea)
        provider_label = f"{self.config.llm_provider}:{self.config.llm_model}"

        linkedin_prompt = self._load_prompt("linkedin").format(**context)
        linkedin_raw = self.llm.generate(system_prompt, linkedin_prompt)
        linkedin_data = self._parse_json(linkedin_raw)

        log = GenerationLog(
            provider=f"llm:{provider_label}",
            prompt=linkedin_prompt,
            response=linkedin_raw,
            status="success",
        )
        self.db.add(log)

        facebook_prompt = self._load_prompt("facebook").format(**context)
        facebook_raw = self.llm.generate(system_prompt, facebook_prompt)
        facebook_data = self._parse_json(facebook_raw)

        log_fb = GenerationLog(
            provider=f"llm:{provider_label}",
            prompt=facebook_prompt,
            response=facebook_raw,
            status="success",
        )
        self.db.add(log_fb)

        image_prompt_template = self._load_prompt("image").format(**context)
        image_raw = self.llm.generate(system_prompt, image_prompt_template)
        image_data = self._parse_json(image_raw)

        title = linkedin_data.get("title", idea.title)
        linkedin_text = linkedin_data.get("linkedin_text", "")
        facebook_text = facebook_data.get("facebook_text", "")
        hashtags = linkedin_data.get("hashtags", "") or facebook_data.get("hashtags", "")
        cta = linkedin_data.get("cta", "") or facebook_data.get("cta", "")
        image_prompt = image_data.get("image_prompt", "")

        website = normalize_website(self.config.website)
        linkedin_text, cta = finalize_post_text(
            linkedin_text,
            brand_name=self.config.brand_name,
            website=website,
            cta=cta,
            platform="linkedin",
        )
        facebook_text, fb_cta = finalize_post_text(
            facebook_text,
            brand_name=self.config.brand_name,
            website=website,
            cta=facebook_data.get("cta", "") or cta,
            platform="facebook",
        )
        if not cta:
            cta = fb_cta

        quality = self.quality_checker.check(
            title,
            linkedin_text,
            facebook_text,
            hashtags,
            brand_name=self.config.brand_name,
            website=website,
        )

        draft = PostDraft(
            project_id=self.project.id,
            idea_id=idea.id,
            title=title,
            linkedin_text=linkedin_text,
            facebook_text=facebook_text,
            image_prompt=image_prompt,
            hashtags=hashtags,
            cta=cta,
            status="draft",
            quality_warnings=quality.summary,
        )
        self.db.add(draft)
        self.db.flush()

        for log_entry in [log, log_fb]:
            log_entry.draft_id = draft.id

        self.db.commit()
        self.db.refresh(draft)

        try:
            self.image_service.generate_for_draft(draft)
            self.db.refresh(draft)
        except Exception:
            pass

        idea.status = "drafted"
        self.db.commit()

        self.notifications.notify_draft_ready(draft)
        return draft

    def generate_idea(self) -> ContentIdea:
        """Create a new content idea using AI (no manual input required)."""
        recent_titles = [
            row[0]
            for row in (
                self.db.query(ContentIdea.title)
                .filter(ContentIdea.project_id == self.project.id)
                .order_by(ContentIdea.created_at.desc())
                .limit(25)
                .all()
            )
        ]
        recent_draft_titles = [
            row[0]
            for row in (
                self.db.query(PostDraft.title)
                .filter(PostDraft.project_id == self.project.id)
                .order_by(PostDraft.created_at.desc())
                .limit(25)
                .all()
            )
        ]
        recent_topics = recent_titles + recent_draft_titles
        recent_block = "\n".join(f"- {t}" for t in recent_topics[:30]) or "- (none yet)"

        system_prompt = self._load_prompt("system").format(
            brand_name=self.config.brand_name,
            brand_website=normalize_website(self.config.website),
            brand_tone="\n".join(f"- {t}" for t in self.config.brand_tone) or "- clear and professional",
            brand_avoid="\n".join(f"- {a}" for a in self.config.brand_avoid) or "- hype and overpromising",
            product_context=self.config.product_context or f"{self.config.brand_name} product and services.",
            brand_positioning="\n".join(f"- {p}" for p in self.config.brand_positioning) or "- practical value",
            target_audience=self.config.default_target_audience,
        )

        idea_prompt = self._load_prompt("idea").format(
            brand_name=self.config.brand_name,
            target_audience=self.config.default_target_audience,
            product_context=self.config.product_context or f"{self.config.brand_name} product and services.",
            brand_positioning="\n".join(f"- {p}" for p in self.config.brand_positioning) or "- practical value",
            recent_topics=recent_block,
        )

        provider_label = f"{self.config.llm_provider}:{self.config.llm_model}"
        raw = self.llm.generate(system_prompt, idea_prompt)
        data = self._parse_json(raw)

        idea = ContentIdea(
            project_id=self.project.id,
            title=data.get("title", "Untitled idea"),
            topic=data.get("topic", ""),
            angle=data.get("angle", ""),
            target_audience=data.get("target_audience", self.config.default_target_audience),
            notes=data.get("notes", ""),
            status="approved",
            priority=5,
        )
        self.db.add(idea)

        log = GenerationLog(
            provider=f"llm:{provider_label}",
            prompt=idea_prompt,
            response=raw,
            status="success",
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(idea)
        return idea

    def generate_post_from_ai_idea(self) -> PostDraft:
        """Full pipeline: AI idea → AI draft + image → notification."""
        idea = self.generate_idea()
        return self.generate_draft_from_idea(idea)

    def regenerate_text(self, draft: PostDraft) -> PostDraft:
        if not draft.idea:
            raise ValueError("Draft has no associated content idea")
        return self.generate_draft_from_idea(draft.idea)

    def generate_daily(self, count: int = 1) -> list[PostDraft]:
        ideas = (
            self.db.query(ContentIdea)
            .filter(
                ContentIdea.project_id == self.project.id,
                ContentIdea.status.in_(["new", "approved"]),
            )
            .order_by(ContentIdea.priority.desc(), ContentIdea.created_at)
            .limit(count)
            .all()
        )
        return [self.generate_draft_from_idea(idea) for idea in ideas]
