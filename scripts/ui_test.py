"""UI route tests — every page and key form must return without 500."""

import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app

EMAIL = "admin@infrapilot.io"
PASSWORD = "testpass123"


def login(client: TestClient) -> None:
    r = client.post("/login", data={"email": EMAIL, "password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303, f"login failed: {r.status_code}"


def assert_page(name: str, resp, forbidden: tuple[str, ...] = ("Internal Server Error", "UndefinedError")):
    if resp.status_code >= 500:
        raise AssertionError(f"HTTP {resp.status_code}")
    body = resp.text
    for token in forbidden:
        if token in body:
            raise AssertionError(f"response contains '{token}'")


def main() -> int:
    init_db()
    client = TestClient(app)
    failures: list[str] = []
    passed = 0

    def run(name: str, fn):
        nonlocal passed
        try:
            fn()
            passed += 1
            print(f"  OK  {name}")
        except Exception as e:
            failures.append(f"{name}: {e}")
            print(f"  FAIL {name}: {e}")

    login(client)

    for path in ["/dashboard", "/ideas", "/drafts", "/schedule", "/published", "/projects", "/drafts/1"]:
        run(f"GET {path}", lambda p=path: assert_page(p, client.get(p)))

    def test_settings_redirect():
        r = client.get("/settings", follow_redirects=False)
        assert r.status_code == 303
        assert "/projects" in r.headers.get("location", "")

    run("GET /settings redirect", test_settings_redirect)

    def test_automation_save():
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
        assert r.status_code == 303
        assert_page("GET /schedule after save", client.get("/schedule"))

    run("POST /schedule/automation save", test_automation_save)

    def test_review_approve():
        r = client.post("/drafts/1/review", data={"action": "approve_only"}, follow_redirects=False)
        assert r.status_code == 303
        assert_page("GET /drafts/1 after approve", client.get("/drafts/1"))

    run("POST /drafts/1/review approve_only", test_review_approve)

    def test_review_schedule():
        schedule_date = (date.today() + timedelta(days=3)).isoformat()
        r = client.post(
            "/drafts/1/review",
            data={
                "action": "schedule",
                "scheduled_date": schedule_date,
                "scheduled_time": "14:30",
                "platforms": "linkedin,facebook",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert_page("GET /schedule after review schedule", client.get("/schedule"))

    run("POST /drafts/1/review schedule", test_review_schedule)

    def test_idea_create():
        r = client.post(
            "/ideas/create",
            data={
                "title": "UI test idea",
                "topic": "Testing",
                "angle": "Smoke test",
                "target_audience": "Devs",
                "platform_preference": "both",
                "priority": "5",
                "status": "new",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert_page("GET /ideas after create", client.get("/ideas"))

    run("POST /ideas/create", test_idea_create)

    def test_download_image():
        r = client.get("/drafts/1/download-image", follow_redirects=False)
        assert r.status_code in (200, 303)

    run("GET /drafts/1/download-image", test_download_image)

    print(f"\n{passed} passed, {len(failures)} failed")
    for f in failures:
        print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
