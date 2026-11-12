from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def gender_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Я парень 👨", callback_data="gender:male")
    builder.button(text="Я девушка 👩", callback_data="gender:female")
    builder.adjust(1)
    return builder.as_markup()


INSTITUTES = ["ИИС", "ИОМ", "ИУПСиБК", "ИЭФ", "ИМ", "ИГУиП", "ВШБиТ", "Предунивер"]

# Направления по институтам: (текст кнопки, полное название в анкете)
INSTITUTE_PROGRAMS: dict[str, list[tuple[str, str]]] = {
    "ИИС": [
        ("ПИ", "Прикладная информатика"),
        ("БИ", "Бизнес информатика"),
        ("ПМиИ", "Прикладная математика и информатика"),
    ],
    "ИОМ": [
        ("Менеджмент", "Менеджмент"),
        ("Экономика", "Экономика"),
        ("Инноватика", "Инноватика"),
        ("Экология и природопользование", "Экология и природопользование"),
        ("Техн. трансп. процессов", "Технология транспортных процессов"),
    ],
    "ИГУиП": [
        ("Психология", "Психология"),
        ("Социология", "Социология"),
        ("ГМУ", "Государственное и муниципальное управление"),
        ("Юриспруденция", "Юриспруденция"),
        ("Политология", "Политология"),
    ],
    "ИУПСиБК": [
        ("Управление персоналом", "Управление персоналом"),
        ("Гостиничное дело", "Гостиничное дело"),
        ("Менеджмент", "Менеджмент"),
    ],
    "ИЭФ": [
        ("Экономика", "Экономика"),
        ("Менеджмент", "Менеджмент"),
    ],
    "ИМ": [
        ("Менеджмент", "Менеджмент"),
        ("Реклама и СО", "Реклама и связи с общественностью"),
    ],
    "ВШБиТ": [
        ("Разработка новых продуктов", "Разработка новых продуктов для инновационной экономики"),
        ("Трансфер технологий", "Управление трансфером технологий"),
    ],
    "Предунивер": [
        ("Соц.-эконом. профиль", "Социально-экономический профиль"),
        ("Технологический профиль", "Технологический профиль"),
        ("Соц.-гуманит. профиль", "Социально-гуманитарный профиль"),
    ],
}


def institute_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for inst in INSTITUTES:
        builder.button(text=inst, callback_data=f"institute:{inst}")
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup()


def program_kb(institute: str) -> InlineKeyboardMarkup | None:
    """Кнопки направлений для института. None — если список не задан.
    callback_data: program:<институт>:<индекс> — чтобы уложиться в 64 байта.
    """
    programs = INSTITUTE_PROGRAMS.get(institute)
    if not programs:
        return None
    builder = InlineKeyboardBuilder()
    for idx, (label, _value) in enumerate(programs):
        builder.button(text=label, callback_data=f"program:{institute}:{idx}")
    if institute in ("ИИС", "ИЭФ", "ИМ"):
        builder.adjust(2)
    else:
        builder.adjust(1)
    return builder.as_markup()


def resolve_program(institute: str, idx: int) -> str | None:
    """Полное название направления по институту и индексу кнопки."""
    programs = INSTITUTE_PROGRAMS.get(institute) or []
    if 0 <= idx < len(programs):
        return programs[idx][1]
    return None


def course_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in range(1, 7):
        builder.button(text=str(n), callback_data=f"course:{n}")
    builder.adjust(3, 3)
    return builder.as_markup()


def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Смотреть анкеты")
    builder.button(text="👤 Моя анкета")
    builder.button(text="✏️ Редактировать")
    builder.button(text="❌ Удалить анкету")
    builder.adjust(1, 1, 2)
    return builder.as_markup(resize_keyboard=True)


def search_gender_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👩 Искать девушку", callback_data="search_gender:female")
    builder.button(text="👨 Искать парня", callback_data="search_gender:male")
    builder.adjust(1)
    return builder.as_markup()


def skip_description_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="skip_description")
    return builder.as_markup()


def edit_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Имя", callback_data="edit:name")
    builder.button(text="Возраст", callback_data="edit:age")
    builder.button(text="Институт", callback_data="edit:institute")
    builder.button(text="Направление", callback_data="edit:program")
    builder.button(text="Курс", callback_data="edit:course")
    builder.button(text="Описание", callback_data="edit:description")
    builder.button(text="Фото", callback_data="edit:photo")
    builder.button(text="« Назад", callback_data="edit:cancel")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def profile_actions_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️", callback_data=f"like:{user_id}")
    builder.button(text="✉️", callback_data=f"msg:{user_id}")
    builder.button(text="👎", callback_data=f"dislike:{user_id}")
    builder.button(text="🚨 Пожаловаться", callback_data=f"report:{user_id}")
    builder.button(text="💤 Спать", callback_data="sleep")
    builder.adjust(3, 1, 1)
    return builder.as_markup()


def rewind_only_kb() -> InlineKeyboardMarkup:
    """Кнопка под сохранённой прошлой анкетой — вернуть действия бесплатно"""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Вернуть", callback_data="rewind")
    return builder.as_markup()


def restart_search_kb() -> InlineKeyboardMarkup:
    """Кнопка «Начать заново», когда все анкеты просмотрены"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Начать заново", callback_data="restart_search")
    return builder.as_markup()


def report_kb(reported_id: int) -> InlineKeyboardMarkup:
    """Кнопки под жалобой для админа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить анкету", callback_data=f"report_delete:{reported_id}")
    builder.button(text="✖️ Отклонить жалобу", callback_data=f"report_dismiss:{reported_id}")
    builder.adjust(1)
    return builder.as_markup()


def after_match_kb(username: str | None, with_continue: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if username:
        builder.button(text="💬 Написать", url=f"https://t.me/{username}")
    if with_continue:
        builder.button(text="🔍 Дальше смотреть", callback_data="continue_search")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data="confirm_delete")
    builder.button(text="Отмена", callback_data="cancel_delete")
    builder.adjust(2)
    return builder.as_markup()


def liked_you_kb(from_id: int) -> InlineKeyboardMarkup:
    """Кнопки под заявкой"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять заявку", callback_data=f"likeback:{from_id}")
    builder.button(text="✖️ Отклонить", callback_data=f"skipliker:{from_id}")
    builder.adjust(1)
    return builder.as_markup()


def photos_done_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Готово", callback_data="photos_done")
    return builder.as_markup()
