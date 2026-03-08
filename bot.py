"""
historian_capture/bot.py

Ingest tap for history_jr_bot.
Long-polling, no webhook, no reverse proxy needed.
Saves every update as raw JSON + parsed provenance fields to SQLite.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv
from log_utils import install_log_redactor
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("historian")


DB_PATH = os.getenv("DB_PATH", "historian.db")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_updates (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Telegram identifiers
            update_id               INTEGER UNIQUE NOT NULL,
            message_id              INTEGER,
            chat_id                 INTEGER,
            ingestion_ts            TEXT NOT NULL,   -- UTC ISO-8601, when WE saw it

            -- Provenance (where the OP actually came from)
            fwd_from_chat_id        INTEGER,         -- origin channel id
            fwd_from_chat_username  TEXT,            -- e.g. @Clio_History
            fwd_from_chat_title     TEXT,
            fwd_from_message_id     INTEGER,         -- OP message id in origin channel
            fwd_date                TEXT,            -- UTC ISO-8601, when OP was published

            -- Content shape (for quick filtering, not processing)
            has_text                INTEGER,         -- 0/1
            has_caption             INTEGER,         -- 0/1
            media_group_id          TEXT,            -- non-null → part of album
            media_type              TEXT,            -- photo/video/document/audio/sticker/…
            entity_types            TEXT,            -- JSON array of entity type strings

            -- Full fidelity
            full_json               TEXT NOT NULL
        )
    """)
    conn.commit()
    log.info("DB ready at %s", path)
    return conn


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def utc_iso(ts) -> str | None:
    """Convert a datetime or unix timestamp to UTC ISO-8601 string."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts, tz=timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat()


def extract_provenance(msg) -> dict:
    """
    Pull forward-origin fields.  Telegram Bot API 7.0 introduced forward_origin;
    older clients still send forward_from_chat.  Handle both.
    """
    result = {
        "fwd_from_chat_id": None,
        "fwd_from_chat_username": None,
        "fwd_from_chat_title": None,
        "fwd_from_message_id": None,
        "fwd_date": None,
    }

    # Bot API >= 7.0
    origin = getattr(msg, "forward_origin", None)
    if origin is not None:
        chat = getattr(origin, "chat", None)
        if chat:
            result["fwd_from_chat_id"] = chat.id
            result["fwd_from_chat_username"] = getattr(chat, "username", None)
            result["fwd_from_chat_title"] = getattr(chat, "title", None)
        result["fwd_from_message_id"] = getattr(origin, "message_id", None)
        result["fwd_date"] = utc_iso(getattr(origin, "date", None))
        return result

    # Bot API < 7.0 fallback
    fwd_chat = getattr(msg, "forward_from_chat", None)
    if fwd_chat:
        result["fwd_from_chat_id"] = fwd_chat.id
        result["fwd_from_chat_username"] = getattr(fwd_chat, "username", None)
        result["fwd_from_chat_title"] = getattr(fwd_chat, "title", None)
        result["fwd_from_message_id"] = getattr(msg, "forward_from_message_id", None)
        result["fwd_date"] = utc_iso(getattr(msg, "forward_date", None))

    return result


def media_type(msg) -> str | None:
    for attr in ("photo", "video", "document", "audio", "voice",
                 "video_note", "sticker", "animation"):
        if getattr(msg, attr, None):
            return attr
    return None


def entity_types(msg) -> list[str]:
    entities = getattr(msg, "entities", None) or getattr(msg, "caption_entities", None) or []
    return list({e.type for e in entities})


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def make_handler(conn: sqlite3.Connection):
    async def handle_message(update: Update, _ctx):
        msg = update.effective_message
        if msg is None:
            return

        now = datetime.now(tz=timezone.utc).isoformat()
        prov = extract_provenance(msg)
        mtype = media_type(msg)
        etypes = entity_types(msg)

        # Serialize the full update via python-telegram-bot's built-in method
        full = update.to_json()

        try:
            conn.execute("""
                INSERT OR IGNORE INTO raw_updates (
                    update_id, message_id, chat_id, ingestion_ts,
                    fwd_from_chat_id, fwd_from_chat_username, fwd_from_chat_title,
                    fwd_from_message_id, fwd_date,
                    has_text, has_caption, media_group_id, media_type, entity_types,
                    full_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                update.update_id,
                msg.message_id,
                msg.chat_id,
                now,
                prov["fwd_from_chat_id"],
                prov["fwd_from_chat_username"],
                prov["fwd_from_chat_title"],
                prov["fwd_from_message_id"],
                prov["fwd_date"],
                1 if msg.text else 0,
                1 if msg.caption else 0,
                msg.media_group_id,
                mtype,
                json.dumps(etypes),
                full,
            ))
            conn.commit()

            log.info(
                "saved update_id=%s  fwd_from=%s  media=%s  group=%s  entities=%s",
                update.update_id,
                prov["fwd_from_chat_username"] or prov["fwd_from_chat_id"] or "—",
                mtype or "text",
                msg.media_group_id or "—",
                etypes or "—",
            )

        except sqlite3.IntegrityError:
            log.warning("duplicate update_id=%s, skipped", update.update_id)

    return handle_message


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    install_log_redactor(token, replacement="<TOKEN>")
    conn = init_db(DB_PATH)

    app = (
        Application.builder()
        .token(token)
        .build()
    )

    app.add_handler(MessageHandler(filters.ALL, make_handler(conn)))

    log.info("Starting long-poll loop …")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,   # ignore backlog on startup
    )


if __name__ == "__main__":
    main()
