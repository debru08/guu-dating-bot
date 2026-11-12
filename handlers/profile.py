from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
import json

from database import get_user, create_or_update_user, delete_user, get_photos
from keyboards import (
    main_menu_kb,
    confirm_delete_kb,
    edit_menu_kb,
    skip_description_kb,
    institute_kb,
    course_kb,
    photos_done_kb,
    program_kb,
    resolve_program,
)
from states import EditProfile
from handlers.search import profile_caption
from config import MIN_AGE, MAX_AGE, MAX_DESCRIPTION_LENGTH

router = Router()
MAX_PHOTOS = 1


def _require_text(message: Message) -> str | None:
    if not message.text:
        return None
    return message.text.strip()


@router.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("У тебя ещё нет анкеты. Нажми /start")
        return

    caption = profile_caption(user)
    photos = get_photos(user)
    if not photos:
        await message.answer("В анкете нет фото. Отредактируй анкету.")
        return

    if len(photos) == 1:
        await message.answer_photo(photo=photos[0], caption=caption, parse_mode="HTML")
    else:
        media = [InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")]
        for pid in photos[1:]:
            media.append(InputMediaPhoto(media=pid))
        await message.answer_media_group(media=media)


@router.message(F.text == "✏️ Редактировать")
async def edit_profile_start(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала создай анкету через /start")
        return

    await state.clear()
    await message.answer("Что хочешь изменить?", reply_markup=edit_menu_kb())


@router.callback_query(F.data == "edit:cancel")
async def edit_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Редактирование отменено.")
    await callback.answer()


@router.callback_query(F.data == "edit:name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.name)
    await callback.message.edit_text("Введи новое имя:")
    await callback.answer()


@router.callback_query(F.data == "edit:age")
async def edit_age_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.age)
    await callback.message.edit_text("Введи новый возраст (числом):")
    await callback.answer()


@router.callback_query(F.data == "edit:institute")
async def edit_institute_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.institute)
    await callback.message.edit_text("Выбери институт:", reply_markup=institute_kb())
    await callback.answer()


@router.callback_query(F.data == "edit:program")
async def edit_program_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.program)
    user = await get_user(callback.from_user.id)
    institute = user["institute"] if user else None
    kb = program_kb(institute) if institute else None
    if kb:
        await callback.message.edit_text(
            "Выбери направление:",
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text("Введи новое направление подготовки:")
    await callback.answer()


@router.callback_query(F.data == "edit:course")
async def edit_course_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.course)
    await callback.message.edit_text("Выбери курс:", reply_markup=course_kb())
    await callback.answer()


@router.callback_query(F.data == "edit:description")
async def edit_description_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.description)
    await callback.message.edit_text(
        f"Введи новое описание (до {MAX_DESCRIPTION_LENGTH} символов)\n"
        "или нажми «Пропустить», чтобы убрать описание:",
        reply_markup=skip_description_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "edit:photo")
async def edit_photo_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.photo)
    await state.update_data(photos=[])
    await callback.message.edit_text(
        "Пришли одно новое фото.\n"
        "Старое будет заменено — сохранится сразу."
    )
    await callback.answer()


async def after_edit(message: Message):
    await message.answer("Изменения сохранены ✅", reply_markup=main_menu_kb())


@router.message(EditProfile.name)
async def edit_name_save(message: Message, state: FSMContext):
    name = _require_text(message)
    if name is None:
        await message.answer("Нужно отправить имя текстом ✏️")
        return
    if len(name) < 2 or len(name) > 30:
        await message.answer("Имя должно быть от 2 до 30 символов. Попробуй ещё раз:")
        return

    await create_or_update_user(message.from_user.id, name=name)
    await state.clear()
    await after_edit(message)


@router.message(EditProfile.age)
async def edit_age_save(message: Message, state: FSMContext):
    text = _require_text(message)
    if text is None or not text.isdigit():
        await message.answer("Напиши возраст числом:")
        return

    age = int(text)
    if age < MIN_AGE or age > MAX_AGE:
        await message.answer(f"Возраст должен быть от {MIN_AGE} до {MAX_AGE}.")
        return

    await create_or_update_user(message.from_user.id, age=age)
    await state.clear()
    await after_edit(message)


