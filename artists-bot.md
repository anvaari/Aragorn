# Telegram Bot — Architecture & Flows

The interactive bot lives in `app/telegram_bot/`. It runs on the **same bot token as the channel**
(`telegram_bot_tk`): the channel receives posts, private chats get the interactive bot.
All user-facing text is Persian; messages use Telegram's legacy `Markdown` parse mode
(escape user/DB-derived text with `_escape_md` from `telegram/event_formatter.py`).

> **Keep this doc in sync** — update it whenever a bot feature, flow, or table changes.

## Runtime layout

Everything runs inside the single FastAPI process, started from the `lifespan` hook in `app/main.py`:

```
FastAPI lifespan
├── start_digest_scheduler()   # existing daily digest posts (app/core/scheduler.py)
├── start_bot_scheduler()      # 10-min reminder tick + 30-min enrichment sweep + daily summary refresh
└── start_bot_polling()        # aiogram 3 Dispatcher as asyncio task (app/telegram_bot/runner.py)
```

Two I/O paths, deliberately split to avoid sync→async friction:

| Path | Stack | Used for |
|---|---|---|
| Interactive | aiogram 3 (async, long polling) | handlers, inline keyboards, callback answers |
| Push | sync `requests` → `send_text_to_chat` (`app/telegram/bot.py`) | reminder pings, new-event alerts — called from APScheduler threads and sync service code |

**Proxy**: both paths honor `tg_gpt_ig_proxy` **only when the value contains `http`** —
requests via `_proxies()` in `app/telegram/bot.py`, aiogram via `_bot_session()` /
`AiohttpSession(proxy=...)` in `runner.py` (requires the `aiogram[proxy]` extra, i.e. `aiohttp-socks`).

**Single poller rule**: only ONE process may long-poll per token (Telegram returns 409 otherwise).
Set `bot_enabled=false` in `.env` on any secondary/dev instance — this disables polling only;
the push path and schedulers still run.

**Polling resilience**: mid-poll network errors are retried inside aiogram's `_listen_updates`
with backoff. If `start_polling` itself crashes (e.g. the local proxy was down at startup —
`TelegramNetworkError` / `ProxyConnectionError` on `tg_gpt_ig_proxy`), `_poll` in `runner.py`
rebuilds the Bot (the dispatcher is reused — routers can only be attached once) and retries
with backoff (2/5/15/30/60s), logging a proxy hint.

**Signals & shutdown**: `start_polling(..., handle_signals=False)` — aiogram's default signal
handler would swallow Ctrl+C so uvicorn never shuts down. `stop_bot_polling` waits at most 5s
for the polling task before abandoning it, so shutdown can't hang.

## Module map

```
app/telegram_bot/
  runner.py              # start/stop polling; Bot session (proxy); asyncio task lifecycle
  callbacks.py           # aiogram CallbackData factories (one class per inline action)
  keyboards.py           # inline keyboard builders (all Persian labels)
  cards.py               # message texts: event card, artist page, alerts, reminder pings
  notifier.py            # notify_new_event() fan-out + send_due_reminders() scan
  handlers/
    common.py            # /start, deep link evt_<id>, main menu, safe_edit()
    events.py            # day browsing → event card → set reminder; "artists of event"
    artists.py           # /artist FSM search → artist page (performances + related) → follow
    reminders.py         # /reminders list + delete
    admin.py             # admin-only normalization proposal review (✅/❌, pagination, bulk)
app/db/crud_artist.py    # artists + event_artists (normalize, find-or-create, linking, related)
app/db/crud_proposals.py # artist_name_proposals (pending normalization review rows)
app/db/crud_bot.py       # bot_users, event_reminders, artist_follows
app/services/artist_service.py   # link_event_artists(), enrichment sweep
app/services/normalization_service.py  # Persian→English proposals, apply/reject, admin DM
app/open_ai/artist_search.py     # LLM + web_search identity resolution (Responses API)
app/utils/event_time.py  # Shamsi/Gregorian parsing, Tehran now, Persian digits, day labels
app/cli.py               # typer CLI for one-off jobs (run from repo ROOT: python app/cli.py)
```

## Data model

Bot tables (created idempotently in `app/db/database.py:create_table`):

