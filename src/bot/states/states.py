from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    waiting_target = State()
    waiting_content = State()
    confirm = State()


class ChannelAddStates(StatesGroup):
    waiting_channel = State()
    waiting_type = State()


class UserSearchStates(StatesGroup):
    waiting_query = State()
