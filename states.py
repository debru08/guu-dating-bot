from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    name = State()
    gender = State()
    age = State()
    institute = State()
    program = State()
    course = State()
    description = State()
    photo = State()


class EditProfile(StatesGroup):
    name = State()
    age = State()
    institute = State()
    program = State()
    course = State()
    description = State()
    photo = State()


class SendMessage(StatesGroup):
    waiting = State()

