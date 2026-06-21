"""End-to-end smoke tests for the Content Engine."""

import sys
from pathlib import Path

import httpx

BASE = "http://localhost:8000"
EMAIL = "admin@infrapilot.io"
PASSWORD = "testpass123"


def main() -> int:
    failures: list[str] = []
    passed: list[str] = []

    client = httpx.Client(base_url=BASE, follow_redirects=True, timeout=60.0)

    def check(name: str, resp: httpx.Response, expect: int | tuple = 200, url_contains: str = ""):
        ok_codes = (expect,) if isinstance(expect, int) else expect
        ok = resp.status_code in ok_codes
        if url_contains and url_contains not in str(resp.url):
            ok = False
        if ok:
            passed.append(name)
        else:
            failures.append(f"{name}: status={resp.status_code} url={resp.url}")

    # Public routes
    check("GET /login", client.get("/login"), 200)

    anon = httpx.Client(base_url=BASE, follow_redirects=True, timeout=60.0)
    r = anon.get("/")
    if r.status_code == 200 and "Insights" in r.text:
        passed.append("GET / (public blog)")
    else:
        failures.append(f"GET / (public blog): status={r.status_code}")
    anon.close()

    # Login
    resp = client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    if "Sign In" in resp.text or "/login" in str(resp.url):
        failures.append(f"POST /login: failed (still on login page)")
    else:
        passed.append("POST /login")

    # Authenticated pages
    for path in ["/dashboard", "/ideas", "/drafts", "/schedule", "/published", "/notifications", "/projects"]:
        r = client.get(path)
        if "Sign In" in r.text:
            failures.append(f"GET {path}: not authenticated (login page shown)")
        elif r.status_code >= 500 or "Internal Server Error" in r.text:
            failures.append(f"GET {path}: status={r.status_code} or server error in body")
        else:
            passed.append(f"GET {path}")

    r = client.get("/settings")
    if "Sign In" in r.text:
        failures.append("GET /settings: not authenticated")
    elif "/projects" in str(r.url) or "Projects" in r.text:
        passed.append("GET /settings -> projects")
    else:
        failures.append(f"GET /settings: unexpected url {r.url}")

    r = client.get("/drafts/1")
    if "Sign In" in r.text:
        failures.append("GET /drafts/1: not authenticated")
    elif r.status_code >= 500 or "Internal Server Error" in r.text:
        failures.append(f"GET /drafts/1: status={r.status_code} or server error")
    else:
        passed.append("GET /drafts/1")

    # Key form POST (must redirect, not 500)
    r = client.post(
        "/schedule/automation",
        data={
            "automation_enabled": "true",
            "automation_interval_days": "1",
            "automation_posts_per_run": "1",
            "automation_spacing_days": "1",
            "automation_publish_time": "10:00",
            "automation_platforms": "linkedin,facebook",
            "automation_auto_publish": "false",
            "automation_auto_generate": "true",
            "automation_require_approval": "true",
        },
        follow_redirects=False,
    )
    if r.status_code == 303:
        passed.append("POST /schedule/automation")
    else:
        failures.append(f"POST /schedule/automation: status={r.status_code}")

    client.close()

    print("=== Smoke Test Results ===")
    for p in passed:
        print(f"  OK  {p}")
    for f in failures:
        print(f"  FAIL {f}")

    print(f"\n{len(passed)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
