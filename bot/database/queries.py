from datetime import datetime, timezone
from typing import Optional

from database.models import Business, Resources, Transaction, User


class InsufficientFundsError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def get_user_by_telegram_id(conn, telegram_id: int) -> Optional[User]:
    cur = await conn.execute("SELECT * FROM users WHERE telegram_id=%s", (telegram_id,))
    row = await cur.fetchone()
    return User.from_row(row) if row else None


async def get_user_by_nickname(conn, nickname: str) -> Optional[User]:
    cur = await conn.execute("SELECT * FROM users WHERE LOWER(nickname)=LOWER(%s)", (nickname,))
    row = await cur.fetchone()
    return User.from_row(row) if row else None


async def get_user_by_id(conn, user_id: int) -> Optional[User]:
    cur = await conn.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    row = await cur.fetchone()
    return User.from_row(row) if row else None


async def create_user(conn, telegram_id, nickname, age, password_hash, password_salt, start_money, start_stars):
    now = _now()
    # referral_code must start as NULL: PostgreSQL UNIQUE columns allow many NULLs,
    # while multiple empty strings would violate the unique constraint.
    cur = await conn.execute(
        """INSERT INTO users(
            telegram_id,nickname,age,password_hash,password_salt,money,stars,
            privilege,house_id,created_at,last_activity_at,referral_code
        ) VALUES(%s,%s,%s,%s,%s,%s,%s,'none',NULL,%s,%s,NULL)
        RETURNING id""",
        (telegram_id, nickname, age, password_hash, password_salt, start_money, start_stars, now, now),
    )
    user_id = (await cur.fetchone())["id"]
    await conn.execute("UPDATE users SET referral_code=%s WHERE id=%s", (f"ref_{user_id}", user_id))
    await conn.execute("INSERT INTO resources(user_id) VALUES(%s) ON CONFLICT DO NOTHING", (user_id,))
    await conn.execute("INSERT INTO case_inventory(user_id) VALUES(%s) ON CONFLICT DO NOTHING", (user_id,))
    await conn.commit()
    return await get_user_by_id(conn, user_id)


async def update_user_money(conn, user_id, delta):
    cur = await conn.execute(
        "UPDATE users SET money=money+%s WHERE id=%s AND money+%s >= 0",
        (delta, user_id, delta),
    )
    if cur.rowcount != 1:
        raise InsufficientFundsError("Недостаточно денег")


async def update_user_stars(conn, user_id, delta):
    cur = await conn.execute(
        "UPDATE users SET stars=stars+%s WHERE id=%s AND stars+%s >= 0",
        (delta, user_id, delta),
    )
    if cur.rowcount != 1:
        raise InsufficientFundsError("Недостаточно звёзд")


async def get_resources(conn, user_id):
    cur = await conn.execute("SELECT * FROM resources WHERE user_id=%s", (user_id,))
    row = await cur.fetchone()
    if not row:
        await conn.execute("INSERT INTO resources(user_id) VALUES(%s) ON CONFLICT DO NOTHING", (user_id,))
        cur = await conn.execute("SELECT * FROM resources WHERE user_id=%s", (user_id,))
        row = await cur.fetchone()
    return Resources.from_row(row)


VALID_RESOURCES = ("stone", "wood", "food", "ore")


async def update_resource(conn, user_id, resource_type, delta):
    if resource_type not in VALID_RESOURCES:
        raise ValueError(f"Неизвестный ресурс: {resource_type}")
    cur = await conn.execute(
        f"UPDATE resources SET {resource_type}={resource_type}+%s "
        f"WHERE user_id=%s AND {resource_type}+%s >= 0",
        (delta, user_id, delta),
    )
    if cur.rowcount != 1:
        raise InsufficientFundsError("Недостаточно ресурсов")


async def get_businesses(conn, user_id):
    # PostgreSQL requires every non-aggregated selected column to be in GROUP BY.
    cur = await conn.execute(
        """SELECT
            business_type,
            COUNT(*) AS quantity,
            MIN(id) AS id,
            user_id,
            MAX(level) AS level,
            MIN(created_at) AS created_at
        FROM business_instances
        WHERE user_id=%s
        GROUP BY business_type, user_id
        ORDER BY MIN(id)""",
        (user_id,),
    )
    rows = await cur.fetchall()
    return [Business.from_row(r) for r in rows]