| Table | Purpose | Notes |
|---|---|---|
| `artists` | canonical artist identity | `name` (original, NEVER overwritten), `normalized_name` (approved English spelling — set only via an approved proposal or CLI `--apply`), `name_en`, `ig_handle`, `bio`, `resolved`, `source_url`, `attempts` (enrichment cap 3), `summary` + `summary_event_count` (LLM event-history summary; refreshed when linked-event count changes) |
| `event_artists` | event ↔ artist links | `artist_name_raw` = spelling on the poster; idempotent per (event, artist) |
| `artist_name_proposals` | normalization review queue | `artist_id`, `current_name` → `proposed_name`, `status` = pending/approved/rejected, `decided_at`; one pending per artist (INSERT guarded) |
| `bot_users` | chat registry | upserted on `/start` |
| `event_reminders` | one-off event reminders | `remind_at` = **Gregorian** `YYYY-MM-DD HH:MM` Tehran; `UNIQUE(chat_id, event_id, remind_at)`; `sent` flag |
| `artist_follows` | artist subscriptions | `notify_new` (new-post alert), `notify_pre` + `pre_hours` (pre-event reminder); `UNIQUE(chat_id, artist_id)` |

`events` gains two columns consumed by bot + digest: `id` (**`INTEGER PRIMARY KEY`** — SQLite
only auto-assigns rowid aliases with exactly this spelling; `create_table` also backfills
`id = rowid` for legacy NULL rows and `insert_event` assigns `MAX(id)+1` explicitly) and
`tg_message_id` (channel post id, used by digest title links).

## Flows

### 1. Ingestion → linking → follower alerts
```
endpoint (ig / image / manual)
  → event_service: send to channel (capture tg_message_id) → insert_event
  → _post_store_pipeline (never breaks ingestion; lazy imports, logs failures):
      • link_event_artists(event_id, performer_names)
            normalize (strip ZWNJ, collapse spaces, casefold) → find-or-create artist → link
      • notify_new_event(event_id, event)
            followers matched by linked artist_id OR normalized name in raw performers string
            → "new post" alert DMs + pre-created event_reminders rows for notify_pre followers
```
GPT extraction (`app/open_ai/text_events.py`) returns `(event, performer_names)`; the display
`performers` string stays comma-joined. Bare weekday dates ("پنجشنبه") are resolved to the next
Shamsi date by `_resolve_weekday_date` before parsing.

### 2. Browse events by day
`/start` → main menu → «رویدادها» → day picker (today, tomorrow, +5 days; labels via
`jday_short_label`, Shamsi from `digest_timezone`) → day's events (SQL `datetime LIKE 'jdate%'`)
→ event card → «یادآوری این رویداد» (2h / 24h / both; rejected for past/unparseable events) or
«هنرمندان این اجرا» → artist page. Deep link `t.me/<bot>?start=evt_<id>` opens the card directly.

### 3. Artist page (dedicated)
`/artist` or menu → FSM asks for a name → search matches **artists only**
(`search_artists` — LIKE on `artists.name`/`name_en`; events are NOT shown in search results —
the artist page is where events live) → artist page shows:
- **identity**: canonical name, `name_en`, IG handle, bio (empty + "not yet reviewed" note until enrichment resolves);
- **summary** («خلاصه اجراها»): LLM-written Persian summary of the artist's event history
  (event types, instruments/role, frequent co-performers) — see flow 5;
- **performances**: upcoming (asc) / past (desc, max 5) / undated — split **in Python** via
  `parse_event_datetime` (mixed Shamsi/Gregorian strings make SQL ordering wrong), from
  `get_events_for_artist` (event_artists JOIN + performers LIKE fallback);
- **related artists** («هنرمندان مرتبط»): co-performers via `event_artists` self-join on shared
  events, plus names parsed from the artist's raw performers strings resolved against the artists
  table (normalized, aliases included) — deduped; rendered as text **and** tappable buttons
  (max 6) that open those artists' pages;
- **follow**: ➕ → choose «رویداد جدید» / «یادآوری قبل از اجرا» / «هر دو» → upsert `artist_follows`.

### 4. Reminders (scan-based)
`event_reminders` is the source of truth (the scheduler is in-memory). Every 10 minutes
`send_due_reminders()` (via `start_bot_scheduler` → `_run_reminder_tick`) sends due pings with
`send_text_to_chat` and marks `sent=1`; survives restarts. `/reminders` lists active reminders
and followed artists with delete buttons.

### 5. Artist enrichment (identity resolution)
Every 30 minutes (gated by `artist_enrichment_enabled`): fetch unresolved artists
(`resolved=0 AND attempts<3`, batch of 5) → `search_artist_web` (Responses API,
`tools=[{"type":"web_search"}]`, model = `openai_artist_model` or fallback `openai_text_model`)
→ mark resolved only with `name` + `source_url` + confidence ≥ 0.5; otherwise `attempts += 1`
(cap 3, then abandoned). Each unique artist is web-searched at most 3 times ever; unresolved
names stay raw-matchable (fallbacks in flows 1 and 3).

