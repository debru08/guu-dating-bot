import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from handlers import start, registration, search, profile, admin

logging.basicConfig(level=logging.INFO)


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_СЮДА":
        print("❌ Ошибка: укажи BOT_TOKEN в config.py или в .env")
        return

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(search.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)

    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
