#!/usr/bin/env -S uv run --script

"""
historian_capture/analyze.py

Run this after collecting a batch of forwarded messages.
Prints a summary of what your real data actually looks like.
"""

import json
import sqlite3
import sys
from collections import Counter

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "historian.db"
conn = sqlite3.connect(DB_PATH)
rows = conn.execute("SELECT * FROM raw_updates").fetchall()
cols = [d[0] for d in conn.execute("SELECT * FROM raw_updates LIMIT 0").description]

def col(row, name):
    return row[cols.index(name)]

print(f"\n{'='*60}")
print(f"Total updates captured: {len(rows)}")
print(f"{'='*60}\n")

# Provenance coverage
has_prov = sum(1 for r in rows if col(r, "fwd_from_chat_id"))
print(f"Forwarded (have provenance): {has_prov}/{len(rows)}")

# Origin channels
sources = Counter(
    col(r, "fwd_from_chat_username") or str(col(r, "fwd_from_chat_id"))
    for r in rows if col(r, "fwd_from_chat_id")
)
print(f"\nOrigin channels ({len(sources)} unique):")
for src, count in sources.most_common():
    print(f"  {src:40s} {count}")

# Media types
media = Counter(col(r, "media_type") or "text_only" for r in rows)
print(f"\nMedia types:")
for t, count in media.most_common():
    print(f"  {t:20s} {count}")

# Albums
albums = [r for r in rows if col(r, "media_group_id")]
album_ids = Counter(col(r, "media_group_id") for r in albums)
print(f"\nAlbum messages: {len(albums)} messages across {len(album_ids)} albums")
if album_ids:
    sizes = Counter(album_ids.values())
    print(f"  Album sizes: { dict(sorted(sizes.items())) }")

# Entity types
all_entities: list[str] = []
for r in rows:
    try:
        all_entities.extend(json.loads(col(r, "entity_types") or "[]"))
    except json.JSONDecodeError:
        pass
entity_counts = Counter(all_entities)
print(f"\nEntity types seen:")
for e, count in entity_counts.most_common():
    print(f"  {e:30s} {count}")

# Nulls check
text_only = sum(1 for r in rows if col(r, "has_text") and not col(r, "media_type"))
caption_only = sum(1 for r in rows if col(r, "has_caption") and not col(r, "has_text"))
no_text = sum(1 for r in rows if not col(r, "has_text") and not col(r, "has_caption"))
print(f"\nContent shape:")
print(f"  text only (no media):    {text_only}")
print(f"  caption only:            {caption_only}")
print(f"  pure media (no text):    {no_text}")

print(f"\n{'='*60}\n")