### 6. Artist summary refresh (daily)
`refresh_artist_summaries` (daily job in `start_bot_scheduler`, first pass at app startup,
gated by `artist_enrichment_enabled`): selects artists whose **linked-event count differs from
the count their stored summary was built from** (`get_artists_needing_summary` — so a summary is
regenerated only when new events are added for that artist; the stored count is the linked count,
not the LIKE-augmented total, to avoid perpetual staleness). For each (batch of 50, most-linked
first): builds an event list (max 30) + co-performer names, asks the LLM (`summarize_artist` in
`open_ai/artist_search.py`, plain chat completion, no web search) for a short Persian summary of
event types, instruments/role, and frequent co-performers; stores it in `artists.summary`.
LLM failures leave the old state and are retried next sweep.

### 7. Artist name normalization (approval-gated)
Persian artist names get an English spelling in `artists.normalized_name`; the original
`name` is never modified. Nothing is applied without the admin's explicit ✅.

```
propose  — daily job `artist-normalization-propose` (limit 50/day) or CLI
           `python app/cli.py normalize-artists`:
           get_artists_missing_normalized_name (Persian-script names, no normalized_name,
           no pending proposal; ASCII names are skipped as already-searchable)
           → normalize_artist_names (one chat completion per ~25 names; empty value =
           "not a plausible artist name", silently drops OCR junk like «وکال)»)
           → artist_name_proposals rows (status=pending)
notify   — if ≥1 new proposal: DM bot_admin_chat_id via send_text_to_chat
           (aiogram markup serialized with model_dump_json) + «بررسی پیشنهادها» button
review   — handlers/admin.py (admin-only: callback.from_user.id must equal
           bot_admin_chat_id, else ⛔ alert): pages of 10 pending proposals, ✅/❌ per
           item, ◀️/▶️ pagination, «تأیید همه‌ی صفحه» and «تأیید همه» bulk buttons
apply    — approve_proposal writes status=approved AND artists.normalized_name in one
           commit; reject only flips status (artist stays without normalized_name)
```

Bulk backfill of all artists at once: `python app/cli.py normalize-artists --limit 100000`
(follow the same Telegram review) or `--apply` to skip review. Inspect the queue with
`python app/cli.py proposals [--status pending|approved|rejected|all]`.

`normalized_name` is included in artist search (`search_artists`), identity matching
(`find_artist_by_normalized_name`) and related-artist resolution, so users find a Persian
artist by typing its English name and vice versa.

## CLI (one-off jobs, run from repo ROOT)

`python app/cli.py <command>` — the script lives in `app/`, so `app/` lands on `sys.path`
(same trick as `fastapi run app/main.py`) and `.env` is read from the root CWD.

| Command | Purpose |
|---|---|
| `backfill-summaries [--batch-size 50]` | loop `refresh_artist_summaries` until no stale artist remains |
| `backfill-artists` | rebuild `artists` + `event_artists` from every event's `performers` string (idempotent — for DBs restored/created before linking existed) |
| `normalize-artists [--limit N] [--apply]` | propose Persian→English names (default) or write directly (`--apply`); always notifies the admin in Telegram unless `--apply` |
| `proposals [--status pending] [--limit 20]` | list the review queue |

## Config keys (see `app/core/config.py` — source of truth)

| Key | Default | Meaning |
|---|---|---|
| `bot_enabled` | `true` | aiogram polling on/off (409 rule above) |
| `artist_enrichment_enabled` | `true` | 30-min web-search sweep + daily summary refresh + daily normalization proposals |
| `openai_artist_model` | `""` | empty → use `openai_text_model` |
| `bot_admin_chat_id` | `""` | admin's personal numeric chat id; normalization review DMs go here (empty → skipped; find it in `bot_users` after `/start`) |
| `telegram_channel_username` | `""` | enables digest title links (main-branch feature) |
| `digest_*` | see config | digest schedule/timezone (pre-existing) |

## Gotchas & conventions

- **aiogram routing is first-match-wins**: `MenuCB` handlers are split per `F.action` across
  modules — don't add a catch-all `MenuCB.filter()`.
- **callback_data ≤ 64 bytes** — all factories here pack well under; keep new ones short.
- `safe_edit()` falls back to `callback.answer()` when the message can't be edited.
- Never answer the same callback query twice in one handler (second call raises).
- Reminder/alert DMs must never break ingestion: everything after insert is try/except + logged.
- Persian output everywhere; escape dynamic text with `_escape_md`; `UNKNOWN_TIME` = `"00:01"`
  (sentinel for "time not announced").
