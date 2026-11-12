from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from database import (
    get_user,
    get_next_profile,
    add_view,
    add_like,
    is_mutual,
    get_photos,
    remove_view,
    clear_views,
    count_profiles,
)
from keyboards import (
    profile_actions_kb,
    after_match_kb,
    main_menu_kb,
    search_gender_kb,
    liked_you_kb,
    rewind_only_kb,
    restart_search_kb,
)
from states import SendMessage

router = Router()

# user_id -> gender_filter
search_filters = {}
# user_id -> id предыдущей анкеты (для бесплатного возврата)
last_profiles: dict[int, int] = {}
# user_id -> id текущей показанной анкеты
current_profiles: dict[int, int] = {}
# user_id -> message_id всех сообщений текущей анкеты (фото + кнопки)
profile_messages: dict[int, list[int]] = {}


def profile_caption(profile) -> str:
    """Собирает текст анкеты с разделителями"""
    caption = f"<b>{profile['name']}</b>, {profile['age']}"

    edu = []
    if profile["institute"]:
        edu.append(f"Институт: {profile['institute']}")
    if profile["program"]:
        edu.append(f"Направление: {profile['program']}")
    if profile["course"]:
        edu.append(f"Курс: {profile['course']}")

    if edu:
        caption += "\n-----------\n" + "\n".join(edu)

    if profile["description"]:
        caption += "\n-----------\n" + profile["description"]

    return caption


async def safe_delete(message):
    """Безопасное удаление сообщения"""
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def clear_profile_messages(bot: Bot, chat_id: int, viewer_id: int):
    """Удаляет все сообщения текущей анкеты (медиагруппа + кнопки)."""
    ids = profile_messages.pop(viewer_id, [])
    for mid in ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass


async def show_profile(target, profile, from_callback: bool = False):
    """
    Показывает анкету одним блоком:
    - 1 фото: фото + текст + кнопки в одном сообщении
    - несколько фото: альбом с текстом, сразу под ним — кнопки
    Перед показом удаляет предыдущий блок анкеты целиком.
    """
    from aiogram.types import InputMediaPhoto, CallbackQuery

    caption = profile_caption(profile)
    photos = get_photos(profile)
    if not photos:
        return

    if isinstance(target, CallbackQuery):
        bot = target.bot
        chat_id = target.message.chat.id
        viewer_id = target.from_user.id
    else:
        bot = target.bot
        chat_id = target.chat.id
        viewer_id = target.from_user.id

    # Убираем прошлую анкету целиком (все фото + кнопки)
    await clear_profile_messages(bot, chat_id, viewer_id)
    if from_callback and isinstance(target, CallbackQuery):
        await safe_delete(target.message)

    current_profiles[viewer_id] = profile["user_id"]
    kb = profile_actions_kb(int(profile["user_id"]))
    msg_ids: list[int] = []

    try:
        if len(photos) == 1:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=photos[0],
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
            msg_ids.append(msg.message_id)
        else:
            media = [InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")]
            for pid in photos[1:]:
                media.append(InputMediaPhoto(media=pid))
            album = await bot.send_media_group(chat_id=chat_id, media=media)
            msg_ids.extend(m.message_id for m in album)
            # Медиагруппа не поддерживает кнопки — сразу под альбомом
            btn_msg = await bot.send_message(
                chat_id=chat_id,
                text="\u200b",
                reply_markup=kb,
            )
            msg_ids.append(btn_msg.message_id)
    except Exception:
        # Если альбом уже ушёл, не дублируем фото — только кнопки, если их ещё нет
        if not msg_ids:
            try:
                msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photos[0],
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                msg_ids.append(msg.message_id)
            except Exception:
                pass
        elif len(photos) > 1:
            try:
                btn_msg = await bot.send_message(
                    chat_id=chat_id,
                    text="\u200b",
                    reply_markup=kb,
                )
                msg_ids.append(btn_msg.message_id)
            except Exception:
                pass

    if msg_ids:
        profile_messages[viewer_id] = msg_ids


async def notify_liked(bot: Bot, from_id: int, to_id: int, message_text: str | None = None):
    """Отправляет to_id заявку от from_id (с анкетой отправителя и опциональным сообщением)"""
    target = await get_user(to_id)
    if not target:
        return
    me = await get_user(from_id)
    photos = get_photos(me)
    if not me or not photos:
        return

    caption = f"💌 Новая заявка!\n\n{profile_caption(me)}"
    if message_text:
        caption += f"\n\n✉️ Сообщение:\n<i>{message_text}</i>"
    caption += "\n\nПрими заявку — и этот человек получит доступ к твоей анкете и сможет написать тебе."

    try:
        await bot.send_photo(
            chat_id=to_id,
            photo=photos[0],
            caption=caption,
            parse_mode="HTML",
            reply_markup=liked_you_kb(from_id)
        )
        for pid in photos[1:]:
            try:
                await bot.send_photo(chat_id=to_id, photo=pid)
            except Exception:
                pass
    except Exception:
        pass


async def send_match_to(bot: Bot, to_id: int, other_id: int, header: str = "🔥 У тебя взаимная симпатия!"):
    """Сообщает to_id, что заявка принята и теперь доступна анкета other_id"""
    other = await get_user(other_id)
    if not other:
        return
    text = f"{header}\n\n{profile_caption(other)}"
    photos = get_photos(other)
    if not photos:
        return
    try:
        await bot.send_photo(
            chat_id=to_id,
            photo=photos[0],
            caption=text,
            parse_mode="HTML",
            reply_markup=after_match_kb(other["username"])
        )
        for pid in photos[1:]:
            try:
                await bot.send_photo(chat_id=to_id, photo=pid)
            except Exception:
                pass
    except Exception:
        pass





async def send_saved_previous(bot: Bot, chat_id: int, profile_id: int):
    """Показывает прошлую анкету только с фото и кнопкой «Вернуть»."""
    profile = await get_user(profile_id)
    if not profile:
        return
    photos = get_photos(profile)
    if not photos:
        return
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photos[0],
            caption="💾 Прошлая анкета",
            reply_markup=rewind_only_kb(),
        )
    except Exception:
        pass


