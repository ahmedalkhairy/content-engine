"""Image generation provider abstraction."""

import base64
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.services.project_config import ProjectConfig

logger = logging.getLogger(__name__)

# Deprecated preview model names → current stable models
GEMINI_IMAGE_MODEL_ALIASES = {
    "gemini-2.0-flash-preview-image-generation": "gemini-2.5-flash-image",
    "gemini-2.0-flash-exp-image-generation": "gemini-2.5-flash-image",
}

GEMINI_IMAGE_MODEL_FALLBACKS = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image",
]


class ImageProvider(ABC):
    @abstractmethod
    def generate_image(
        self, prompt: str, output_path: str, topic: str = "", brand_name: str = ""
    ) -> str:
        ...


class MockImageProvider(ImageProvider):
    def generate_image(
        self, prompt: str, output_path: str, topic: str = "", brand_name: str = ""
    ) -> str:
        settings = get_settings()
        now = datetime.now()
        full_dir = Path(output_path).parent if output_path else settings.images_dir
        full_dir.mkdir(parents=True, exist_ok=True)
        out = Path(output_path) if output_path else full_dir / f"mock_{now.strftime('%Y%m%d_%H%M%S')}.png"

        size = (1024, 1024)
        bg_color = (10, 22, 40)
        accent = (59, 130, 246)
        text_color = (226, 232, 240)
        muted = (148, 163, 184)
        brand = brand_name or "Content Engine"

        img = Image.new("RGB", size, bg_color)
        draw = ImageDraw.Draw(img)
        self._draw_grid(draw, size)
        self._draw_icons(draw, size, accent)
        self._draw_text(draw, topic or "Content", brand, text_color, muted, size, accent)
        img.save(str(out), "PNG")
        return str(out)

    def _draw_grid(self, draw: ImageDraw.ImageDraw, size: tuple):
        step = 64
        for x in range(0, size[0], step):
            draw.line([(x, 0), (x, size[1])], fill=(30, 45, 70), width=1)
        for y in range(0, size[1], step):
            draw.line([(0, y), (size[0], y)], fill=(30, 45, 70), width=1)

    def _draw_icons(self, draw: ImageDraw.ImageDraw, size: tuple, accent: tuple):
        cx, cy = size[0] // 2, size[1] // 2 - 80
        draw.rounded_rectangle([cx - 120, cy - 60, cx + 120, cy + 60], radius=12, outline=accent, width=3)
        for i in range(3):
            y = cy - 30 + i * 30
            draw.rectangle([cx - 90, y - 8, cx + 90, y + 8], fill=(30, 58, 95))
        draw.ellipse([cx - 200, cy - 180, cx - 80, cy - 100], outline=accent, width=2)
        draw.ellipse([cx - 160, cy - 200, cx - 40, cy - 110], outline=accent, width=2)

    def _draw_text(self, draw, topic, brand, text_color, muted, size, accent):
        try:
            title_font = ImageFont.truetype("arial.ttf", 48)
            topic_font = ImageFont.truetype("arial.ttf", 32)
            brand_font = ImageFont.truetype("arial.ttf", 28)
        except OSError:
            title_font = topic_font = brand_font = ImageFont.load_default()

        draw.text((size[0] // 2, size[1] - 120), brand, fill=accent, anchor="mm", font=brand_font)
        topic_display = topic[:60] + "..." if len(topic) > 60 else topic
        draw.text((size[0] // 2, size[1] - 60), topic_display, fill=text_color, anchor="mm", font=topic_font)
        draw.text((size[0] // 2, 60), "Content", fill=muted, anchor="mm", font=title_font)


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_image(
        self, prompt: str, output_path: str, topic: str = "", brand_name: str = ""
    ) -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024",
                    "response_format": "b64_json",
                },
            )
            response.raise_for_status()
            image_data = base64.b64decode(response.json()["data"][0]["b64_json"])
            out.write_bytes(image_data)
        return str(out)


class GeminiImageProvider(ImageProvider):
    """Google Gemini native image generation via generateContent API."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = GEMINI_IMAGE_MODEL_ALIASES.get(model, model)

    def _models_to_try(self) -> list[str]:
        models = [self.model]
        for fallback in GEMINI_IMAGE_MODEL_FALLBACKS:
            if fallback not in models:
                models.append(fallback)
        return models

    def generate_image(
        self, prompt: str, output_path: str, topic: str = "", brand_name: str = ""
    ) -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []
        for model in self._models_to_try():
            try:
                return self._generate_with_model(model, prompt, out)
            except Exception as e:
                errors.append(f"{model}: {e}")
                logger.warning("Gemini image model %s failed: %s", model, e)

        raise ValueError("Gemini image generation failed. " + " | ".join(errors))

    def _generate_with_model(self, model: str, prompt: str, out: Path) -> str:
        # Image models require v1beta; v1 rejects responseModalities
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

        with httpx.Client(timeout=180) as client:
            response = client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            )
            if response.status_code == 404:
                raise ValueError("Model not found (404)")
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError("No candidates in response")

        for part in candidates[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                out.write_bytes(base64.b64decode(inline["data"]))
                return str(out)

        raise ValueError("Response did not contain image data")


def get_image_provider(config: ProjectConfig) -> ImageProvider:
    provider = config.image_provider.lower()
    if provider == "openai" and config.openai_api_key:
        return OpenAIImageProvider(config.openai_api_key)
    if provider == "gemini" and config.gemini_api_key:
        model = GEMINI_IMAGE_MODEL_ALIASES.get(
            config.gemini_image_model, config.gemini_image_model
        )
        return GeminiImageProvider(config.gemini_api_key, model)
    return MockImageProvider()