async def get_business_quantity(conn, user_id, business_type):
    cur = await conn.execute(
        "SELECT COUNT(*) FROM business_instances WHERE user_id=%s AND business_type=%s",
        (user_id, business_type),
    )
    return (await cur.fetchone())[0]


async def add_business(conn, user_id, business_type, quantity=1, level=1):
    for _ in range(quantity):
        await conn.execute(
            "INSERT INTO business_instances(user_id,business_type,level,created_at) VALUES(%s,%s,%s,%s)",
            (user_id, business_type, level, _now()),
        )


async def get_business_instances(conn, user_id, business_type=None):
    if business_type:
        cur = await conn.execute(
            "SELECT * FROM business_instances WHERE user_id=%s AND business_type=%s ORDER BY id",
            (user_id, business_type),
        )
    else:
        cur = await conn.execute("SELECT * FROM business_instances WHERE user_id=%s ORDER BY id", (user_id,))
    return await cur.fetchall()


async def get_business_instance(conn, user_id, instance_id):
    cur = await conn.execute(
        "SELECT * FROM business_instances WHERE id=%s AND user_id=%s",
        (instance_id, user_id),
    )
    return await cur.fetchone()


async def start_business_upgrade(conn, user_id, instance_id, new_level, seconds):
    end = datetime.now(timezone.utc).timestamp() + seconds
    started = _now()
    ends = datetime.fromtimestamp(end, timezone.utc).isoformat()
    cur = await conn.execute(
        """UPDATE business_instances
        SET upgrade_started_at=%s, upgrade_ends_at=%s
        WHERE id=%s AND user_id=%s AND level=%s AND upgrade_ends_at IS NULL""",
        (started, ends, instance_id, user_id, new_level - 1),
    )
    if cur.rowcount != 1:
        raise ValueError("Улучшение уже запущено или бизнес изменился")


async def finish_business_upgrade_if_ready(conn, user_id, instance_id):
    row = await get_business_instance(conn, user_id, instance_id)
    if not row or not row["upgrade_ends_at"]:
        return row, False
    if _parse_dt(row["upgrade_ends_at"]) > datetime.now(timezone.utc):
        return row, False
    await conn.execute(
        "UPDATE business_instances SET level=level+1, upgrade_started_at=NULL, upgrade_ends_at=NULL "
        "WHERE id=%s AND user_id=%s AND level < 7",
        (instance_id, user_id),
    )
    return await get_business_instance(conn, user_id, instance_id), True


async def complete_ready_upgrades(conn, user_id):
    cur = await conn.execute(
        "SELECT id,upgrade_ends_at FROM business_instances "
        "WHERE user_id=%s AND upgrade_ends_at IS NOT NULL",
        (user_id,),
    )
    rows = await cur.fetchall()
    completed = []
    now = datetime.now(timezone.utc)
    for row in rows:
        if _parse_dt(row["upgrade_ends_at"]) <= now:
            cur = await conn.execute(
                """UPDATE business_instances
                SET level=level+1,upgrade_started_at=NULL,upgrade_ends_at=NULL
                WHERE id=%s AND user_id=%s AND level < 7""",
                (row["id"], user_id),
            )
            if cur.rowcount == 1:
                completed.append(row["id"])
    return completed


async def add_transaction(conn, user_id, type_, currency, amount, description, external_id=None):
    cur = await conn.execute(
        """INSERT INTO transactions(
            user_id,type,currency,amount,description,external_id,created_at
        ) VALUES(%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING RETURNING id""",
        (user_id, type_, currency, amount, description, external_id, _now()),
    )
    row = await cur.fetchone()
    return row is not None


async def get_transactions(conn, user_id, limit=20):
    cur = await conn.execute(
        "SELECT * FROM transactions WHERE user_id=%s ORDER BY id DESC LIMIT %s",
        (user_id, limit),
    )
    return [Transaction.from_row(r) for r in await cur.fetchall()]


async def set_last_activity(conn, user_id, when=None):
    await conn.execute("UPDATE users SET last_activity_at=%s WHERE id=%s", (when or _now(), user_id))


async def get_last_activity(conn, user_id):
    cur = await conn.execute("SELECT last_activity_at FROM users WHERE id=%s", (user_id,))
    r = await cur.fetchone()
    return r[0] if r else None


