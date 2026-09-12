from database import queries
from services.transactions import CURRENCY_MONEY,CURRENCY_STARS,TX_QUEST,log_transaction

QUEST_REQUIREMENTS={1:1,2:1,3:1000,4:1,5:1}

def format_stars(units:int)->str:
    if units%100==0: return str(units//100)
    return f"{units/100:.2f}".rstrip('0').rstrip('.')

async def auto_claim(conn,user_id,quest_id):
    row=await queries.claim_quest(conn,user_id,quest_id)
    if not row: return False
    if row['reward_money']:
        await log_transaction(conn,user_id,TX_QUEST,CURRENCY_MONEY,row['reward_money'],f"Награда за задание: {row['title']}")
    if row['reward_stars']:
        units=int(round(row['reward_stars']*100))
        await log_transaction(conn,user_id,TX_QUEST,CURRENCY_STARS,units,f"Награда за задание: {row['title']}")
    return True

async def progress(conn,user_id,quest_id,value):
    await queries.set_quest_progress(conn,user_id,quest_id,value,QUEST_REQUIREMENTS[quest_id])
    return await auto_claim(conn,user_id,quest_id)
