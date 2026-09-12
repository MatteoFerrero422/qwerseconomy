"""One-time SQLite -> PostgreSQL migration.

Run locally from the bot directory:
    DATABASE_URL='postgresql://...' python migrate_sqlite.py

The SQLite file is read locally and is never uploaded to Render by this script.
"""
import asyncio
import os
import sqlite3

import psycopg

from config import DATABASE_URL
from database.database import SCHEMA

TABLES = [
    'users',
    'resources',
    'businesses',
    'business_instances',
    'transactions',
    'referrals',
    'quests',
    'user_quests',
    'case_inventory',
    'admin_logs',
]

ID_TABLES = ['users', 'businesses', 'business_instances', 'transactions', 'referrals', 'admin_logs']


def sqlite_path() -> str:
    return os.getenv('SQLITE_DB', os.path.join('database', 'game.db'))


def normalize_value(table, column, value):
    # PostgreSQL UNIQUE columns can have many NULLs, but not many empty strings.
    if table == 'users' and column == 'referral_code' and value == '':
        return None
    if table == 'transactions' and column == 'external_id' and value == '':
        return None
    return value


async def migrate():
    path = sqlite_path()
    if not os.path.exists(path):
        raise SystemExit(f'SQLite database not found: {path}')

    sq = sqlite3.connect(path)
    sq.row_factory = sqlite3.Row

    pg = await psycopg.AsyncConnection.connect(DATABASE_URL)
    try:
        await pg.execute(SCHEMA)

        # Make the external ID index tolerate old SQLite rows containing ''.
        await pg.execute('DROP INDEX IF EXISTS idx_transactions_external_id2')
        await pg.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_external_id2 "
            "ON transactions(external_id) WHERE external_id IS NOT NULL AND external_id <> ''"
        )

        for table in TABLES:
            info = sq.execute(f'PRAGMA table_info({table})').fetchall()
            if not info:
                print(f'{table}: skipped (table does not exist in SQLite)')
                continue

            sqlite_columns = [r[1] for r in info]
            pg_cur = await pg.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s",
                (table,),
            )
            pg_columns = {r[0] for r in await pg_cur.fetchall()}
            columns = [c for c in sqlite_columns if c in pg_columns]

            rows = sq.execute(f'SELECT * FROM {table}').fetchall()
            if not rows:
                print(f'{table}: 0 rows')
                continue

            placeholders = ','.join(['%s'] * len(columns))
            sql = (
                f'INSERT INTO {table} ({",".join(columns)}) '
                f'VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            )

            inserted = 0
            for row in rows:
                values = tuple(normalize_value(table, c, row[c]) for c in columns)
                cur = await pg.execute(sql, values)
                inserted += cur.rowcount

            print(f'{table}: {inserted}/{len(rows)} rows inserted')

        # The current bot stores internal ⭐ as hundredths. Mark the database as
        # already normalized so startup never multiplies balances by 100.
        await pg.execute(
            "INSERT INTO schema_meta(key,value) VALUES(%s,%s) "
            "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            ('stars_scaled_v2', '1'),
        )

        # Apply current business compatibility rules to migrated data.
        await pg.execute(
            "UPDATE business_instances SET level=2 "
            "WHERE business_type IN ('farm','mine') AND level < 2"
        )
        await pg.execute(
            "UPDATE users SET last_activity_at=COALESCE(last_activity_at,created_at)"
        )
        await pg.execute(
            "UPDATE users SET referral_code='ref_' || id "
            "WHERE referral_code IS NULL OR referral_code=''"
        )
        await pg.execute(
            "INSERT INTO resources(user_id) SELECT id FROM users ON CONFLICT(user_id) DO NOTHING"
        )
        await pg.execute(
            "INSERT INTO case_inventory(user_id) SELECT id FROM users ON CONFLICT(user_id) DO NOTHING"
        )

        # Reset BIGSERIAL sequences to the current maximum IDs.
        for table in ID_TABLES:
            sql = f"""SELECT setval(
                pg_get_serial_sequence(%s, 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT MAX(id) IS NOT NULL FROM {table})
            )"""
            await pg.execute(sql, (table,))

        await pg.commit()
        print('Migration completed successfully.')
    except Exception:
        await pg.rollback()
        raise
    finally:
        await pg.close()
        sq.close()


if __name__ == '__main__':
    asyncio.run(migrate())
