from database import queries
TX_PURCHASE='purchase'; TX_SALE='sale'; TX_CREDIT='credit'; TX_DEBIT='debit'; TX_STAR_TOPUP='star_topup'; TX_STAR_WITHDRAW='star_withdraw'; TX_DONATE_PURCHASE='donate_purchase'; TX_CASE='case'; TX_QUEST='quest'; TX_INCOME='income'
CURRENCY_MONEY='money'; CURRENCY_STARS='stars'
async def log_transaction(conn,user_id,tx_type,currency,amount,description,external_id=None):
    return await queries.add_transaction(conn,user_id,tx_type,currency,amount,description,external_id)
