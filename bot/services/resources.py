RESOURCES={
 'stone':{'name':'Камень','emoji':'🪨','buy_price':1,'sell_price':1},
 'wood':{'name':'Дерево','emoji':'🌲','buy_price':1,'sell_price':1},
 'food':{'name':'Еда','emoji':'🌾','buy_price':1,'sell_price':1},
 'ore':{'name':'Руда','emoji':'⛏️','buy_price':1,'sell_price':1},
}
def get_resource_info(resource_type): return RESOURCES.get(resource_type)