async def set_vip(conn, user_id, vip_type, expires_at):
    await conn.execute(
        "UPDATE users SET vip_type=%s,vip_expires_at=%s,privilege=%s WHERE id=%s",
        (vip_type, expires_at, f"VIP {vip_type.title()}", user_id),
    )


async def clear_vip_if_expired(conn, user_id):
    cur = await conn.execute("SELECT vip_type,vip_expires_at FROM users WHERE id=%s", (user_id,))
    r = await cur.fetchone()
    if r and r[1] and _parse_dt(r[1]) <= datetime.now(timezone.utc):
        await conn.execute(
            "UPDATE users SET vip_type=NULL,vip_expires_at=NULL,privilege='none' WHERE id=%s",
            (user_id,),
        )
        return True
    return False


async def get_referral_code(conn, user_id):
    cur = await conn.execute("SELECT referral_code FROM users WHERE id=%s", (user_id,))
    r = await cur.fetchone()
    return r[0] if r else None


async def apply_referral(conn, invited_user_id, referral_code):
    cur = await conn.execute("SELECT id FROM users WHERE referral_code=%s", (referral_code,))
    r = await cur.fetchone()
    if not r or r[0] == invited_user_id:
        return None
    inviter_id = r[0]

    cur = await conn.execute("SELECT id FROM referrals WHERE invited_user_id=%s", (invited_user_id,))
    if await cur.fetchone():
        return None

    cur = await conn.execute(
        """INSERT INTO referrals(inviter_user_id,invited_user_id,created_at)
        VALUES(%s,%s,%s)
        ON CONFLICT(invited_user_id) DO NOTHING RETURNING id""",
        (inviter_id, invited_user_id, _now()),
    )
    if not await cur.fetchone():
        return None
    await conn.execute("UPDATE users SET referred_by_user_id=%s WHERE id=%s", (inviter_id, invited_user_id))
    return inviter_id


async def get_quest_rows(conn, user_id):
    cur = await conn.execute(
        """SELECT q.*,
            COALESCE(uq.progress,0) AS progress,
            COALESCE(uq.completed,0) AS completed,
            COALESCE(uq.claimed,0) AS claimed
        FROM quests q
        LEFT JOIN user_quests uq ON uq.quest_id=q.id AND uq.user_id=%s
        ORDER BY q.id""",
        (user_id,),
    )
    return await cur.fetchall()


async def set_quest_progress(conn, user_id, quest_id, progress, required):
    completed = 1 if progress >= required else 0
    await conn.execute(
        """INSERT INTO user_quests(user_id,quest_id,progress,completed,claimed)
        VALUES(%s,%s,%s,%s,0)
        ON CONFLICT(user_id,quest_id) DO UPDATE SET
            progress=GREATEST(user_quests.progress,EXCLUDED.progress),
            completed=GREATEST(user_quests.completed,EXCLUDED.completed)""",
        (user_id, quest_id, progress, completed),
    )


async def get_quest(conn, user_id, quest_id):
    cur = await conn.execute(
        """SELECT q.*,
            COALESCE(uq.progress,0) AS progress,
            COALESCE(uq.completed,0) AS completed,
            COALESCE(uq.claimed,0) AS claimed
        FROM quests q
        LEFT JOIN user_quests uq ON uq.quest_id=q.id AND uq.user_id=%s
        WHERE q.id=%s""",
        (user_id, quest_id),
    )
    return await cur.fetchone()


async def claim_quest(conn, user_id, quest_id):
    row = await get_quest(conn, user_id, quest_id)
    if not row or not row["completed"] or row["claimed"]:
        return None

    cur = await conn.execute(
        """UPDATE user_quests
        SET claimed=1
        WHERE user_id=%s AND quest_id=%s AND completed=1 AND claimed=0""",
        (user_id, quest_id),
    )
    if cur.rowcount != 1:
        return None

    if row["reward_money"]:
        await update_user_money(conn, user_id, row["reward_money"])
    if row["reward_stars"]:
        await update_user_stars(conn, user_id, int(round(float(row["reward_stars"]) * 100)))
    if row["reward_money_case"]:
        await conn.execute(
            "UPDATE case_inventory SET money_cases=money_cases+%s WHERE user_id=%s",
            (row["reward_money_case"], user_id),
        )
    return row


