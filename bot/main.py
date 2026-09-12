from keep_alive import keep_alive
keep_alive()

import asyncio,logging
from aiogram import Bot,Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import config
from database.database import db
from middleware import EconomyActivityMiddleware
from handlers import auth,buyer,cases,donate,profile,quests,shop,start,referrals,top,admin
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
async def main():
 await db.init()
 bot=Bot(token=config.BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
 dp=Dispatcher(storage=MemoryStorage())
 dp.message.middleware(EconomyActivityMiddleware()); dp.callback_query.middleware(EconomyActivityMiddleware()); dp.pre_checkout_query.middleware(EconomyActivityMiddleware())
 for r in (start.router,auth.router,profile.router,shop.router,buyer.router,donate.router,cases.router,quests.router,referrals.router,top.router,admin.router): dp.include_router(r)
 await bot.delete_webhook(drop_pending_updates=True); await dp.start_polling(bot)
if __name__=='__main__':
 try: asyncio.run(main())
 except (KeyboardInterrupt,SystemExit): pass