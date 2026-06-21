"""Settings management service."""

from sqlalchemy.orm import Session

from app.models import Setting

SENSITIVE_KEYS = {
    "openai_api_key",
    "facebook_access_token",
    "telegram_bot_token",
    "linkedin_access_token",
}


class SettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str, default: str = "") -> str:
        setting = self.db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else default

    def set(self, key: str, value: str, encrypted: bool = False) -> Setting:
        if key in SENSITIVE_KEYS:
            encrypted = True

        setting = self.db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
            setting.encrypted = encrypted
        else:
            setting = Setting(key=key, value=value, encrypted=encrypted)
            self.db.add(setting)
        self.db.commit()
        self.db.refresh(setting)
        return setting

    def get_all(self) -> dict[str, str]:
        settings = self.db.query(Setting).all()
        result = {}
        for s in settings:
            if s.encrypted and s.value:
                result[s.key] = "••••••••"
            else:
                result[s.key] = s.value
        return result

    def get_raw(self, key: str, default: str = "") -> str:
        """Get setting value without masking (for internal use)."""
        setting = self.db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else default

    def bulk_update(self, data: dict[str, str]) -> None:
        for key, value in data.items():
            if value and value != "••••••••":
                self.set(key, value)
