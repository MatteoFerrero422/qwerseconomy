from datetime import datetime, timezone
from decimal import Decimal

D = Decimal

# ЕДИНАЯ таблица уровней для завода, фермы и шахты.
# Цена — стоимость перехода НА указанный уровень.
# Одна общая таблица доходов для ЗАВОДА, ФЕРМЫ и ШАХТЫ.
# Не выводить эти значения через float: Decimal сохраняет точные значения.
BUSINESS_LEVELS = {
    1: {'income_money': D('166.667'), 'income_stars': D('0'), 'price': 50000},
    2: {'income_money': D('250'), 'income_stars': D('0'), 'price': 100000},
    3: {'income_money': D('300'), 'income_stars': D('0'), 'price': 150000},
    4: {'income_money': D('350'), 'income_stars': D('0'), 'price': 200000},
    5: {'income_money': D('400'), 'income_stars': D('0'), 'price': 250000},
    6: {'income_money': D('400'), 'income_stars': D('0.10'), 'price': 500000},
    7: {'income_money': D('500'), 'income_stars': D('0.15'), 'price': 1000000},
}

# Для совместимости со старым кодом: цена перехода на уровень.
UPGRADE_COSTS = {level: data['price'] for level, data in BUSINESS_LEVELS.items() if level >= 2}

# Сохраняем существующие времена улучшений.
UPGRADE_TIMES = {2: 0, 3: 600, 4: 1800, 5: 10800, 6: 0, 7: 0}

# Моментальные улучшения за единую ⭐-валюту.
STAR_UPGRADE_COSTS = {2: 10, 3: 15, 4: 25, 5: 50, 6: 100, 7: 100}

BUSINESSES = {
    'factory': {
        'name': 'Мини-завод', 'emoji': '🏭',
        'purchase_money': BUSINESS_LEVELS[1]['price'],
        'purchase_level': 1,
        'max_level': 7,
        'production': {'wood': 1, 'ore': 1},
    },
    'farm': {
        'name': 'Ферма', 'emoji': '🌾',
        'purchase_money': BUSINESS_LEVELS[2]['price'],
        'purchase_level': 2,
        'max_level': 7,
        'production': {'food': 3},
    },
    'mine': {
        'name': 'Шахта', 'emoji': '⛏️',
        'purchase_money': BUSINESS_LEVELS[2]['price'],
        'purchase_level': 2,
        'max_level': 7,
        'production': {'stone': 4},
    },
    # Ларёк сохраняется как существующий отдельный игровой объект.
    # Единая таблица уровней относится к трём бизнесам: заводу, ферме и шахте.
    'stall': {
        'name': 'Ларёк', 'emoji': '🏪',
        'purchase_money': 5000,
        'purchase_level': 1,
        'max_level': 1,
        'income_by_level': {1: D('50')},
        'stars_by_level': {1: D('0')},
        'production': {},
    },
}

VIP = {
    'bronze': {'name': 'VIP Bronze', 'price': 15, 'multiplier': 1.3},
    'silver': {'name': 'VIP Silver', 'price': 25, 'multiplier': 1.5, 'daily_gift': True},
    'gold': {'name': 'VIP Gold', 'price': 50, 'multiplier': 2.0, 'monthly_gift': True},
}


def get_business_info(business_type):
    return BUSINESSES.get(business_type)


def all_business_types():
    return BUSINESSES


def business_max_level(info):
    return int(info.get('max_level', 1)) if info else 1


def business_purchase_level(info):
    return int(info.get('purchase_level', 1)) if info else 1


def business_level_data(info, level):
    if not info:
        return None
    if info in BUSINESSES.values() and 'production' in info and info.get('max_level') == 7:
        return BUSINESS_LEVELS.get(level)
    return {
        'income_money': (info.get('income_by_level') or {}).get(level, D('0')),
        'income_stars': (info.get('stars_by_level') or {}).get(level, D('0')),
        'price': info.get('purchase_money', 0),
    }


def business_income_per_minute(info, level):
    data = business_level_data(info, level)
    return D(str(data['income_money'])) if data else D('0')


def business_stars_per_minute(info, level):
    data = business_level_data(info, level)
    return D(str(data['income_stars'])) if data else D('0')


def business_production(info, level):
    return {k: v * level for k, v in info.get('production', {}).items()}


def vip_multiplier(vip_type, expires_at):
    if not vip_type or not expires_at:
        return 1.0
    try:
        if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
            return 1.0
    except ValueError:
        return 1.0
    return VIP.get(vip_type, {}).get('multiplier', 1.0)
