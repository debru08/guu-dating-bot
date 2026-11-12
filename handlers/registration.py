from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import json

from states import Registration
from keyboards import gender_kb, institute_kb, course_kb, main_menu_kb, skip_description_kb, photos_done_kb, program_kb, resolve_program
from database import create_or_update_user, get_user
from config import MIN_AGE, MAX_AGE, MAX_DESCRIPTION_LENGTH

router = Router()

MAX_PHOTOS = 1


def _require_text(message: Message) -> str | None:
    """Вернуть текст или None, если прислали не текст."""
    if not message.text:
        return None
    return message.text.strip()


@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext):
    name = _require_text(message)
    if name is None:
        await message.answer("Нужно отправить имя текстом ✏️")
        return
    if len(name) < 2 or len(name) > 30:
        await message.answer("Имя должно быть от 2 до 30 символов. Попробуй ещё раз:")
        return

    await state.update_data(name=name)
    await state.set_state(Registration.gender)
    await message.answer("Отлично. Теперь выбери пол:", reply_markup=gender_kb())


@router.callback_query(Registration.gender, F.data.startswith("gender:"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await state.set_state(Registration.age)
    await callback.message.edit_text("Сколько тебе лет? (числом)")
    await callback.answer()


@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext):
    text = _require_text(message)
    if text is None:
        await message.answer("Напиши возраст числом, например 19")
        return
    if not text.isdigit():
        await message.answer("Напиши возраст числом, например 19")
        return

    age = int(text)
    if age < MIN_AGE or age > MAX_AGE:
        await message.answer(f"Возраст должен быть от {MIN_AGE} до {MAX_AGE} лет.")
        return

    await state.update_data(age=age)
    await state.set_state(Registration.institute)
    await message.answer("Выбери институт:", reply_markup=institute_kb())


@router.callback_query(Registration.institute, F.data.startswith("institute:"))
async def process_institute(callback: CallbackQuery, state: FSMContext):
    institute = callback.data.split(":", 1)[1]
    await state.update_data(institute=institute)
    await state.set_state(Registration.program)
    kb = program_kb(institute)
    if kb:
        await callback.message.edit_text(
            "Выбери направление:",
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text("Какое у тебя направление? (например, «Экономика»)")
    await callback.answer()


@router.message(Registration.institute)
async def process_institute_invalid(message: Message):
    await message.answer("Выбери институт кнопкой на клавиатуре 👆")


@router.callback_query(Registration.program, F.data.startswith("program:"))
async def process_program_button(callback: CallbackQuery, state: FSMContext):
    """Кнопки направления по институту (callback: program:<институт>:<индекс>)"""
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
    await state.update_data(institute=institute, program=program)
    await state.set_state(Registration.course)
    await callback.message.edit_text(f"Направление: {program}\n\nНа каком ты курсе?")
    await callback.message.answer("Выбери курс:", reply_markup=course_kb())
    await callback.answer()


@router.message(Registration.program)
async def process_program(message: Message, state: FSMContext):
    data = await state.get_data()
    institute = data.get("institute")
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
        await message.answer("Название направления должно быть от 2 до 80 символов. Попробуй ещё раз:")
        return

    await state.update_data(program=program)
    await state.set_state(Registration.course)
    await message.answer("На каком ты курсе?", reply_markup=course_kb())


@router.callback_query(Registration.course, F.data.startswith("course:"))
async def process_course(callback: CallbackQuery, state: FSMContext):
    course = int(callback.data.split(":", 1)[1])
    await state.update_data(course=course)
    await state.set_state(Registration.description)
    await callback.message.edit_text(
        f"Расскажи немного о себе (до {MAX_DESCRIPTION_LENGTH} символов).\n"
        "Можно написать интересы, что ищешь, или просто пару предложений.\n\n"
        "Или нажми «Пропустить», если не хочешь писать описание.",
        reply_markup=skip_description_kb()
    )
    await callback.answer()


@router.message(Registration.course)
async def process_course_invalid(message: Message):
    await message.answer("Выбери курс кнопкой на клавиатуре 👆", reply_markup=course_kb())


@router.callback_query(Registration.description, F.data == "skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description="", photos=[])
    await state.set_state(Registration.photo)
    await callback.message.edit_text(
        "Хорошо, описание пропущено.\n"
        "Пришли одно фото — анкета сохранится сразу."
    )
    await callback.answer()


@router.message(Registration.description)
async def process_description(message: Message, state: FSMContext):
    desc = _require_text(message)
    if desc is None:
        await message.answer(
            "Напиши описание текстом или нажми «Пропустить».",
            reply_markup=skip_description_kb()
        )
        return
    if len(desc) > MAX_DESCRIPTION_LENGTH:
        await message.answer(f"Слишком длинно. Максимум {MAX_DESCRIPTION_LENGTH} символов.")
        return

    await state.update_data(description=desc, photos=[])
    await state.set_state(Registration.photo)
    await message.answer(
        "Пришли одно фото — анкета сохранится сразу."
    )


@router.message(Registration.photo, F.photo)
async def process_photo_add(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"Уже {MAX_PHOTOS} фото — максимум.")
        await _finish_registration(message, state, photos)
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    await message.answer("Фото получено. Сохраняю анкету…")
    await _finish_registration(message, state, photos)


async def _finish_registration(message: Message, state: FSMContext, photos: list):
    data = await state.get_data()
    if not photos:
        await message.answer("Нужно хотя бы одно фото.")
        return

    import json
    description = data.get("description", "")
    await create_or_update_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        name=data["name"],
        gender=data["gender"],
        age=data["age"],
        institute=data.get("institute"),
        program=data.get("program"),
        course=data.get("course"),
        description=description,
        photo_id=photos[0],
        photos=json.dumps(photos),
        status="approved",
    )
    await state.clear()
    await message.answer(
        "Анкета создана! ✅\nТеперь можно смотреть анкеты других.",
        reply_markup=main_menu_kb()
    )


@router.message(Registration.photo, F.text == "/done")
async def process_photos_done_cmd(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    if not photos:
        await message.answer("Сначала пришли хотя бы одно фото.")
        return
    await _finish_registration(message, state, photos)


@router.callback_query(Registration.photo, F.data == "photos_done")
async def process_photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    if not photos:
        await callback.answer("Нужно хотя бы одно фото", show_alert=True)
        return
    import json
    description = data.get("description", "")
    await create_or_update_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        name=data["name"],
        gender=data["gender"],
        age=data["age"],
        institute=data.get("institute"),
        program=data.get("program"),
        course=data.get("course"),
        description=description,
        photo_id=photos[0],
        photos=json.dumps(photos),
        status="approved",
    )
    await state.clear()
    await callback.message.edit_text("Анкета создана! ✅")
    await callback.message.answer(
        "Теперь можно смотреть анкеты других.",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.message(Registration.photo)
async def process_photo_invalid(message: Message):
    await message.answer("Пришли одно фото.")
