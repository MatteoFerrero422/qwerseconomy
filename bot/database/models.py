from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id:int; telegram_id:int; nickname:str; age:int; password_hash:str; password_salt:str; money:int; stars:int; privilege:str; house_id:Optional[int]; created_at:str; last_activity_at:Optional[str]=None; vip_type:Optional[str]=None; vip_expires_at:Optional[str]=None; referral_code:Optional[str]=None; referred_by_user_id:Optional[int]=None; stall_income:int=0; daily_gift_claimed_at:Optional[str]=None; monthly_gift_claimed_at:Optional[str]=None
    @classmethod
    def from_row(cls,row):
        return cls(row['id'],row['telegram_id'],row['nickname'],row['age'],row['password_hash'],row['password_salt'],row['money'],row['stars'],row['privilege'],row['house_id'],row['created_at'],row['last_activity_at'],row['vip_type'],row['vip_expires_at'],row['referral_code'],row['referred_by_user_id'],row['stall_income'],row['daily_gift_claimed_at'],row['monthly_gift_claimed_at'])
@dataclass
class Resources:
    user_id:int; stone:int; wood:int; food:int; ore:int
    @classmethod
    def from_row(cls,row): return cls(row['user_id'],row['stone'],row['wood'],row['food'],row['ore'])
@dataclass
class Business:
    id:int; user_id:int; business_type:str; level:int; quantity:int; created_at:str
    @classmethod
    def from_row(cls,row): return cls(row['id'],row['user_id'],row['business_type'],row['level'],row['quantity'],row['created_at'])
@dataclass
class Transaction:
    id:int; user_id:int; type:str; currency:str; amount:int; description:str; created_at:str; external_id:Optional[str]=None
    @classmethod
    def from_row(cls,row): return cls(row['id'],row['user_id'],row['type'],row['currency'],row['amount'],row['description'],row['created_at'],row['external_id'])