def remember_previous(viewer_id: int, leaving_profile_id: int):
    """Сохраняет анкету, с которой уходим (для бесплатного возврата)."""
    if leaving_profile_id:
        last_profiles[viewer_id] = leaving_profile_id


async def answer_no_profiles(target, viewer_id: int, gender_filter: str | None, from_callback: bool = False):
    """Сообщение, когда анкет больше нет: либо никого нет, либо всё просмотрено — предложить начать заново."""
    total = await count_profiles(gender_filter=gender_filter, exclude_id=viewer_id)
    if total == 0:
        if gender_filter == "female":
            text = "Пока нет анкет девушек 😔"
        elif gender_filter == "male":
            text = "Пока нет анкет парней 😔"
        else:
            text = "Пока нет анкет 😔"
        kb = main_menu_kb()
        if from_callback:
            await target.message.answer(text, reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)
        return

    text = (
        "Ты просмотрел все доступные анкеты.\n"
        "Нажми «Начать заново», чтобы смотреть их снова."
    )
    if from_callback:
        await target.message.answer(text, reply_markup=restart_search_kb())
    else:
        await target.answer(text, reply_markup=restart_search_kb())


def get_filter(user_id: int):
    return search_filters.get(user_id)


@router.message(F.text == "🔍 Смотреть анкеты")
async def start_search(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("У тебя ещё нет анкеты. Нажми /start")
        return

    await message.answer(
        "Кого будем искать?",
        reply_markup=search_gender_kb()
    )


@router.callback_query(F.data.startswith("search_gender:"))
async def choose_search_gender(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала создай анкету через /start", show_alert=True)
        return

    choice = callback.data.split(":")[1]  # female / male
    search_filters[callback.from_user.id] = choice

    profile = await get_next_profile(callback.from_user.id, gender_filter=choice)

    if not profile:
        await answer_no_profiles(callback, callback.from_user.id, choice, from_callback=True)
        await callback.answer()
        return

    await add_view(callback.from_user.id, profile["user_id"])
    await show_profile(callback, profile, from_callback=True)
    await callback.answer()


@router.callback_query(F.data.startswith("like:"))
async def process_like(callback: CallbackQuery, bot: Bot):
    to_id = int(callback.data.split(":")[1])
    from_id = callback.from_user.id

    user = await get_user(from_id)
    if not user:
        await callback.answer("Сначала создай анкету через /start", show_alert=True)
        return

    is_mutual_flag, is_new = await add_like(from_id, to_id)
    await add_view(from_id, to_id)

    if is_mutual_flag:
        # Сообщаем второму, что заявка принята и анкета доступна
        await send_match_to(bot, to_id, from_id)

        # Показываем мэтч мне — без кнопки «Дальше», анкета перелистнётся сама
        target = await get_user(to_id)
        await clear_profile_messages(bot, callback.message.chat.id, from_id)
        await safe_delete(callback.message)
        photos = get_photos(target)
        if photos:
            await callback.message.answer_photo(
                photo=photos[0],
                caption=f"🔥 Взаимная симпатия!\n\n{profile_caption(target)}",
                parse_mode="HTML",
                reply_markup=after_match_kb(target["username"], with_continue=False)
                if target["username"] else None
            )
            for pid in photos[1:]:
                try:
                    await callback.message.answer_photo(photo=pid)
                except Exception:
                    pass
        await callback.answer("Взаимно! 🔥")
    else:
        await callback.answer("Заявка отправлена ✅")
        if is_new:
            await notify_liked(bot, from_id, to_id)

    # После лайка показываем следующую; прошлую можно вернуть кнопкой
    remember_previous(from_id, to_id)
    await send_saved_previous(bot, from_id, to_id)

    gender_filter = get_filter(from_id)
    next_profile = await get_next_profile(from_id, gender_filter=gender_filter)

    if next_profile:
        await add_view(from_id, next_profile["user_id"])
        await show_profile(callback, next_profile, from_callback=True)
    else:
        await safe_delete(callback.message)
        await answer_no_profiles(callback, from_id, gender_filter, from_callback=True)


@router.callback_query(F.data.startswith("dislike:"))
async def process_dislike(callback: CallbackQuery, bot: Bot):
    to_id = int(callback.data.split(":")[1])
    from_id = callback.from_user.id

    user = await get_user(from_id)
    if not user:
        await callback.answer()
        return

    await add_view(from_id, to_id)
    remember_previous(from_id, to_id)
    await send_saved_previous(bot, from_id, to_id)
    await callback.answer()

    gender_filter = get_filter(from_id)
    next_profile = await get_next_profile(from_id, gender_filter=gender_filter)

    if next_profile:
        await add_view(from_id, next_profile["user_id"])
        await show_profile(callback, next_profile, from_callback=True)
    else:
        await safe_delete(callback.message)
        await answer_no_profiles(callback, from_id, gender_filter, from_callback=True)


@router.callback_query(F.data == "sleep")
async def process_sleep(callback: CallbackQuery):
    await clear_profile_messages(callback.bot, callback.message.chat.id, callback.from_user.id)
    await safe_delete(callback.message)
    await callback.message.answer(
        "Отдыхай! Когда захочешь продолжить — жми «🔍 Смотреть анкеты»",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "continue_search")
async def continue_search(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return

    gender_filter = get_filter(callback.from_user.id)
    profile = await get_next_profile(callback.from_user.id, gender_filter=gender_filter)

    if profile:
        await add_view(callback.from_user.id, profile["user_id"])
        await show_profile(callback, profile, from_callback=True)
    else:
        await answer_no_profiles(callback, callback.from_user.id, gender_filter, from_callback=True)
    await callback.answer()


@router.callback_query(F.data.startswith("likeback:"))
async def process_like_back(callback: CallbackQuery, bot: Bot):
    """Принять заявку — открыть доступ к своей анкете и получить доступ к анкете отправителя"""
    liker_id = int(callback.data.split(":")[1])
    my_id = callback.from_user.id

    me = await get_user(my_id)
    if not me:
        await callback.answer("Сначала создай анкету через /start", show_alert=True)
        return

    liker = await get_user(liker_id)
    if not liker:
        await safe_delete(callback.message)
        await callback.answer("Эта анкета больше недоступна", show_alert=True)
        return

    already = await is_mutual(my_id, liker_id)
    await add_like(my_id, liker_id)
    await add_view(my_id, liker_id)
    await safe_delete(callback.message)

    if already:
        await callback.answer("Вы уже понравились друг другу 🔥")
        return

    # Отправителю заявки — доступ к моей анкете
    await send_match_to(
        bot, liker_id, my_id,
        header="✅ Твоя заявка принята! Теперь тебе доступна эта анкета:"
    )
    # Тому, кто принял — анкета отправителя
    await send_match_to(
        bot, my_id, liker_id,
        header="🎉 Заявка принята! Теперь вы можете написать друг другу:"
    )
    await callback.answer("Заявка принята ✅")


@router.callback_query(F.data.startswith("skipliker:"))
async def process_skip_liker(callback: CallbackQuery):
    liker_id = int(callback.data.split(":")[1])
    await add_view(callback.from_user.id, liker_id)
    await safe_delete(callback.message)
    await callback.answer("Заявка отклонена")


@router.callback_query(F.data.startswith("msg:"))
async def process_msg_start(callback: CallbackQuery, state: FSMContext):
    """Начать отправку сообщения + лайк"""
    to_id = int(callback.data.split(":")[1])
    from_id = callback.from_user.id

    user = await get_user(from_id)
    if not user:
        await callback.answer("Сначала создай анкету через /start", show_alert=True)
        return

    await state.set_state(SendMessage.waiting)
    await state.update_data(msg_to_id=to_id)
    await callback.message.answer(
        "Напиши сообщение, которое увидит этот человек вместе с твоей заявкой.\n"
        "Или /cancel чтобы отменить."
    )
    await callback.answer()


@router.message(SendMessage.waiting, F.text == "/cancel")
async def process_msg_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu_kb())


@router.message(SendMessage.waiting)
async def process_msg_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    to_id = data.get("msg_to_id")
    from_id = message.from_user.id
    await state.clear()

    if not to_id:
        await message.answer("Что-то пошло не так. Попробуй ещё раз.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Нужен текст сообщения. Попробуй ещё раз через ✉️")
        return
    if len(text) > 500:
        await message.answer("Слишком длинное сообщение (макс. 500 символов).")
        return

    user = await get_user(from_id)
    if not user:
        await message.answer("Сначала создай анкету через /start")
        return

    is_mutual_flag, is_new = await add_like(from_id, to_id)
    await add_view(from_id, to_id)

    if is_mutual_flag:
        await send_match_to(bot, to_id, from_id)
        target = await get_user(to_id)
        if target:
            photos = get_photos(target)
            if photos:
                await message.answer_photo(
                    photo=photos[0],
                    caption=f"🔥 Взаимная симпатия!\n\n{profile_caption(target)}",
                    parse_mode="HTML",
                    reply_markup=after_match_kb(target["username"], with_continue=False)
                    if target.get("username") else None
                )
                for pid in photos[1:]:
                    try:
                        await message.answer_photo(photo=pid)
                    except Exception:
                        pass
        await message.answer("Взаимно! 🔥 Твоё сообщение тоже доставлено.")
    else:
        if is_new:
            await notify_liked(bot, from_id, to_id, message_text=text)
        else:
            # уже лайкали раньше — всё равно отправим сообщение отдельным уведомлением
            await notify_liked(bot, from_id, to_id, message_text=text)
        await message.answer("Заявка и сообщение отправлены ✉️✅")

    remember_previous(from_id, to_id)
    await send_saved_previous(bot, from_id, to_id)

    gender_filter = get_filter(from_id)
    next_profile = await get_next_profile(from_id, gender_filter=gender_filter)
    if next_profile:
        await add_view(from_id, next_profile["user_id"])
        await show_profile(message, next_profile, from_callback=False)
    else:
        await answer_no_profiles(message, from_id, gender_filter, from_callback=False)


@router.callback_query(F.data == "rewind")
async def process_rewind(callback: CallbackQuery):
    """Бесплатно вернуть предыдущую анкету с действиями."""
    uid = callback.from_user.id
    prev_id = last_profiles.get(uid)
    if not prev_id:
        await callback.answer("Нечего возвращать", show_alert=True)
        return

    prev = await get_user(prev_id)
    if not prev:
        last_profiles.pop(uid, None)
        await callback.answer("Та анкета больше недоступна", show_alert=True)
        return

    await remove_view(uid, prev_id)
    last_profiles.pop(uid, None)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await show_profile(callback, prev, from_callback=True)
    await callback.answer("Анкета возвращена")


@router.callback_query(F.data == "restart_search")
async def process_restart_search(callback: CallbackQuery):
    """Сбросить просмотры и начать круг заново."""
    uid = callback.from_user.id
    user = await get_user(uid)
    if not user:
        await callback.answer("Сначала создай анкету через /start", show_alert=True)
        return

    await clear_views(uid)
    gender_filter = get_filter(uid)
    profile = await get_next_profile(uid, gender_filter=gender_filter)

    if not profile:
        await answer_no_profiles(callback, uid, gender_filter, from_callback=True)
        await callback.answer()
        return

    await add_view(uid, profile["user_id"])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_profile(callback, profile, from_callback=True)
    await callback.answer("Начинаем заново 🔄")
