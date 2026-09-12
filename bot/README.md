# Economy Bot — Render + PostgreSQL

This version is prepared for deployment on Render with an external PostgreSQL database (recommended: Neon).

## Environment variables

Set these in Render → Environment:

```env
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_id
ADMIN_IDS=123,456
BOT_USERNAME=your_bot_username_without_@
DATABASE_URL=postgresql://...
```

Do **not** put real secrets in GitHub, `.env`, README files, or the ZIP uploaded to a public repository.

## Render

The repository root contains `render.yaml`.

- Build: `pip install -r bot/requirements.txt`
- Start: `cd bot && python main.py`
- Health check: `/health`

`keep_alive.py` reads Render's `PORT` environment variable automatically.

## PostgreSQL

The bot uses `psycopg` and no longer uses SQLite at runtime. Render's local filesystem is not used for persistent game data.

## Migrating the old SQLite database

Keep your old `bot/database/game.db` locally (do not commit it to GitHub), set `DATABASE_URL` to the new PostgreSQL database, then run from the `bot` directory:

```bash
python migrate_sqlite.py
```

The migration script:

- creates the PostgreSQL schema;
- copies users, resources, businesses, business instances, transactions, referrals, quests, quest progress, cases and admin logs;
- preserves existing numeric IDs where possible;
- preserves the current internal ⭐ representation (hundredths);
- normalizes empty unique values safely;
- resets PostgreSQL sequences after import.

After migration, deploy the bot on Render with the same `DATABASE_URL`.
