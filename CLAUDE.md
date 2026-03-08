# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
# if no .env file found, advise User to copy sample.env to .env (platform-specific) and edit it to set TELEGRAM_BOT_TOKEN
uv sync

# Before running bot.py (if an existing webhook is registered):
. .env
curl https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook

# Run the ingestion bot
uv run bot.py

# Analyze collected data
uv run analyze.py historian.db
```

## Dependencies

- **python-telegram-bot 22.6** — Full Support for Bot API 9.3

## Architecture

**PNC v2** is a two-script Telegram data capture prototype for schema design research.

**`bot.py`** — Long-polling Telegram bot (no webhook). On each incoming message it:
1. Extracts provenance via `extract_provenance()`, which handles both Bot API ≥7.0 (`forward_origin`) and the legacy `forward_from_chat` field.
2. Writes one row to `raw_updates` (SQLite, WAL mode) with parsed fields plus the full raw JSON blob.
3. Uses `log_utils.install_log_redactor()` to strip the bot token from all log output.

**`analyze.py`** — Runs read-only SQL queries and prints a console report against the collected `historian.db`. Takes the DB path as a CLI argument.

**`log_utils.py`** — Thin logging utility: wraps the root logger's formatter to redact a secret string from all output.

**Config** via `.env`: `TELEGRAM_BOT_TOKEN` (required), `DB_PATH` (default: `historian.db`).

The bot token can only have one active update receiver at a time — do not run `bot.py` alongside
a webhook-registered instance of the same token.

## References

- [Bot API changelog](https://core.telegram.org/bots/api)
- [`MessageOrigin` / `forward_origin` types](https://core.telegram.org/bots/api#messageorigin)
