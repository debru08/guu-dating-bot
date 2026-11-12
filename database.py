import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "dating.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                gender TEXT,
                age INTEGER,
                city TEXT,
                institute TEXT,
                program TEXT,
                course INTEGER,
                description TEXT,
                photo_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                from_id INTEGER,
                to_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (from_id, to_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS views (
                viewer_id INTEGER,
                viewed_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (viewer_id, viewed_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                reporter_id INTEGER,
                reported_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (reporter_id, reported_id)
            )
        """)
        await db.commit()

    async with aiosqlite.connect(DB_PATH) as db:
        for column in ("institute TEXT", "program TEXT", "course INTEGER", "photos TEXT"):
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {column}")
                await db.commit()
            except aiosqlite.OperationalError:
                pass


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def create_or_update_user(user_id: int, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        # check existence inside same connection
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            existing = await cursor.fetchone()

        if existing:
            fields = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [user_id]
            await db.execute(
                f"UPDATE users SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                values
            )
        else:
            columns = ["user_id"] + list(kwargs.keys())
            placeholders = ", ".join("?" for _ in columns)
            values = [user_id] + list(kwargs.values())
            await db.execute(
                f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
        await db.commit()


async def add_report(reporter_id: int, reported_id: int) -> bool:
    """
    Добавляет жалобу на анкету.
    Возвращает True, если жалоба новая (повтор от того же человека не считается).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO reports (reporter_id, reported_id) VALUES (?, ?)",
            (reporter_id, reported_id)
        )
        is_new = cursor.rowcount > 0
        await db.commit()
        return is_new


async def get_open_reports(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT r.reported_id, r.reporter_id,
                   ru.name AS reported_name, ru.age AS reported_age,
                   qu.name AS reporter_name
            FROM reports r
            JOIN users ru ON ru.user_id = r.reported_id
            LEFT JOIN users qu ON qu.user_id = r.reporter_id
            ORDER BY r.created_at ASC
            LIMIT ?
            """,
            (limit,)
        ) as cursor:
            return await cursor.fetchall()


async def resolve_reports(reported_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reports WHERE reported_id = ?", (reported_id,))
        await db.commit()


async def clear_views(viewer_id: int):
    """Удалить все просмотры пользователя (служебное)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM views WHERE viewer_id = ?", (viewer_id,))
        await db.commit()


async def get_next_profile(viewer_id: int, gender_filter: str | None = None):
    """
    Следующая анкета, которую зритель ещё не смотрел в текущем круге.
    Порядок случайный (ORDER BY RANDOM).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT u.* FROM users u
            WHERE u.user_id != ?
              AND u.user_id NOT IN (
                  SELECT viewed_id FROM views
                  WHERE viewer_id = ?
              )
        """
        params: list = [viewer_id, viewer_id]

        if gender_filter:
            query += " AND u.gender = ?"
            params.append(gender_filter)

        query += " ORDER BY RANDOM() LIMIT 1"

        async with db.execute(query, params) as cursor:
            return await cursor.fetchone()


async def count_profiles(gender_filter: str | None = None, exclude_id: int | None = None) -> int:
    """Сколько анкет есть всего (для различения «никого нет» и «всё просмотрено»)."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT COUNT(*) FROM users WHERE 1=1"
        params: list = []
        if exclude_id is not None:
            query += " AND user_id != ?"
            params.append(exclude_id)
        if gender_filter:
            query += " AND gender = ?"
            params.append(gender_filter)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def add_view(viewer_id: int, viewed_id: int):
    """Зафиксировать просмотр (обновляет время при повторном просмотре)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO views (viewer_id, viewed_id, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(viewer_id, viewed_id) DO UPDATE SET
                created_at = CURRENT_TIMESTAMP
            """,
            (viewer_id, viewed_id),
        )
        await db.commit()


async def add_like(from_id: int, to_id: int) -> tuple[bool, bool]:
    """
    Ставит лайк.
    Возвращает (is_mutual, is_new):
      is_mutual — есть ли встречный лайк
      is_new    — лайк поставлен впервые (а не повторно после сброса просмотров)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO likes (from_id, to_id) VALUES (?, ?)",
            (from_id, to_id)
        )
        is_new = cursor.rowcount > 0
        await db.commit()

        async with db.execute(
            "SELECT 1 FROM likes WHERE from_id = ? AND to_id = ?", (to_id, from_id)
        ) as cur:
            mutual = await cur.fetchone()
        return mutual is not None, is_new


async def is_mutual(a_id: int, b_id: int) -> bool:
    """Есть ли уже взаимная симпатия между двумя пользователями"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM likes WHERE from_id = ? AND to_id = ?", (a_id, b_id)
        ) as cur:
            ab = await cur.fetchone()
        async with db.execute(
            "SELECT 1 FROM likes WHERE from_id = ? AND to_id = ?", (b_id, a_id)
        ) as cur:
            ba = await cur.fetchone()
        return ab is not None and ba is not None


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM likes") as c:
            likes = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM reports") as c:
            reports = (await c.fetchone())[0]
        return {"total": total, "likes": likes, "reports": reports}


async def delete_user(user_id: int):
    """Полностью удаляет пользователя: анкету, лайки, просмотры и жалобы на него"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.execute(
            "DELETE FROM likes WHERE from_id = ? OR to_id = ?", (user_id, user_id)
        )
        await db.execute(
            "DELETE FROM views WHERE viewer_id = ? OR viewed_id = ?", (user_id, user_id)
        )
        await db.execute("DELETE FROM reports WHERE reported_id = ?", (user_id,))
        await db.commit()



def get_photos(profile) -> list[str]:
    """Список file_id фото анкеты (1–3)."""
    import json
    if profile is None:
        return []
    try:
        raw = profile["photos"]
    except Exception:
        raw = None
    photos = []
    if raw:
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
    if not photos:
        try:
            pid = profile["photo_id"]
            if pid:
                photos = [pid]
        except Exception:
            pass
    return [p for p in photos if p][:1]


async def remove_view(viewer_id: int, viewed_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM views WHERE viewer_id = ? AND viewed_id = ?",
            (viewer_id, viewed_id),
        )
        await db.commit()
