"""Ensure generated posts reference the brand and product URL."""

import re

_STALE_DOMAINS = ("infrapilot.io", "infrapilot.to", "infrapilot.com")
_CORRECT_DOMAIN = "infrapilot.tech"


def normalize_website(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def sanitize_brand_urls(text: str, *, correct_website: str) -> str:
    """Replace hallucinated/wrong InfraPilot domains in post text."""
    if not text:
        return text
    domain = website_domain(correct_website)
    if domain != _CORRECT_DOMAIN:
        return text
    out = text
    for stale in _STALE_DOMAINS:
        out = re.sub(re.escape(stale), _CORRECT_DOMAIN, out, flags=re.IGNORECASE)
    return out


def website_domain(website: str) -> str:
    norm = normalize_website(website)
    return re.sub(r"^https?://", "", norm).rstrip("/").lower()


def text_contains_website(text: str, website: str) -> bool:
    if not website:
        return True
    lower = text.lower()
    domain = website_domain(website)
    norm = normalize_website(website).lower()
    return domain in lower or norm in lower


def text_contains_brand(text: str, brand_name: str) -> bool:
    return brand_name.lower() in text.lower() if brand_name else True


def build_default_cta(brand_name: str, website: str) -> str:
    website = normalize_website(website)
    if website:
        return f"Learn more about {brand_name} → {website}"
    return f"Follow {brand_name} for more infrastructure insights."


def finalize_post_text(
    text: str,
    *,
    brand_name: str,
    website: str,
    cta: str = "",
    platform: str = "linkedin",
) -> tuple[str, str]:
    """
    Guarantee brand + product URL appear in the post body (not only in metadata).
    Returns (final_text, final_cta).
    """
    text = sanitize_brand_urls((text or "").strip(), correct_website=website)
    website = normalize_website(website)
    cta = sanitize_brand_urls((cta or "").strip(), correct_website=website)

    if not cta:
        cta = build_default_cta(brand_name, website)
    elif website and not text_contains_website(cta, website):
        cta = f"{cta} → {website}"

    needs_brand = brand_name and not text_contains_brand(text, brand_name)
    needs_link = website and not text_contains_website(text, website)

    if needs_brand or needs_link:
        parts: list[str] = []
        if needs_brand and needs_link:
            parts.append(f"At {brand_name}, we build tools for exactly this kind of problem.")
        elif needs_brand:
            parts.append(f"— {brand_name}")

        if needs_link:
            parts.append(f"🔗 {cta}")

        footer = "\n".join(parts)
        text = f"{text}\n\n{footer}" if text else footer

    return text.strip(), cta
