"""Resolve effective configuration for a project (DB + env fallbacks)."""

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.models import Project


@dataclass
class ProjectConfig:
    project_id: int
    project_name: str
    brand_name: str
    website: str
    product_context: str
    brand_tone: list[str]
    brand_avoid: list[str]
    brand_positioning: list[str]
    default_target_audience: str
    default_hashtags: str

    llm_provider: str
    llm_model: str
    openai_api_key: str
    gemini_api_key: str

    image_provider: str
    gemini_image_model: str

    facebook_page_id: str
    facebook_access_token: str
    linkedin_mode: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_notify_enabled: bool
    telegram_send_link: bool
    telegram_send_linkedin_text: bool
    telegram_send_linkedin_image: bool
    telegram_send_facebook_text: bool
    auto_publish_enabled: bool
    default_timezone: str


def _split_lines(value: str) -> list[str]:
    if not value:
        return []
    return [line.strip().lstrip("- ").strip() for line in value.splitlines() if line.strip()]


DEPRECATED_GEMINI_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
}


def _resolve_llm_model(project: Project, env: Settings) -> str:
    provider = (project.llm_provider or env.llm_provider or "mock").lower()
    model = (project.llm_model or "").strip()
    if provider == "gemini":
        if not model or model.startswith("gpt") or model in DEPRECATED_GEMINI_MODELS:
            return env.gemini_model
        return model
    if provider == "openai":
        if not model or model.startswith("gemini"):
            return env.openai_model
        return model
    return model or env.openai_model


def resolve_project_config(project: Project, env: Settings | None = None) -> ProjectConfig:
    env = env or get_settings()
    return ProjectConfig(
        project_id=project.id,
        project_name=project.name,
        brand_name=project.brand_name or project.name,
        website=project.website,
        product_context=project.product_context,
        brand_tone=_split_lines(project.brand_tone),
        brand_avoid=_split_lines(project.brand_avoid),
        brand_positioning=_split_lines(project.brand_positioning),
        default_target_audience=project.default_target_audience or "Professionals",
        default_hashtags=project.default_hashtags,
        llm_provider=project.llm_provider or env.llm_provider or "mock",
        llm_model=_resolve_llm_model(project, env),
        openai_api_key=project.openai_api_key or env.openai_api_key,
        gemini_api_key=project.gemini_api_key or env.gemini_api_key,
        image_provider=project.image_provider or env.image_provider or "mock",
        gemini_image_model=project.gemini_image_model or env.gemini_image_model,
        facebook_page_id=project.facebook_page_id or env.facebook_page_id,
        facebook_access_token=project.facebook_access_token or env.facebook_access_token,
        linkedin_mode=project.linkedin_mode or env.linkedin_mode,
        telegram_bot_token=project.telegram_bot_token or env.telegram_bot_token,
        telegram_chat_id=project.telegram_chat_id or env.telegram_chat_id,
        telegram_notify_enabled=project.telegram_notify_enabled if project.telegram_notify_enabled is not None else True,
        telegram_send_link=project.telegram_send_link if project.telegram_send_link is not None else True,
        telegram_send_linkedin_text=bool(project.telegram_send_linkedin_text),
        telegram_send_linkedin_image=bool(project.telegram_send_linkedin_image),
        telegram_send_facebook_text=bool(project.telegram_send_facebook_text),
        auto_publish_enabled=project.auto_publish_enabled if project.auto_publish_enabled else env.auto_publish_enabled,
        default_timezone=project.default_timezone or env.default_timezone,
    )
