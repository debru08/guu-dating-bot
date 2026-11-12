from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database import get_user
from keyboards import main_menu_kb, gender_kb
from states import Registration
from config import ADMIN_IDS

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)

    if user:
        await message.answer(
            f"С возвращением, {user['name']}! 👋\n\n"
            "Что делаем?",
            reply_markup=main_menu_kb()
        )
    else:
        await message.answer(
            "Привет! Это бот знакомств для студентов ГУУ 🎓\n\n"
            "Здесь можно найти новых друзей и, возможно, нечто большее.\n\n"
            "Давай создадим твою анкету.\n\n"
            "Как тебя зовут?"
        )
        await state.set_state(Registration.name)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer("Главное меню:", reply_markup=main_menu_kb())
    else:
        await message.answer("Сначала нужно создать анкету. Нажми /start")