async def get_case_inventory(conn, user_id):
    cur = await conn.execute("SELECT * FROM case_inventory WHERE user_id=%s", (user_id,))
    r = await cur.fetchone()
    if not r:
        await conn.execute("INSERT INTO case_inventory(user_id) VALUES(%s) ON CONFLICT DO NOTHING", (user_id,))
        cur = await conn.execute("SELECT * FROM case_inventory WHERE user_id=%s", (user_id,))
        r = await cur.fetchone()
    return r


async def consume_money_case(conn, user_id):
    cur = await conn.execute(
        "UPDATE case_inventory SET money_cases=money_cases-1 WHERE user_id=%s AND money_cases>0",
        (user_id,),
    )
    return cur.rowcount == 1


async def add_stall_income(conn, user_id, amount):
    await conn.execute("UPDATE users SET stall_income=stall_income+%s WHERE id=%s", (amount, user_id))


async def add_business_stars(conn, user_id, units):
    # Unified ⭐ balance: business-generated stars and Telegram Stars use users.stars.
    if units <= 0:
        return
    await conn.execute("UPDATE users SET stars=stars+%s WHERE id=%s", (units, user_id))


async def get_referral_stats(conn, user_id):
    cur = await conn.execute("SELECT COUNT(*) FROM referrals WHERE inviter_user_id=%s", (user_id,))
    registered = (await cur.fetchone())[0]
    cur = await conn.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN currency='money' AND type='referral' THEN amount ELSE 0 END),0) AS money_sum,
            COALESCE(SUM(CASE WHEN currency='stars' AND type='referral' THEN amount ELSE 0 END),0) AS stars_sum
        FROM transactions WHERE user_id=%s""",
        (user_id,),
    )
    row = await cur.fetchone()
    return {'invited': registered, 'registered': registered, 'money': row['money_sum'], 'stars': row['stars_sum']}


async def get_top_users(conn, currency, limit=10, user_id=None):
    col = 'money' if currency == 'money' else 'stars'
    cur = await conn.execute(
        f"SELECT id,nickname,{col} AS value FROM users ORDER BY {col} DESC,id ASC LIMIT %s",
        (limit,),
    )
    top = await cur.fetchall()
    own = None
    if user_id:
        # PostgreSQL requires an alias for a derived table in this query.
        cur = await conn.execute(
            f"""SELECT pos FROM (
                SELECT id,
                       ROW_NUMBER() OVER (ORDER BY {col} DESC,id ASC) AS pos
                FROM users
            ) AS ranked
            WHERE id=%s""",
            (user_id,),
        )
        own = await cur.fetchone()
    return top, (own[0] if own else None)


async def add_admin_log(conn, admin_user_id, admin_nickname, command, target_user_id=None, target_nickname=None, value=''):
    await conn.execute(
        """INSERT INTO admin_logs(
            admin_user_id,admin_nickname,command,target_user_id,target_nickname,value,created_at
        ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
        (admin_user_id, admin_nickname, command, target_user_id, target_nickname, value, _now()),
    )


async def reset_player(conn, user_id):
    await conn.execute(
        """UPDATE users SET
            money=0,stars=0,privilege='none',house_id=NULL,vip_type=NULL,vip_expires_at=NULL,
            stall_income=0,daily_gift_claimed_at=NULL,monthly_gift_claimed_at=NULL,referred_by_user_id=NULL
        WHERE id=%s""",
        (user_id,),
    )
    await conn.execute("UPDATE resources SET stone=0,wood=0,food=0,ore=0 WHERE user_id=%s", (user_id,))
    await conn.execute("DELETE FROM business_instances WHERE user_id=%s", (user_id,))
    await conn.execute("DELETE FROM businesses WHERE user_id=%s", (user_id,))
    await conn.execute("DELETE FROM user_quests WHERE user_id=%s", (user_id,))
    await conn.execute("UPDATE case_inventory SET money_cases=0,star_cases=0 WHERE user_id=%s", (user_id,))
    await conn.execute("UPDATE users SET referred_by_user_id=NULL WHERE referred_by_user_id=%s", (user_id,))
    await conn.execute("DELETE FROM referrals WHERE inviter_user_id=%s OR invited_user_id=%s", (user_id, user_id))
    await conn.execute("UPDATE users SET last_activity_at=%s WHERE id=%s", (_now(), user_id))