@router.callback_query(EditProfile.institute, F.data.startswith("institute:"))
async def edit_institute_save(callback: CallbackQuery, state: FSMContext):
    institute = callback.data.split(":", 1)[1]
    # Сохраняем институт и сбрасываем старое направление — нужно выбрать новое
    await create_or_update_user(callback.from_user.id, institute=institute, program="")
    await state.set_state(EditProfile.program)
    kb = program_kb(institute)
    if kb:
        await callback.message.edit_text(
            f"Институт: {institute}\n\nТеперь выбери направление:",
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text(
            f"Институт: {institute}\n\nВведи направление текстом:"
        )
    await callback.answer()


@router.message(EditProfile.institute)
async def edit_institute_invalid(message: Message):
    await message.answer("Выбери институт кнопкой ниже:", reply_markup=institute_kb())


@router.callback_query(EditProfile.program, F.data.startswith("program:"))
async def edit_program_button(callback: CallbackQuery, state: FSMContext):
    """Кнопки направления (callback: program:<институт>:<индекс>)"""
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные", show_alert=True)
        return
    _, institute, idx_s = parts
    try:
        idx = int(idx_s)
    except ValueError:
        await callback.answer("Некорректные данные", show_alert=True)
        return
    program = resolve_program(institute, idx)
    if not program:
        await callback.answer("Направление не найдено", show_alert=True)
        return
    await create_or_update_user(callback.from_user.id, program=program)
    await state.clear()
    await callback.message.edit_text(f"Направление изменено: {program}")
    await callback.message.answer("Изменения сохранены ✅", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(EditProfile.program)
async def edit_program_save(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    institute = user["institute"] if user else None
    kb = program_kb(institute) if institute else None
    if kb:
        await message.answer(
            "Выбери направление кнопкой 👆",
            reply_markup=kb,
        )
        return

    program = _require_text(message)
    if program is None:
        await message.answer("Напиши направление текстом ✏️")
        return
    if len(program) < 2 or len(program) > 80:
        await message.answer("Направление должно быть от 2 до 80 символов. Попробуй ещё раз:")
        return

    await create_or_update_user(message.from_user.id, program=program)
    await state.clear()
    await after_edit(message)


@router.callback_query(EditProfile.course, F.data.startswith("course:"))
async def edit_course_save(callback: CallbackQuery, state: FSMContext):
    course = int(callback.data.split(":", 1)[1])
    await create_or_update_user(callback.from_user.id, course=course)
    await state.clear()
    await callback.message.edit_text(f"Курс обновлён: {course}")
    await callback.message.answer("Изменения сохранены ✅", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(EditProfile.course)
async def edit_course_invalid(message: Message):
    await message.answer("Выбери курс кнопкой на клавиатуре 👆", reply_markup=course_kb())


@router.callback_query(EditProfile.description, F.data == "skip_description")
async def edit_description_skip(callback: CallbackQuery, state: FSMContext):
    await create_or_update_user(callback.from_user.id, description="")
    await state.clear()
    await callback.message.edit_text("Описание убрано.")
    await callback.message.answer("Изменения сохранены ✅", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(EditProfile.description)
async def edit_description_save(message: Message, state: FSMContext):
    desc = _require_text(message)
    if desc is None:
        await message.answer("Напиши описание текстом или нажми «Пропустить».", reply_markup=skip_description_kb())
        return
    if len(desc) > MAX_DESCRIPTION_LENGTH:
        await message.answer(f"Максимум {MAX_DESCRIPTION_LENGTH} символов.")
        return

    await create_or_update_user(message.from_user.id, description=desc)
    await state.clear()
    await after_edit(message)


@router.message(EditProfile.photo, F.photo)
async def edit_photo_add(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"Уже {MAX_PHOTOS} фото.")
        await _save_edit_photos(message, state, photos)
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    await message.answer("Фото получено. Сохраняю…")
    await _save_edit_photos(message, state, photos)


async def _save_edit_photos(message: Message, state: FSMContext, photos: list):
    if not photos:
        await message.answer("Нужно хотя бы одно фото.")
        return
    await create_or_update_user(
        message.from_user.id,
        photo_id=photos[0],
        photos=json.dumps(photos),
    )
    await state.clear()
    await after_edit(message)


@router.message(EditProfile.photo, F.text == "/done")
async def edit_photos_done_cmd(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    if not photos:
        await message.answer("Сначала пришли фото.")
        return
    await _save_edit_photos(message, state, photos)


@router.callback_query(EditProfile.photo, F.data == "photos_done")
async def edit_photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    if not photos:
        await callback.answer("Нужно хотя бы одно фото", show_alert=True)
        return
    await create_or_update_user(
        callback.from_user.id,
        photo_id=photos[0],
        photos=json.dumps(photos),
    )
    await state.clear()
    await callback.message.edit_text("Фото обновлены ✅")
    await callback.message.answer("Изменения сохранены ✅", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(EditProfile.photo)
async def edit_photo_invalid(message: Message):
    await message.answer("Пришли одно фото.")


@router.message(F.text == "❌ Удалить анкету")
async def delete_profile_request(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("У тебя нет анкеты.")
        return

    await message.answer(
        "Точно хочешь удалить свою анкету?\nЭто действие нельзя отменить.",
        reply_markup=confirm_delete_kb()
    )


@router.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback: CallbackQuery):
    await delete_user(callback.from_user.id)
    await callback.message.edit_text("Анкета удалена.\nКогда захочешь — создай новую через /start")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Удаление отменено.")
    await callback.answer()
