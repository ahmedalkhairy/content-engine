"""LinkedIn publishing via local browser (Playwright + saved session)."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from app.config import get_settings
from app.models import PostDraft

logger = logging.getLogger(__name__)


class LinkedInBrowserPublisher:
    """Automate LinkedIn posting using the user's logged-in browser profile."""

    FEED_URL = "https://www.linkedin.com/feed/"

    def __init__(self, headless: bool | None = None):
        self.settings = get_settings()
        self.headless = headless if headless is not None else False
        self.profile_dir = self.settings.storage_dir / "linkedin_profile"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def login_interactive(self) -> None:
        """Open LinkedIn in a visible browser — log in once, session is saved."""
        self._run_browser(login_only=True)

    def publish_draft(self, draft: PostDraft) -> str:
        """Create a LinkedIn post from draft text + image. Returns empty external URL."""
        text = self._compose_post_text(draft)
        image_path = draft.image_path if draft.image_path and Path(draft.image_path).exists() else None
        if not text.strip():
            raise ValueError("Draft has no LinkedIn text")
        self._run_browser(text=text, image_path=image_path)
        return ""

    def _compose_post_text(self, draft: PostDraft) -> str:
        parts = [draft.linkedin_text.strip()]
        if draft.hashtags:
            tags = draft.hashtags.strip()
            if not tags.startswith("#"):
                tags = " ".join(f"#{t.strip().lstrip('#')}" for t in tags.replace(",", " ").split() if t.strip())
            parts.append(tags)
        if draft.cta:
            parts.append(draft.cta.strip())
        return "\n\n".join(p for p in parts if p)

    def _run_browser(
        self,
        *,
        login_only: bool = False,
        text: str = "",
        image_path: str | None = None,
    ) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            ) from e

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(self.FEED_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)

                if login_only:
                    logger.info("LinkedIn login window open — sign in, then close the browser.")
                    page.wait_for_timeout(120000)
                    return

                if "login" in page.url.lower() or "authwall" in page.url.lower():
                    raise RuntimeError(
                        "Not logged in to LinkedIn. Run: python -m app linkedin-login"
                    )

                self._open_composer(page)
                self._fill_text(page, text)
                if image_path:
                    self._upload_image(page, image_path)
                self._click_post(page)
                page.wait_for_timeout(3000)
            except Exception:
                screenshot = self.settings.logs_dir / f"linkedin_error_{int(time.time())}.png"
                self.settings.logs_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(screenshot))
                    logger.exception("LinkedIn browser publish failed (screenshot: %s)", screenshot)
                except Exception:
                    logger.exception("LinkedIn browser publish failed")
                raise
            finally:
                context.close()

    def _open_composer(self, page) -> None:
        selectors = [
            "button.share-box-feed-entry__trigger",
            "div.share-box-feed-entry__top-bar button",
            ".share-box__open",
        ]
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click()
                page.wait_for_timeout(1500)
                return
        btn = page.get_by_role("button", name=re.compile(r"start a post|post", re.I)).first
        if btn.count():
            btn.click()
            page.wait_for_timeout(1500)
            return
        raise RuntimeError("Could not open LinkedIn post composer")

    def _fill_text(self, page, text: str) -> None:
        editor = page.locator('div[role="textbox"][contenteditable="true"]').first
        if not editor.count():
            editor = page.locator('[contenteditable="true"]').first
        editor.wait_for(state="visible", timeout=15000)
        editor.click()
        page.keyboard.type(text, delay=10)

    def _upload_image(self, page, image_path: str) -> None:
        file_input = page.locator('input[type="file"]').first
        if file_input.count():
            file_input.set_input_files(image_path)
            page.wait_for_timeout(3000)
            return
        for label in ("Add a photo", "Add media", "Photo"):
            btn = page.get_by_role("button", name=re.compile(label, re.I)).first
            if btn.count() and btn.is_visible():
                with page.expect_file_chooser(timeout=10000) as fc_info:
                    btn.click()
                fc_info.value.set_files(image_path)
                page.wait_for_timeout(3000)
                return
        logger.warning("Image upload control not found — posting text only")

    def _click_post(self, page) -> None:
        post_btn = page.get_by_role("button", name=re.compile(r"^post$", re.I)).last
        post_btn.wait_for(state="visible", timeout=15000)
        post_btn.click()
