"""PostgreSQL database layer for the game bot."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg

from config import DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    nickname TEXT UNIQUE NOT NULL,
    age INTEGER NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    money BIGINT NOT NULL DEFAULT 0 CHECK (money >= 0),
    stars BIGINT NOT NULL DEFAULT 0 CHECK (stars >= 0),
    privilege TEXT NOT NULL DEFAULT 'none',
    house_id BIGINT,
    created_at TEXT NOT NULL,
    last_activity_at TEXT,
    vip_type TEXT,
    vip_expires_at TEXT,
    referral_code TEXT UNIQUE,
    referred_by_user_id BIGINT REFERENCES users(id),
    stall_income BIGINT NOT NULL DEFAULT 0,
    daily_gift_claimed_at TEXT,
    monthly_gift_claimed_at TEXT
);

CREATE TABLE IF NOT EXISTS resources (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    stone BIGINT NOT NULL DEFAULT 0 CHECK (stone >= 0),
    wood BIGINT NOT NULL DEFAULT 0 CHECK (wood >= 0),
    food BIGINT NOT NULL DEFAULT 0 CHECK (food >= 0),
    ore BIGINT NOT NULL DEFAULT 0 CHECK (ore >= 0)
);

CREATE TABLE IF NOT EXISTS businesses (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_type TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (user_id, business_type)
);

CREATE TABLE IF NOT EXISTS business_instances (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_type TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 7),
    upgrade_started_at TEXT,
    upgrade_ends_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    currency TEXT NOT NULL,
    amount BIGINT NOT NULL,
    description TEXT,
    external_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS referrals (
    id BIGSERIAL PRIMARY KEY,
    inviter_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invited_user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    reward_money BIGINT NOT NULL DEFAULT 0,
    reward_stars DOUBLE PRECISION NOT NULL DEFAULT 0,
    reward_money_case INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_quests (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    progress INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    claimed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(user_id, quest_id)
);

CREATE TABLE IF NOT EXISTS case_inventory (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    money_cases INTEGER NOT NULL DEFAULT 0 CHECK (money_cases >= 0),
    star_cases INTEGER NOT NULL DEFAULT 0 CHECK (star_cases >= 0)
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    admin_nickname TEXT NOT NULL,
    command TEXT NOT NULL,
    target_user_id BIGINT,
    target_nickname TEXT,
    value TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_business_instances_user ON business_instances(user_id);
CREATE INDEX IF NOT EXISTS idx_referrals_inviter ON referrals(inviter_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created ON admin_logs(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_external_id2
    ON transactions(external_id) WHERE external_id IS NOT NULL AND external_id <> '';
"""


class CompatRow(dict):
    """Dict-like row with SQLite-compatible numeric indexing used by old handlers."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def row_factory(cursor):
    if cursor.description is None:
        return lambda values: values
    columns = [d.name for d in cursor.description]

    def make_row(values):
        return CompatRow(zip(columns, values))

    return make_row


class Database:
    def __init__(self, url: str):
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        self.url = url
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        async with await psycopg.AsyncConnection.connect(self.url, row_factory=row_factory) as conn:
            await conn.execute(SCHEMA)
            await self._seed_quests(conn)

            # The current project stores ⭐ in hundredths internally.
            # Never multiply balances automatically: doing so after a SQLite→PostgreSQL
            # migration would corrupt already-scaled balances.
            await conn.execute(
                "INSERT INTO schema_meta(key,value) VALUES(%s,%s) "
                "ON CONFLICT(key) DO NOTHING",
                ('stars_scaled_v2', '1'),
            )

            await conn.execute(
                "UPDATE business_instances SET level=2 "
                "WHERE business_type IN ('farm','mine') AND level < 2"
            )
            await conn.execute(
                "UPDATE users SET last_activity_at=COALESCE(last_activity_at,created_at)"
            )
            await conn.execute(
                "UPDATE users SET referral_code='ref_' || id "
                "WHERE referral_code IS NULL OR referral_code=''"
            )
            await conn.execute(
                "INSERT INTO case_inventory(user_id) SELECT id FROM users "
                "ON CONFLICT(user_id) DO NOTHING"
            )
            await conn.commit()

    async def _seed_quests(self, conn):
        quests = [
            (1, 'first_friend', '👥 Первый друг', 'Пригласите в игру 1 друга.', 0, 0, 0),
            (2, 'first_stall', '🏪 Первый ларёк', 'Купите ларёк в магазине.', 2500, 0.25, 0),
            (3, 'first_1000_stall', '🏪 Первые 1 000$', 'Заработайте первые 1 000$ с помощью ларька.', 5000, 0.25, 0),
            (4, 'resource_stock', '📦 Запас ресурсов', 'Купите 5 000 камня, 5 000 руды и 2 500 дерева.', 0, 0.25, 1),
            (5, 'first_factory', '🏭 Первый завод', 'Купите мини-завод в магазине.', 5000, 1, 0),
        ]
        async with conn.cursor() as cur:
            await cur.executemany(
                """INSERT INTO quests(
                    id,code,title,description,reward_money,reward_stars,reward_money_case
                ) VALUES(%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO NOTHING""",
                quests,
            )
        await conn.execute(
            "UPDATE quests SET code=%s,title=%s,description=%s,reward_money=0,reward_stars=0 WHERE id=1",
            ('first_friend', '👥 Первый друг', 'Пригласите в игру 1 друга.'),
        )
        await conn.execute(
            "UPDATE quests SET code=%s,title=%s,description=%s WHERE id=3",
            ('first_1000_stall', '🏪 Первые 1 000$', 'Заработайте первые 1 000$ с помощью ларька.'),
        )

    @asynccontextmanager
    async def connect(self):
        # The lock prevents multiple concurrent operations from sharing one connection.
        # Each context is a real PostgreSQL transaction: handlers explicitly commit or
        # exceptions roll it back when the context closes.
        async with self._lock:
            conn = await psycopg.AsyncConnection.connect(self.url, row_factory=row_factory)
            try:
                yield conn
            except Exception:
                await conn.rollback()
                raise
            finally:
                await conn.close()


db = Database(DATABASE_URL)
