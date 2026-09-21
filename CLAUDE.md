# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Aragorn collects independent (Iranian) music events and publishes them to a Telegram channel. FastAPI service with three ingestion paths: an Instagram post URL, an uploaded poster image (OCR), or manually supplied event data. Persian text is extracted into a structured event via OpenAI, formatted as Markdown, sent to Telegram, and stored in SQLite.

## Commands

```bash
pip install -r requirements.txt   # Python 3.12 (see .devcontainer/)
fastapi run app/main.py           # run from repo ROOT, not app/
```

- **Run from the repo root.** Modules use absolute imports rooted at `app/` (e.g. `from core.config import ...`); uvicorn puts the app file's directory on `sys.path`, while `.env` is read from the current working directory — so running from root makes both work. Running from inside `app/` loses the root `.env`.
- There is no test suite, no linter config, and no CI. mypy is used ad hoc (`mypy app`, no config file).

## API

All routes are mounted under `/api/v1/events/` (note the `events` prefix added in `app/api/v1/router.py`) and require `Authorization: Bearer <aragorn_tk>`:

- `POST /api/v1/events/ig_event` — `ig_link` is a **query parameter**, not a JSON body.
- `POST /api/v1/events/manual_event` — JSON body matching `EventCreate`.
- `POST /api/v1/events/image_event` — multipart with two file fields: `event_detail_image` (poster, OCR'd) and `event_image` (photo attached to the Telegram message).

## Architecture

Pipeline: endpoint → `app/services/event_service.py` (orchestration) → source adapter → GPT extraction → Telegram → SQLite. A daily digest scheduler (`app/core/scheduler.py`, started via the `lifespan` hook in `app/main.py`) sends a compact Persian list of upcoming events to Telegram via `app/services/digest_service.py`.

- **Ingestion adapters**: `app/ig_scrapper/extractor.py` scrapes caption + thumbnail URL via instagrapi (auth via session file, `cl.load_settings`); `app/open_ai/image_events.py` OCRs a poster via the OpenAI Responses API. Both feed `extract_event_from_ig_text` in `app/open_ai/text_events.py`, which holds the large system prompt and parses the JSON reply into `EventCreate`.
- **`app/models/event.py`**: `EventCreate` has computed properties `datetime` (`date time`) and `google_calendar_link` — not pydantic fields, so `model_dump()` excludes them. Shamsi (Jalali) → Gregorian conversion lives in `app/utils/google_calendar.py` using `jdatetime`.
- **Telegram** (`app/telegram/`): `send_image_to_telegram` branches on whether the photo is a URL (`str`) or raw bytes; `event_formatter.py` renders Persian Markdown, escapes `_`, and detects lat/long locations to produce Google Maps links.
- **DB** (`app/db/`): raw sqlite3, one new connection per operation via `initialize_db()`; the `events` table is created if missing. Rows store `created_at` (ingestion time) plus the event's Shamsi `datetime` as `"YYYY-MM-DD HH:MM"` in the `datetime` column — written by `insert_event` (older rows have it NULL and are invisible to digests). `get_events_by_jdate(jdate)` queries by Shamsi date prefix; SQL is parameterized.
- **Digest** (`app/core/scheduler.py`, `app/services/digest_service.py`): APScheduler `BackgroundScheduler` started in `app/main.py`'s lifespan. Schedules come from `digest_schedules` (JSON list of `{"time": "HH:MM", "day_offset": N}`; 0 = today, 1 = tomorrow), plus `digest_enabled` / `digest_timezone` in config — all with defaults so `.env` can omit them. Silent (no message) when no events match; `misfire_grace_time` 1h to catch up after a restart.
- **Config** (`app/core/config.py`): pydantic-settings, every field required. The env var names are the `alias=` values there — **config.py is the source of truth**, not README.md or `.env.sample`, which are outdated (e.g. `instagram_login_session_file`, `openai_text_model`, `openai_image_model` vs. the old `instagram_login_cookie` / `openai_model`).
- **Proxy**: `tg_gpt_ig_proxy` is shared by Telegram, OpenAI, and Instagram clients; each applies it only when the value contains `http`.
- **Logging**: get a logger with `get_app_logger(__name__)` from `app/log/logger.py` (rich-formatted stdout handler); add `exc_info=True` for error traces, as existing code does.

## Conventions & context

- User-facing output is Persian; the GPT system prompt in `text_events.py` enforces Shamsi dates (`YYYY-MM-DD`), 24-hour times, and returns `""` (never null) for missing fields; time falls back to `"00:01"` when absent.
- `session.json` at the repo root is the instagrapi Instagram session file (gitignored); `aragorn_db.sqlite` is the live dev database.
- Recent direction: instaloader was replaced with instagrapi, and the image-to-event endpoint is the newest feature.
