from app.config import get_settings
import httpx

s = get_settings()
models = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
]
for m in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": 'Respond JSON: {"msg":"hi"}'}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    r = httpx.post(url, json=payload, headers={"x-goog-api-key": s.gemini_api_key}, timeout=30)
    print(m, r.status_code, r.text[:80].replace("\n", " "))
