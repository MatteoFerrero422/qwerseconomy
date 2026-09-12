from uuid import uuid4
from aiogram.types import LabeledPrice

TOPUP_MIN=1
TOPUP_MAX=1000

def make_topup_payload(amount:int)->str:
    return f"star_topup:{amount}:{uuid4().hex}"

def parse_topup_payload(payload:str):
    parts=payload.split(":")
    if len(parts)!=3 or parts[0]!='star_topup': return None
    try: amount=int(parts[1])
    except ValueError: return None
    return amount if TOPUP_MIN<=amount<=TOPUP_MAX else None

def invoice_prices(amount:int):
    return [LabeledPrice(label=f"{amount} Telegram Stars", amount=amount)]
