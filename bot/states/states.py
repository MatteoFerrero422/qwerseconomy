from aiogram.fsm.state import State,StatesGroup
class RegisterStates(StatesGroup): nickname=State(); age=State(); password=State()
class LoginStates(StatesGroup): nickname=State(); password=State()
class BuyResourceStates(StatesGroup): quantity=State()
class SellResourceStates(StatesGroup): quantity=State()
class StarsWithdrawStates(StatesGroup): amount=State()
class TopupStates(StatesGroup): amount=State()
