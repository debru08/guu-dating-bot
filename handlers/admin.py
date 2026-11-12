from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command

from database import (
    get_photos,
    get_user,
    get_stats,
    get_open_reports,
    add_report,
    resolve_reports,
    delete_user,
)
from keyboards import report_kb
from handlers.search import profile_caption
from config import ADMIN_IDS

router = Router()

EMPTY_KB = InlineKeyboardMarkup(inline_keyboard=[])


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def send_report_card(bot: Bot, chat_id: int, reported_id: int, reporter_id: int):
    """Отправляет админу карточку жалобы: анкета + кнопки действий"""
    reported = await get_user(reported_id)
    if not reported:
        return False

    reporter = await get_user(reporter_id)

    caption = f"🚨 Жалоба на анкету\n\n{profile_caption(reported)}"
    caption += (
        f"\n\nПожаловался: {reporter['name'] if reporter else 'неизвестно'}"
        f"\nID анкеты: <code>{reported_id}</code>"
    )

    await bot.send_photo(
        chat_id=chat_id,
        photo=(get_photos(reported) or [reported["photo_id"]])[0],
        caption=caption,
        parse_mode="HTML",
        reply_markup=report_kb(reported_id)
    )
    return True


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_stats()
    text = (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Всего пользователей: {stats['total']}\n"
        f"Всего лайков: {stats['likes']}\n"
        f"Жалоб: {stats['reports']}\n\n"
        f"Список жалоб: /reports"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("reports"))
async def reports_list(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    reports = await get_open_reports(limit=10)
    if not reports:
        await message.answer("Жалоб нет ✅")
        return

    sent = 0
    for r in reports:
        try:
            ok = await send_report_card(bot, message.from_user.id, r["reported_id"], r["reporter_id"])
            if ok:
                sent += 1
            else:
                await resolve_reports(r["reported_id"])
        except Exception:
            pass

    await message.answer(f"Открытых жалоб: {sent}")


@router.callback_query(F.data.startswith("report:"))
async def process_report(callback: CallbackQuery, bot: Bot):
    """Пользователь нажал «🚨 Пожаловаться» на чужой анкете"""
    reported_id = int(callback.data.split(":")[1])
    reporter_id = callback.from_user.id

    if reported_id == reporter_id:
        await callback.answer("Нельзя пожаловаться на свою анкету")
        return

    reported = await get_user(reported_id)
    if not reported:
        await callback.answer("Эта анкета больше недоступна", show_alert=True)
        return

    is_new = await add_report(reporter_id, reported_id)

    if is_new:
        for admin_id in ADMIN_IDS:
            try:
                await send_report_card(bot, admin_id, reported_id, reporter_id)
            except Exception:
                pass
        await callback.answer("Жалоба отправлена. Спасибо!")
    else:
        await callback.answer("Ты уже жаловался на эту анкету")


@router.callback_query(F.data.startswith("report_delete:"))
async def report_delete(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    reported_id = int(callback.data.split(":")[1])
    user = await get_user(reported_id)

    await delete_user(reported_id)

    if user:
        try:
            await bot.send_message(
                chat_id=reported_id,
                text=(
                    "Твоя анкета была удалена после жалобы.\n"
                    "Если считаешь это ошибкой — создай новую через /start"
                )
            )
        except Exception:
            pass

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n🗑 <b>Анкета удалена</b>",
        parse_mode="HTML",
        reply_markup=EMPTY_KB
    )
    await callback.answer("Анкета удалена")


@router.callback_query(F.data.startswith("report_dismiss:"))
async def report_dismiss(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    reported_id = int(callback.data.split(":")[1])
    await resolve_reports(reported_id)

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n✖️ <b>Жалоба отклонена</b>",
        parse_mode="HTML",
        reply_markup=EMPTY_KB
    )
    await callback.answer("Жалоба закрыта")
