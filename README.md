# Content Engine

A self-hosted Python content automation engine that generates, manages, schedules, and publishes marketing content for Facebook and LinkedIn — for **any product or brand**. Includes multi-project support and AI providers (OpenAI, Google Gemini, or mock mode).

## Features

- **Multi-Project Support** — Run InfraPilot, client brands, or any SaaS from one install
- **Content Ideas Management** — Track topics, angles, and priorities per project
- **AI Post Generation** — OpenAI, Google Gemini, or mock mode
- **AI Image Generation** — Mock PIL, OpenAI DALL-E, or Google Gemini
- **Post Review Queue** — Approve, reject, edit, regenerate
- **Scheduling** — Calendar-based publishing with auto/manual modes
- **Facebook Publishing** — Graph API integration
- **LinkedIn Manual Helper** — Copy text, download image, publishing checklist
- **Telegram Notifications** — Optional alerts for drafts and publishing
- **Admin Dashboard** — Dark SaaS-style web UI with authentication

## Requirements

- Python 3.11+
- Linux server (recommended for production)
- Optional: OpenAI API key, Google Gemini API key, Facebook Page credentials, Telegram bot

## Quick Start

### 1. Clone and install

```bash
cd infra-content-engine
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
APP_SECRET_KEY=your-random-secret-key-here
DATABASE_URL=sqlite:///./storage/infra_content.db
OPENAI_API_KEY=sk-...          # Optional
GEMINI_API_KEY=AI...           # Optional — get from Google AI Studio
LLM_PROVIDER=mock              # openai | gemini | mock
IMAGE_PROVIDER=mock            # openai | gemini | mock
GEMINI_MODEL=gemini-2.0-flash
GEMINI_IMAGE_MODEL=gemini-2.0-flash-preview-image-generation
AUTO_PUBLISH_ENABLED=false      # Keep false until ready
DEFAULT_TIMEZONE=Asia/Jerusalem
```

### 3. Initialize database

```bash
python -m app seed
python -m app create-admin --email admin@example.com --password yourpassword
```

### 4. Generate a test draft

```bash
python -m app generate-draft --idea-id 1
```

### 5. Start the dashboard

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and log in.

### 6. Start the scheduler worker

In a separate terminal:

```bash
python -m app worker
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m app seed` | Seed categories and sample ideas |
| `python -m app create-admin` | Create admin user |
| `python -m app generate-draft --idea-id 1` | Generate draft from idea |
| `python -m app generate-daily` | Generate drafts from pending ideas |
| `python -m app schedule --draft-id 1 --date "2026-06-22 10:00" --platforms linkedin,facebook` | Schedule a post |
| `python -m app publish-now --draft-id 1` | Publish immediately |
| `python -m app regenerate-image --draft-id 1` | Regenerate image |
| `python -m app worker` | Run scheduler worker loop |

Add `--project-id` or `--project-slug` to seed, generate-daily, etc.

## Multi-Project Usage

Each project has its own brand voice, ideas, drafts, API keys, and publishing settings.

1. Open **Projects** in the dashboard
2. Create a new project (name, brand, product context)
3. Configure LLM/image providers per project
4. Use the **project switcher** in the sidebar to change context
5. Seed ideas: `python -m app seed --project-slug my-product`

Existing InfraPilot data is migrated to a default **InfraPilot** project on startup.

## Google Gemini Setup

1. Get an API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Set globally in `.env` or per project in **Projects** page:

```env
GEMINI_API_KEY=AI...
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.0-flash
IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.0-flash-preview-image-generation
```

Per-project keys override global `.env` values. Use **mock** provider for testing without API costs.

## Docker Deployment

```bash
cp .env.example .env
# Edit .env with your settings

docker compose up -d
```

Services:
- **web** — Dashboard on port 8000
- **worker** — Scheduler checking every 60 seconds

Volumes:
- `./storage` — Database, images, logs
- `./.env` — Environment configuration

After starting:

```bash
docker compose exec web python -m app seed
docker compose exec web python -m app create-admin --email admin@example.com --password yourpassword
```

