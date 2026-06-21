"""Telegram notification service."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from app.config import get_settings
from app.services.project_config import ProjectConfig

if TYPE_CHECKING:
    from app.models import PostDraft

logger = logging.getLogger(__name__)

_NUMERIC_CHAT_ID = re.compile(r"^-?\d+$")
_LOCALHOST = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?", re.I)
_MAX_MESSAGE_LEN = 4096


class NotificationService:
    def __init__(self, config: ProjectConfig | None = None):
        self.config = config
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        if not self.config:
            return False
        if not self.config.telegram_notify_enabled:
            return False
        return bool(self.config.telegram_bot_token and self.config.telegram_chat_id)

    @property
    def _api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.config.telegram_bot_token}"

    def _chat_id(self) -> str | None:
        if not self.config:
            return None
        return self._normalize_chat_id(self.config.telegram_chat_id)

    def send(
        self,
        message: str,
        button_url: str | None = None,
        button_text: str = "Open draft",
        parse_mode: str | None = "HTML",
    ) -> bool:
        if not self.enabled or not self.config:
            logger.warning("Telegram notification skipped: not configured or disabled")
            return False

        chat_id = self._chat_id()
        if not chat_id:
            logger.error(
                "Invalid TELEGRAM_CHAT_ID=%r — run: python -m app telegram-info",
                self.config.telegram_chat_id,
            )
            return False

        payload: dict = {
            "chat_id": chat_id,
            "text": message[:_MAX_MESSAGE_LEN],
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if button_url and not _LOCALHOST.search(button_url):
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": button_text, "url": button_url}]]
            }

        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(f"{self._api_base}/sendMessage", json=payload)
                if response.status_code == 200:
                    return True
                data = response.json() if response.content else {}
                logger.error(
                    "Telegram send failed (HTTP %s): %s",
                    response.status_code,
                    data.get("description", response.text[:200]),
                )
                return False
        except Exception:
            logger.exception("Telegram send failed")
            return False

    def send_plain_chunks(self, text: str, header: str = "") -> bool:
        """Send plain text (easy to copy in Telegram). Splits long messages."""
        if not self.enabled:
            return False
        body = (text or "").strip()
        if not body:
            return False
        chunks = self._split_text(body, _MAX_MESSAGE_LEN - 50)
        ok = True
        for i, chunk in enumerate(chunks):
            prefix = header if i == 0 else f"{header} ({i + 1}/{len(chunks)})\n\n" if header else ""
            if not self.send(prefix + chunk, parse_mode=None):
                ok = False
        return ok

    def send_photo(self, image_path: str, caption: str = "") -> bool:
        if not self.enabled or not self.config:
            return False
        chat_id = self._chat_id()
        if not chat_id:
            return False
        path = Path(image_path)
        if not path.exists():
            logger.warning("Telegram photo skipped: file not found %s", image_path)
            return False

        try:
            with httpx.Client(timeout=120) as client, path.open("rb") as img:
                response = client.post(
                    f"{self._api_base}/sendPhoto",
                    data={"chat_id": chat_id, "caption": (caption or "")[:1024]},
                    files={"photo": (path.name, img, "image/jpeg")},
                )
                if response.status_code == 200:
                    return True
                data = response.json() if response.content else {}
                logger.error(
                    "Telegram photo failed (HTTP %s): %s",
                    response.status_code,
                    data.get("description", response.text[:200]),
                )
                return False
        except Exception:
            logger.exception("Telegram photo send failed")
            return False

    @staticmethod
    def _split_text(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n\n", 0, max_len)
            if split_at < max_len // 2:
                split_at = remaining.rfind("\n", 0, max_len)
            if split_at < max_len // 2:
                split_at = max_len
            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()
        return chunks

    @staticmethod
    def _normalize_chat_id(value: str) -> str | None:
        raw = (value or "").strip()
        if not raw:
            return None
        if raw.startswith("@"):
            return raw
        if _NUMERIC_CHAT_ID.match(raw):
            return raw
        if re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$", raw) and raw.endswith("_bot"):
            return None
        return raw

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            (text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _draft_review_url(self, draft_id: int) -> str:
        base = (self.settings.app_public_url or "http://localhost:8000").rstrip("/")
        return f"{base}/drafts/{draft_id}"

    def _compose_linkedin_text(self, draft: PostDraft) -> str:
        parts = [draft.linkedin_text.strip()]
        if draft.hashtags:
            tags = draft.hashtags.strip()
            if not tags.startswith("#"):
                tags = " ".join(f"#{t.strip().lstrip('#')}" for t in tags.replace(",", " ").split() if t.strip())
            parts.append(tags)
        if draft.cta:
            parts.append(draft.cta.strip())
        return "\n\n".join(p for p in parts if p)

    def notify_draft_ready(self, draft: PostDraft):
        if not self.enabled or not self.config:
            return

        brand = self._escape_html(self.config.brand_name)
        safe_title = self._escape_html(draft.title)
        button_url = None

        if self.config.telegram_send_link:
            msg = f"📝 <b>منشور جديد جاهز للمراجعة — {brand}</b>\n\n{safe_title}"
            url = self._draft_review_url(draft.id)
            msg += f"\n\n🔗 {url}"
            if _LOCALHOST.search(url):
                msg += (
                    "\n\n<i>ملاحظة: localhost ما بيفتح من الموبايل. "
                    "حط APP_PUBLIC_URL في .env.</i>"
                )
            else:
                button_url = url
            self.send(msg, button_url=button_url, button_text="افتح في المنصة")

        if self.config.telegram_send_linkedin_text:
            linkedin_body = self._compose_linkedin_text(draft)
            if linkedin_body:
                self.send_plain_chunks(
                    linkedin_body,
                    header="📋 LinkedIn — انسخ والصق:\n\n",
                )

        if self.config.telegram_send_facebook_text and draft.facebook_text.strip():
            self.send_plain_chunks(
                draft.facebook_text.strip(),
                header="📘 Facebook — انسخ والصق:\n\n",
            )

        if self.config.telegram_send_linkedin_image and draft.image_path:
            caption = f"LinkedIn image — {draft.title}"[:1024]
            self.send_photo(draft.image_path, caption=caption)

    def notify_published(self, platform: str, title: str, url: str = ""):
        msg = f"✅ <b>Post published successfully.</b>\n\nPlatform: {platform}\nTitle: {title}"
        if url:
            msg += f"\nURL: {url}"
        self.send(msg)

    def notify_publish_failed(self, platform: str, title: str, error: str):
        self.send(
            f"❌ <b>Publishing failed.</b>\n\n"
            f"Platform: {platform}\nTitle: {title}\nError: {error[:500]}"
        )

    def notify_ready_to_publish(self, title: str):
        self.send(f"📋 <b>Post ready for manual publishing.</b>\n\n{title}")
