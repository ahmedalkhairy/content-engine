"""Email content generation service."""

import json
import re

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailDraft, GenerationLog, Project
from app.services.llm_provider import get_llm_provider
from app.services.post_branding import normalize_website
from app.services.project_config import resolve_project_config

EMAIL_TYPE_LABELS = {
    "promotional": "Promotional / ترويجي",
    "onboarding": "Onboarding / ترحيب",
    "account_activation": "Account activation / تفعيل حساب",
    "server_setup": "Server setup / إضافة سيرفرات",
    "re_engagement": "Re-engagement / إعادة تفاعل",
    "announcement": "Announcement / إعلان",
    "other": "Other / أخرى",
}

LANGUAGE_LABELS = {
    "ar": "Arabic / العربية",
    "en": "English",
}


class EmailGeneratorService:
    def __init__(self, db: Session, project: Project):
        self.db = db
        self.project = project
        self.config = resolve_project_config(project)
        self.settings = get_settings()
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

    def _build_system_prompt(self, target_audience: str) -> str:
        template = self._load_prompt("email_system")
        return template.format(
            brand_name=self.config.brand_name,
            brand_website=normalize_website(self.config.website),
            brand_tone="\n".join(f"- {t}" for t in self.config.brand_tone) or "- clear and professional",
            brand_avoid="\n".join(f"- {a}" for a in self.config.brand_avoid) or "- hype and overpromising",
            product_context=self.config.product_context or f"{self.config.brand_name} product and services.",
            brand_positioning="\n".join(f"- {p}" for p in self.config.brand_positioning) or "- practical value",
            target_audience=target_audience or self.config.default_target_audience,
        )

    def generate_email(
        self,
        goal: str,
        email_type: str = "promotional",
        target_audience: str = "",
        language: str = "ar",
        notes: str = "",
    ) -> EmailDraft:
        audience = target_audience or self.config.default_target_audience
        positioning = self.config.brand_positioning
        one_liner = positioning[0] if positioning else f"{self.config.brand_name} for modern teams"
        website = normalize_website(self.config.website)

        system_prompt = self._build_system_prompt(audience)
        email_prompt = self._load_prompt("email").format(
            goal=goal,
            email_type=EMAIL_TYPE_LABELS.get(email_type, email_type),
            target_audience=audience,
            language_label=LANGUAGE_LABELS.get(language, language),
            notes=notes or "(none)",
            brand_website=website,
            brand_positioning_one_liner=one_liner,
        )

        provider_label = f"{self.config.llm_provider}:{self.config.llm_model}"
        raw = self.llm.generate(system_prompt, email_prompt)
        data = self._parse_json(raw)

        email_draft = EmailDraft(
            project_id=self.project.id,
            goal=goal,
            email_type=email_type,
            target_audience=audience,
            language=language,
            notes=notes,
            subject=data.get("subject", ""),
            preview_text=data.get("preview_text", ""),
            body_html=data.get("body_html", ""),
            body_plain=data.get("body_plain", ""),
            status="draft",
        )
        self.db.add(email_draft)
        self.db.flush()

        log = GenerationLog(
            email_draft_id=email_draft.id,
            provider=f"llm:{provider_label}",
            prompt=email_prompt,
            response=raw,
            status="success",
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(email_draft)
        return email_draft

    def regenerate_email(self, email_draft: EmailDraft) -> EmailDraft:
        audience = email_draft.target_audience or self.config.default_target_audience
        positioning = self.config.brand_positioning
        one_liner = positioning[0] if positioning else f"{self.config.brand_name} for modern teams"
        website = normalize_website(self.config.website)

        system_prompt = self._build_system_prompt(audience)
        email_prompt = self._load_prompt("email").format(
            goal=email_draft.goal,
            email_type=EMAIL_TYPE_LABELS.get(email_draft.email_type, email_draft.email_type),
            target_audience=audience,
            language_label=LANGUAGE_LABELS.get(email_draft.language, email_draft.language),
            notes=email_draft.notes or "(none)",
            brand_website=website,
            brand_positioning_one_liner=one_liner,
        )

        provider_label = f"{self.config.llm_provider}:{self.config.llm_model}"
        raw = self.llm.generate(system_prompt, email_prompt)
        data = self._parse_json(raw)

        email_draft.subject = data.get("subject", "")
        email_draft.preview_text = data.get("preview_text", "")
        email_draft.body_html = data.get("body_html", "")
        email_draft.body_plain = data.get("body_plain", "")

        log = GenerationLog(
            email_draft_id=email_draft.id,
            provider=f"llm:{provider_label}",
            prompt=email_prompt,
            response=raw,
            status="success",
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(email_draft)
        return email_draft
