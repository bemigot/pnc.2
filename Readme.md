# PNC v2 - Prototype collector / technical analyzer

Run it:

```bash
cp sample.env .env
# edit .env with your token

uv sync  # recommended
uv run bot.py
# ...
# 2026-03-08 23:07:37 [INFO] httpx: HTTP Request: POST https://api.telegram.org/bot<TOKEN>/getUpdates "HTTP/1.1 200 OK"
# 2026-03-08 23:07:47 [INFO] httpx: HTTP Request: POST https://api.telegram.org/bot<TOKEN>/getUpdates "HTTP/1.1 200 OK"
```

Then forward a deliberate variety of messages to your channel
- text-only post
- multi-image album
- post with a YouTube link
- post with a PDF
- post with formatted text containing hidden URLs.

Try to cover each case at least twice.

When done:
```bash
uv run analyze.py historian.db
```

That'll give us the breakdown we need to design the real schema.
The key things `analyze.py` is looking for are album sizes, entity type distribution,
and whether `forward_origin` (API 7.0+) or `forward_from_chat` (legacy) is what the bot
actually sees -- that last one is version-dependent and worth confirming on real data.

For more see [Claude](https://claude.ai/share/98e81a8b-6c14-48cd-a982-2fd8abba8466)

**Q**: May I reuse my existing bot and its `TELEGRAM_BOT_TOKEN` in this *long-polling* `bot.py`?

**A**: Yes, with one caveat: **you can't run both simultaneously**.

A Telegram bot token can only have one active update receiver at a time.
If you start the long-polling `bot.py` while the *webhook* is still registered,
Telegram will reject the polling requests.

The fix is one API call to deregister the webhook before starting polling:

```bash
. .env  # read TELEGRAM_BOT_TOKEN
curl https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook

# {"ok":true,"result":true,"description":"Webhook was deleted"}
```

After that, `bot.py` can use the exact same token. When you eventually want the webhook back,
just re-register it with `setWebhook` and stop the polling process.

`python-telegram-bot` library actually does this automatically — the `drop_pending_updates=True`
in `run_polling()` handles the switchover cleanly on startup.

But calling `deleteWebhook` manually first is cleaner and avoids a race condition.

### Claude Code LSP
```bash
npm install -g pyright

# in Claude Code
/plugin install pyright@claude-code-lsps
```