## Systemd Deployment (Linux)

```bash
sudo cp -r infra-content-engine /opt/
cd /opt/infra-content-engine
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # configure
python -m app seed
python -m app create-admin

sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable infra-content-web infra-content-worker
sudo systemctl start infra-content-web infra-content-worker
```

Put nginx or Caddy in front of port 8000 for HTTPS in production.

## API Keys Setup

### OpenAI (optional)

Set in `.env`:
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

Without a key, the system generates mock content suitable for testing.

### Image Generation

```env
IMAGE_PROVIDER=mock    # PIL placeholder (default, no API needed)
IMAGE_PROVIDER=openai  # Requires OPENAI_API_KEY
```

Images are stored in `storage/images/YYYY/MM/`.

### Facebook Page Publishing

1. Create a Facebook App at https://developers.facebook.com/
2. Add the **Pages** product
3. Generate a Page Access Token with `pages_manage_posts` and `pages_read_engagement`
4. Get your Page ID from Page Settings

```env
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_ACCESS_TOKEN=your_page_access_token
```

The system publishes text + image via Graph API v19.0.

### LinkedIn (Manual Mode — Default)

LinkedIn API requires app approval. Default mode prepares content for manual publishing:

1. Open a draft in the dashboard
2. Copy LinkedIn text (copy button)
3. Download the generated image
4. Post manually on LinkedIn
5. Click **Mark as Published**

```env
LINKEDIN_MODE=manual
```

To enable API mode placeholder (not yet implemented):
```env
LINKEDIN_MODE=api
```

See `app/services/linkedin_helper.py` for API setup TODO comments.

### Telegram Notifications (optional)

1. Create a bot via @BotFather
2. Get your chat ID (message @userinfobot or use getUpdates)

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=your_chat_id
```

Notifications sent for:
- New draft ready for review
- Successful publishing
- Publishing failures
- Posts ready for manual publishing

## Auto Publishing

Auto publishing requires **both** settings to be true:

1. **Global:** `AUTO_PUBLISH_ENABLED=true` in `.env` or Settings page
2. **Per-post:** `auto_publish=true` when scheduling

Safety defaults:
- `AUTO_PUBLISH_ENABLED=false` — nothing publishes automatically
- Rejected drafts are never published
- All AI prompts and outputs are logged in `generation_logs`
- API keys are masked in the dashboard

When `auto_publish=false` on a scheduled post, the worker marks it `ready_to_publish` and optionally sends a Telegram notification.

## Database Migrations

Using Alembic:

```bash
alembic upgrade head
```

For PostgreSQL later, update `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:pass@localhost/infra_content
```

## Project Structure

```
infra-content-engine/
├── app/
│   ├── main.py              # FastAPI app
│   ├── cli.py               # Typer CLI
│   ├── models.py            # SQLAlchemy models
│   ├── services/            # Business logic
│   ├── routers/             # Web routes
│   └── templates/           # Jinja2 HTML
├── storage/                 # DB, images, logs
├── prompts/                 # AI prompt templates
├── brand.yml                # Brand voice config
├── alembic/                 # DB migrations
├── docker-compose.yml
└── systemd/                 # Linux service files
```

## Backup Notes

Back up regularly:

- `storage/infra_content.db` — SQLite database
- `storage/images/` — Generated images
- `.env` — Configuration (store securely)
- `brand.yml` — Brand voice settings

Example cron backup:

```bash
0 2 * * * tar -czf /backups/infra-content-$(date +\%Y\%m\%d).tar.gz /opt/infra-content-engine/storage /opt/infra-content-engine/.env
```

## Workflow

1. **Add ideas** — Dashboard → Ideas (or use seeded samples)
2. **Generate drafts** — Click Generate or run CLI
3. **Review** — Check quality warnings, approve or edit
4. **Schedule or publish** — Set date/time and platforms
5. **Worker processes** — Auto-publishes when due (if enabled)
6. **LinkedIn manual** — Copy, post, mark as published
7. **Track** — Published page shows history and errors

## License

Private/internal use for InfraPilot marketing automation.
