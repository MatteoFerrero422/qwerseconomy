from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from database import queries
from services.businesses import business_production, get_business_info, vip_multiplier
from services.economy import calculate_income_per_minute, calculate_star_income_per_minute
from services.transactions import CURRENCY_MONEY,CURRENCY_STARS,TX_INCOME,log_transaction
from services.quests import progress as quest_progress

def parse_time(s): return datetime.fromisoformat(s) if s else datetime.now(timezone.utc)

async def settle_activity(conn,user_id):
    await queries.clear_vip_if_expired(conn,user_id)
    await queries.complete_ready_upgrades(conn,user_id)
    user=await queries.get_user_by_id(conn,user_id)
    last=parse_time(user.last_activity_at)
    now=datetime.now(timezone.utc)
    elapsed=max(0,(now-last).total_seconds())
    instances=await queries.get_business_instances(conn,user_id)
    money_per_min=calculate_income_per_minute(instances,user.vip_type,user.vip_expires_at)
    exact_money=money_per_min*Decimal(str(elapsed))/Decimal('60')
    income=int(exact_money.to_integral_value(rounding=ROUND_DOWN))
    if income:
        await queries.update_user_money(conn,user_id,income)
        await log_transaction(conn,user_id,TX_INCOME,CURRENCY_MONEY,income,f"Пассивный доход за {int(elapsed)} сек.")
    # Business-generated ⭐ are added to the same unified users.stars balance as Telegram Stars.
    star_per_min=calculate_star_income_per_minute(instances)
    exact_stars=star_per_min*Decimal(str(elapsed))/Decimal('60')
    star_units=int((exact_stars*100).to_integral_value(rounding=ROUND_DOWN))
    if star_units:
        await queries.add_business_stars(conn,user_id,star_units)
        await log_transaction(conn,user_id,TX_INCOME,CURRENCY_STARS,star_units,'⭐ Доход от бизнеса')
    produced={}
    cycles=int(elapsed//60)
    if cycles>0:
        for r in instances:
            info=get_business_info(r['business_type'])
            if not info: continue
            for resource,amount in business_production(info,r['level']).items(): produced[resource]=produced.get(resource,0)+amount*cycles
    stall_rate=Decimal('0')
    for r in instances:
        if r['business_type']=='stall': stall_rate += calculate_income_per_minute([r],None,None)
    stall_income=int((stall_rate*Decimal(str(elapsed))/Decimal('60')*Decimal(str(vip_multiplier(user.vip_type,user.vip_expires_at)))).to_integral_value(rounding=ROUND_DOWN))
    if stall_income:
        await queries.add_stall_income(conn,user_id,stall_income)
        current=await queries.get_user_by_id(conn,user_id)
        if current.stall_income>=1000: await quest_progress(conn,user_id,3,1000)
    for resource,amount in produced.items():
        if amount: await queries.update_resource(conn,user_id,resource,amount)
    await queries.set_last_activity(conn,user_id,now.isoformat())
    return income,produced,elapsed,star_units
