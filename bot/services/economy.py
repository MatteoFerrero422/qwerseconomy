from decimal import Decimal
from services.businesses import business_income_per_minute, get_business_info, business_stars_per_minute, vip_multiplier

def calculate_income_per_hour(businesses, vip_type=None, vip_expires_at=None):
    base=Decimal('0')
    for b in businesses:
        info=get_business_info(b.business_type)
        if info: base += business_income_per_minute(info,b.level)*b.quantity*60
    return (base*Decimal(str(vip_multiplier(vip_type,vip_expires_at)))).quantize(Decimal('0.001'))

def calculate_income_per_minute(instances, vip_type=None, vip_expires_at=None):
    base=Decimal('0')
    for b in instances:
        info=get_business_info(b['business_type'])
        if info: base += business_income_per_minute(info,b['level'])
    return base*Decimal(str(vip_multiplier(vip_type,vip_expires_at)))

def calculate_star_income_per_minute(instances):
    total=Decimal('0')
    for b in instances:
        info=get_business_info(b['business_type'])
        if info: total += business_stars_per_minute(info,b['level'])
    return total
