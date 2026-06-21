"""Quality checker for generated post content."""

import re

BUZZWORDS = [
    "revolutionary",
    "game-changing",
    "disruptive",
    "synergy",
    "leverage",
    "paradigm",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "next-level",
    "unlock",
    "supercharge",
    "unparalleled",
    "seamless",
]

EXAGGERATED_CLAIMS = [
    r"100\s*%\s*secure",
    r"completely\s+safe",
    r"zero\s+risk",
    r"never\s+fail",
    r"guaranteed",
    r"impossible\s+to\s+hack",
    r"bulletproof",
    r"foolproof",
    r"always\s+available",
    r"no\s+downtime\s+ever",
]


class QualityResult:
    def __init__(self):
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.passed: bool = True

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False

    @property
    def summary(self) -> str:
        items = self.errors + self.warnings
        return "; ".join(items) if items else ""


class QualityChecker:
    def check(
        self,
        title: str,
        linkedin_text: str,
        facebook_text: str,
        hashtags: str,
        brand_name: str = "",
        website: str = "",
    ) -> QualityResult:
        result = QualityResult()
        combined = f"{linkedin_text} {facebook_text}".lower()

        self._check_brand_mentions(combined, result, brand_name)
        self._check_website_link(f"{linkedin_text} {facebook_text}", result, website)
        self._check_hashtags(hashtags, result)
        self._check_exaggerated_claims(combined, result)
        self._check_buzzwords(combined, result)
        self._check_hook(linkedin_text, result)
        self._check_value(linkedin_text, facebook_text, result)
        self._check_generic(combined, result)
        self._check_word_counts(linkedin_text, facebook_text, result)
        self._check_engagement(linkedin_text, result)

        return result

    def _check_brand_mentions(self, text: str, result: QualityResult, brand_name: str):
        if not brand_name:
            return
        brand_lower = brand_name.lower()
        count = text.count(brand_lower)
        if count > 3:
            result.add_warning(f"{brand_name} mentioned {count} times (recommended: 1-2)")
        if count == 0:
            result.add_warning(f"{brand_name} is not mentioned in the post")

    def _check_website_link(self, text: str, result: QualityResult, website: str):
        if not website:
            result.add_warning("Project website not configured — add it in Projects settings")
            return
        from app.services.post_branding import text_contains_website

        if not text_contains_website(text, website):
            result.add_error(f"Product URL ({website}) missing from post")

    def _check_hashtags(self, hashtags: str, result: QualityResult):
        tags = [t.strip() for t in hashtags.split(",") if t.strip()]
        if len(tags) > 8:
            result.add_warning(f"Too many hashtags ({len(tags)}). Recommended: 3-5")
        if len(tags) == 0:
            result.add_warning("No hashtags provided")

    def _check_exaggerated_claims(self, text: str, result: QualityResult):
        for pattern in EXAGGERATED_CLAIMS:
            if re.search(pattern, text, re.IGNORECASE):
                result.add_error(f"Exaggerated claim detected: matches '{pattern}'")

    def _check_buzzwords(self, text: str, result: QualityResult):
        found = [w for w in BUZZWORDS if w in text]
        if len(found) >= 3:
            result.add_warning(f"Too much buzzword language: {', '.join(found[:5])}")

    def _check_hook(self, linkedin_text: str, result: QualityResult):
        first_line = linkedin_text.strip().split("\n")[0] if linkedin_text else ""
        if len(first_line) < 15:
            result.add_warning("LinkedIn hook (first line) may be too short or missing")
        generic_hooks = [
            "in today's world",
            "in today's fast-paced",
            "are you tired of",
            "did you know that",
        ]
        if any(h in first_line.lower() for h in generic_hooks):
            result.add_warning("LinkedIn hook sounds generic")

    def _check_value(self, linkedin_text: str, facebook_text: str, result: QualityResult):
        combined = f"{linkedin_text} {facebook_text}".lower()
        if len(combined.split()) < 40:
            result.add_warning("Post may lack clear value proposition")

    def _check_generic(self, text: str, result: QualityResult):
        generic_phrases = [
            "in conclusion",
            "it goes without saying",
            "at the end of the day",
            "in this day and age",
            "it's important to note",
            "as we all know",
        ]
        found = [p for p in generic_phrases if p in text]
        if found:
            result.add_warning(f"Generic AI-sounding phrases detected: {', '.join(found)}")

    def _check_word_counts(self, linkedin_text: str, facebook_text: str, result: QualityResult):
        li_words = len(linkedin_text.split())
        fb_words = len(facebook_text.split())
        if li_words < 50:
            result.add_warning(f"LinkedIn post is short ({li_words} words, target: 70-130)")
        if li_words > 180:
            result.add_warning(f"LinkedIn post is long ({li_words} words, target: 70-130)")
        if fb_words < 35:
            result.add_warning(f"Facebook post is short ({fb_words} words, target: 50-100)")
        if fb_words > 140:
            result.add_warning(f"Facebook post is long ({fb_words} words, target: 50-100)")

    def _check_engagement(self, linkedin_text: str, result: QualityResult):
        if not linkedin_text.strip():
            return
        if "?" not in linkedin_text and not any(
            w in linkedin_text.lower() for w in ("what", "how", "why", "you", "your")
        ):
            result.add_warning("Post may lack an engagement hook or question")
        emoji_pattern = re.compile(
            "["
            "\U0001F300-\U0001F9FF"
            "\U00002600-\U000026FF"
            "\U00002700-\U000027BF"
            "]+",
            flags=re.UNICODE,
        )
        if not emoji_pattern.search(linkedin_text):
            result.add_warning("Consider adding 2-3 emojis for LinkedIn readability")
