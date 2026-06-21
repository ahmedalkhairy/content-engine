from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "production"
    app_secret_key: str = "change-me"
    database_url: str = f"sqlite:///{BASE_DIR / 'storage' / 'infra_content.db'}"

    # LLM providers: openai | gemini | mock
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Image providers: mock | openai | gemini
    image_provider: str = "mock"
    gemini_image_model: str = "gemini-2.5-flash-image"

    facebook_page_id: str = ""
    facebook_access_token: str = ""

    linkedin_mode: str = "manual"
    linkedin_browser_headless: bool = False

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    auto_publish_enabled: bool = False
    default_timezone: str = "Asia/Jerusalem"
    session_cookie_secure: bool = False
    app_public_url: str = "http://localhost:8000"

    @property
    def storage_dir(self) -> Path:
        return BASE_DIR / "storage"

    @property
    def images_dir(self) -> Path:
        return self.storage_dir / "images"

    @property
    def logs_dir(self) -> Path:
        return self.storage_dir / "logs"

    @property
    def brand_file(self) -> Path:
        return BASE_DIR / "brand.yml"

    @property
    def prompts_dir(self) -> Path:
        return BASE_DIR / "prompts"


def get_settings() -> Settings:
    return Settings()
