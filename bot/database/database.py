"""PostgreSQL database layer for the game bot."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg
from psycopg_pool import AsyncConnectionPool

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
    """
    PostgreSQL access via a real connection pool.

    Previous implementation opened a brand new TCP/TLS connection for every
    single query AND serialized every single one of them behind one global
    asyncio.Lock — meaning the entire bot could only ever process one DB
    operation at a time, for all users combined. That is what caused the
    lag/freezes under any real load. A pool keeps a handful of already-open
    connections ready and lets independent requests run concurrently.
    """

    def __init__(self, url: str, min_size: int = 2, max_size: int = 10):
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        self.url = url
        self.min_size = min_size
        self.max_size = max_size
        self.pool: AsyncConnectionPool | None = None

    async def init(self) -> None:
        self.pool = AsyncConnectionPool(
            self.url,
            min_size=self.min_size,
            max_size=self.max_size,
            kwargs={
                "row_factory": row_factory,
                # TCP keepalives: detect a dead socket quickly instead of
                # silently sending queries into a connection the network/DB
                # provider already dropped while it sat idle.
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
            # Ping every connection with a cheap query before handing it to
            # a request. Managed Postgres (Render/Supabase/Neon etc.) closes
            # idle connections server-side; without this check the pool would
            # keep handing out a connection object that looks fine locally
            # but is already dead on the server, causing exactly the
            # "SSL connection has been closed unexpectedly" / "the connection
            # is lost" errors seen in the logs. If the check fails, the pool
            # discards that connection and opens a fresh one automatically.
            check=AsyncConnectionPool.check_connection,
            # Proactively recycle connections before they sit idle long
            # enough for the DB provider to kill them itself, and before
            # any single connection gets old enough to be flaky.
            max_idle=120,
            max_lifetime=1800,
            open=False,
        )
        await self.pool.open(wait=True)

        async with self.pool.connection() as conn:
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
            (1, 'first_friend', '👥 Первый друг', 'Пригласите в игру 1 друга.', 5000, 0, 0),
            (2, 'first_stall', '🏪 Первый ларёк', 'Купите ларёк в магазине.', 2500, 0.25, 0),
            (3, 'first_1000_stall', '🏪 Первые 1 000$', 'Заработайте первые 1 000$ с помощью ларька.', 5000, 0.25, 0),
            (4, 'channel_subscription', '📢 Подписка на канал', 'Подпишитесь на наш телеграм-канал: https://t.me/Pepexspace', 5000, 0, 0),
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
            "UPDATE quests SET code=%s,title=%s,description=%s,reward_money=5000,reward_stars=0,reward_money_case=0 WHERE id=1",
            ('first_friend', '👥 Первый друг', 'Пригласите в игру 1 друга.'),
        )
        await conn.execute(
            "UPDATE quests SET code=%s,title=%s,description=%s WHERE id=3",
            ('first_1000_stall', '🏪 Первые 1 000$', 'Заработайте первые 1 000$ с помощью ларька.'),
        )
        await conn.execute(
            "UPDATE quests SET code=%s,title=%s,description=%s,reward_money=5000,reward_stars=0,reward_money_case=0 WHERE id=4",
            ('channel_subscription', '📢 Подписка на канал', 'Подпишитесь на наш телеграм-канал: https://t.me/Pepexspace'),
        )

    @asynccontextmanager
    async def connect(self):
        """
        Drop-in replacement for the old context manager: handler code
        elsewhere (`async with db.connect() as conn: ...`) does not need
        to change at all. Internally this now borrows a connection from
        the pool instead of opening a new one and taking a global lock,
        so independent requests from different users run in parallel.

        No manual rollback here on purpose: `pool.connection()` already
        commits on a clean exit and rolls back on an exception by itself.
        Adding a second rollback on top of that was the bug — when the
        connection was already dead (server-side idle timeout, dropped
        SSL socket), that extra rollback call raised its own
        OperationalError and masked/duplicated what the pool was already
        handling correctly, which is what produced the crashes in the
        logs. Let the pool manage the connection's lifecycle entirely.
        """
        async with self.pool.connection() as conn:
            yield conn

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()


db = Database(DATABASE_URL)
