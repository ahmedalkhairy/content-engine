"""LLM provider abstraction for content generation."""

import json
import re
from abc import ABC, abstractmethod

import httpx

from app.services.project_config import ProjectConfig


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


class GeminiProvider(LLMProvider):
    FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _models_to_try(self) -> list[str]:
        models = [self.model] if self.model else []
        for m in self.FALLBACK_MODELS:
            if m not in models:
                models.append(m)
        return models

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        errors: list[str] = []
        for model in self._models_to_try():
            try:
                return self._generate_with_model(model, system_prompt, user_prompt)
            except Exception as e:
                errors.append(f"{model}: {e}")
        raise ValueError("Gemini text generation failed. " + " | ".join(errors))

    def _generate_with_model(self, model: str, system_prompt: str, user_prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json",
            },
        }
        with httpx.Client(timeout=120) as client:
            response = client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            )
            if response.status_code == 404:
                raise ValueError("Model not found (404)")
            response.raise_for_status()
            data = response.json()
            parts = data["candidates"][0]["content"]["parts"]
            return parts[0]["text"]


class MockLLMProvider(LLMProvider):
    def __init__(self, config: ProjectConfig):
        self.config = config

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        title_match = re.search(r"Title:\s*(.+)", user_prompt)
        topic_match = re.search(r"Topic:\s*(.+)", user_prompt)
        title = title_match.group(1).strip() if title_match else "Content Insight"
        topic = topic_match.group(1).strip() if topic_match else "General"
        brand = self.config.brand_name

        if "facebook" in user_prompt.lower():
            return json.dumps(
                {
                    "facebook_text": (
                        f"{title}\n\n"
                        f"Here's a practical perspective on {topic.lower()}.\n\n"
                        f"{brand} helps teams work smarter with clear, reliable tools. "
                        f"No hype — just useful capabilities that solve real problems.\n\n"
                        f"What challenges are you facing in this area?\n\n"
                        f"#{brand.replace(' ', '')} #Business"
                    ),
                    "hashtags": f"{brand.replace(' ', '')},Business,Marketing",
                    "cta": f"Learn more at {self.config.website or 'our website'}",
                }
            )

        if "image generation prompt" in user_prompt.lower() or (
            "image" in user_prompt.lower() and "image_prompt" in user_prompt.lower()
        ):
            return json.dumps(
                {
                    "image_prompt": (
                        f"Professional dark navy square infographic for {brand}. "
                        f"Topic: {topic}. Modern clean design, minimal text, "
                        f"SaaS aesthetic, LinkedIn post format 1:1."
                    )
                }
            )

        return json.dumps(
            {
                "title": title[:80],
                "linkedin_text": (
                    f"{title}\n\n"
                    f"Many teams struggle with {topic.lower()} — and the usual approaches "
                    f"often create more friction than value.\n\n"
                    f"At {brand}, we focus on practical solutions: clear workflows, "
                    f"reliable outcomes, and tools that fit how you actually work.\n\n"
                    f"What's your experience with {topic.lower()}?\n\n"
                    f"#{brand.replace(' ', '')} #Business #Growth"
                ),
                "hashtags": f"{brand.replace(' ', '')},Business,Growth",
                "cta": f"Explore {brand} at {self.config.website or 'our website'}",
            }
        )


def get_llm_provider(config: ProjectConfig) -> LLMProvider:
    provider = config.llm_provider.lower()
    if provider == "openai" and config.openai_api_key:
        return OpenAIProvider(config.openai_api_key, config.llm_model)
    if provider == "gemini" and config.gemini_api_key:
        return GeminiProvider(config.gemini_api_key, config.llm_model)
    return MockLLMProvider(config)
