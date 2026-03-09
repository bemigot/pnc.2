# Historian Bot — Discovery & Plan

## Project Goal

Build a personal research archive ("Personal Notes Collection") fed by a Telegram bot
(`@history_jr_bot`) subscribed to a private channel (`t.me/history_jr`). When the user
forwards an interesting post from any public Telegram channel into `history_jr`, the bot
captures it, enriches it (transcripts, linked media, summaries), indexes it in a vector DB,
and serves it through a RAG-enabled research assistant backed by Google ADK + Gemini.

---

## Current State

A Python **ingest tap** (`bot.py`) is built and functioning. It runs as a long-polling
Telegram bot (no webhook, no reverse proxy). On every incoming message it saves:

- Raw `full_json` of the Telegram update
- Parsed provenance fields: origin channel, original publication date, forward date
- Content shape flags: media type, `media_group_id`, entity types

Storage: **SQLite** (`historian.db`), single table `raw_updates`.

**Environment:** `uv` project, Python 3.14, `python-telegram-bot` targeting Telegram Bot
API 9.3+.

---

## Immediate Next Step: Data Discovery

The user will **re-forward a curated set of real Telegram posts** into `history_jr`,
deliberately covering the main content types:

- Plain text post
- Post with a YouTube link
- Multi-image album (multiple photos in one post)
- Post with a PDF attachment
- Post with formatted text containing hidden hyperlinks (`text_link` entities)
- Pure media post (no caption)

Once collected, run **`analyze.py`** against the resulting `historian.db`. The analysis
will reveal:

- How many messages per album (`media_group_id` grouping) — critical for the aggregation
  buffer design
- Which `entity` types actually appear in real posts (`url`, `text_link`, `bold`, etc.)
- Whether the bot sees `forward_origin` (Bot API 7.0+) or legacy `forward_from_chat`
- Any unexpected content shapes (null text + null caption, missing provenance, etc.)

---

## What Comes After Discovery

The analysis output drives the design of the **production schema** (moving from SQLite to
PostgreSQL + pgvector), the **media aggregation buffer** (collecting album fragments before
processing), and the **extractor tools** (YouTube transcripts via yt-dlp, URL scraping,
PDF handling) that will be registered as Google ADK agent tools.

No schema or processing code should be written before the discovery run is complete.
