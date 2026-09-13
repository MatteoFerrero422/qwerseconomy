import logging
from aiogram import BaseMiddleware
from typing import Any, Awaitable, Callable
from database.database import db
from database import queries
from services.afk import settle_activity

logger = logging.getLogger(__name__)


class EconomyActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any, dict], Awaitable[Any]], event: Any, data: dict):
        user_id = getattr(getattr(event, 'from_user', None), 'id', None)
        if user_id:
            try:
                async with db.connect() as conn:
                    user = await queries.get_user_by_telegram_id(conn, user_id)
                    if user:
                        try:
                            await settle_activity(conn, user.id)
                            await conn.commit()
                        except Exception:
                            # Don't manually rollback here: if this failed
                            # because the connection itself died mid-query,
                            # rollback() on the same dead connection just
                            # raises a second error. `db.connect()` exiting
                            # abnormally already lets the pool deal with the
                            # connection correctly (see database.py).
                            logger.warning("settle_activity failed for user_id=%s", user_id, exc_info=True)
            except Exception:
                # AFK income settlement is a side effect, not the thing the
                # user is waiting for. A transient DB blip here (network hiccup,
                # a connection being recycled) should never stop the user's
                # actual button press/command from being handled.
                logger.warning("DB unavailable while settling activity for user_id=%s", user_id, exc_info=True)
        return await handler(event, data)
