from aiogram import BaseMiddleware
from typing import Any,Awaitable,Callable
from database.database import db
from database import queries
from services.afk import settle_activity
class EconomyActivityMiddleware(BaseMiddleware):
 async def __call__(self,handler:Callable[[Any,dict],Awaitable[Any]],event:Any,data:dict):
  user_id=getattr(getattr(event,'from_user',None),'id',None)
  if user_id:
   async with db.connect() as conn:
    user=await queries.get_user_by_telegram_id(conn,user_id)
    if user:
     try:
      await settle_activity(conn,user.id)
      await conn.commit()
     except Exception:
      await conn.rollback()
  return await handler(event,data)
