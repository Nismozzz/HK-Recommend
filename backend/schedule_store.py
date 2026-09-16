import csv
import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

DB_PATH = Path(__file__).resolve().parent / "schedule.db"
VALID_DAYS = set(range(7))


class Course(TypedDict):
    name: str
    start: str
    end: str


def connection() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        weekday INTEGER NOT NULL,
        course_code TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL
    )""")
    # Migrate databases created before course locations were removed.
    columns = {row["name"] for row in db.execute("PRAGMA table_info(courses)").fetchall()}
    if "location" in columns:
        db.execute("ALTER TABLE courses RENAME TO courses_legacy")
        db.execute("""CREATE TABLE courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL,
            course_code TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        )""")
        db.execute("""INSERT INTO courses (id, weekday, course_code, start_time, end_time)
            SELECT id, weekday, course_code, start_time, end_time FROM courses_legacy""")
        db.execute("DROP TABLE courses_legacy")
    db.execute("CREATE TABLE IF NOT EXISTS user_profile (id INTEGER PRIMARY KEY CHECK (id = 1), school TEXT NOT NULL)")
    db.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        value TEXT NOT NULL,
        preference TEXT NOT NULL CHECK (preference IN ('like', 'dislike')),
        source TEXT NOT NULL DEFAULT 'explicit',
        updated_at TEXT NOT NULL,
        UNIQUE(category, value)
    )""")
    db.commit()
    return db


def get_school() -> str | None:
    with connection() as db:
        row = db.execute("SELECT school FROM user_profile WHERE id = 1").fetchone()
        value = row["school"].strip() if row else ""
        # Ignore values produced by the old overly-greedy school parser.
        return value if value and value not in {"哪个", "哪個", "未知", "未提供"} else None


def save_school(school: str) -> str:
    value = school.strip()
    if not value:
        raise ValueError("学校名称不能为空")
    with connection() as db:
        db.execute("INSERT INTO user_profile (id, school) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET school = excluded.school", (value,))
    return value


def list_preferences() -> list[dict[str, Any]]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id, category, value, preference, source, updated_at FROM user_preferences ORDER BY category, value").fetchall()]


def get_preferences() -> dict[str, list[str]]:
    preferences: dict[str, list[str]] = {"likes": [], "dislikes": []}
    for item in list_preferences():
        key = "likes" if item["preference"] == "like" else "dislikes"
        preferences[key].append(item["value"])
    return preferences


def save_preference(category: str, value: str, preference: str, source: str = "explicit") -> dict[str, Any]:
    category = category.strip().lower()
    value = value.strip()
    if category not in {"cuisine", "dish", "flavor", "ingredient", "dietary"}:
        raise ValueError("口味类别无效")
    if preference not in {"like", "dislike"}:
        raise ValueError("偏好类型无效")
    if not value or len(value) > 80:
        raise ValueError("偏好内容不能为空或过长")
    timestamp = datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(timespec="seconds")
    with connection() as db:
        db.execute("""INSERT INTO user_preferences (category, value, preference, source, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category, value) DO UPDATE SET preference = excluded.preference, source = excluded.source, updated_at = excluded.updated_at""", (category, value, preference, source, timestamp))
        row = db.execute("SELECT id, category, value, preference, source, updated_at FROM user_preferences WHERE category = ? AND value = ?", (category, value)).fetchone()
    return dict(row)


def delete_preference(preference_id: int) -> bool:
    with connection() as db:
        cursor = db.execute("DELETE FROM user_preferences WHERE id = ?", (preference_id,))
        return cursor.rowcount > 0


def clear_preferences() -> None:
    with connection() as db:
        db.execute("DELETE FROM user_preferences")


def validate_course(weekday: int, course_code: str, start_time: str, end_time: str) -> None:
    if weekday not in VALID_DAYS:
        raise ValueError("weekday 必须是 0-6（星期日到星期六）")
    if not course_code.strip():
        raise ValueError("课程代号不能为空")
    try:
        start = int(start_time[:2]) * 60 + int(start_time[3:5])
        end = int(end_time[:2]) * 60 + int(end_time[3:5])
    except (ValueError, IndexError):
        raise ValueError("时间必须使用 HH:MM 格式") from None
    if len(start_time) != 5 or len(end_time) != 5 or start < 0 or end > 24 * 60 or start >= end:
        raise ValueError("时间必须有效，且开始时间早于结束时间")


def add_course(course: dict[str, Any]) -> dict[str, Any]:
    validate_course(course["weekday"], course["course_code"], course["start_time"], course["end_time"])
    with connection() as db:
        cursor = db.execute("INSERT INTO courses (weekday, course_code, start_time, end_time) VALUES (?, ?, ?, ?)", (course["weekday"], course["course_code"].strip(), course["start_time"], course["end_time"]))
        row = db.execute("SELECT * FROM courses WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def import_csv(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")
    aliases = {"weekday": ["weekday", "星期", "星期几"], "course_code": ["course_code", "课程代号", "课程代码"], "start_time": ["start_time", "开始时间", "开始"], "end_time": ["end_time", "结束时间", "结束"]}
    fields: dict[str, str] = {}
    for field, names in aliases.items():
        found = next((name for name in names if name in reader.fieldnames), None)
        if not found:
            raise ValueError(f"CSV 缺少字段：{names[0]}")
        fields[field] = found
    imported = []
    for index, row in enumerate(reader, start=2):
        raw_day = (row.get(fields["weekday"]) or "").strip()
        day_map = {"日": 0, "天": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
        try:
            weekday = int(raw_day) if raw_day.isdigit() else day_map.get(raw_day.replace("星期", "").replace("周", ""), -1)
            item = {"weekday": weekday, "course_code": (row.get(fields["course_code"]) or "").strip(), "start_time": (row.get(fields["start_time"]) or "").strip(), "end_time": (row.get(fields["end_time"]) or "").strip()}
            validate_course(**item)
            imported.append(add_course(item))
        except (ValueError, TypeError) as error:
            raise ValueError(f"第 {index} 行无效：{error}") from error
    return imported


def list_courses() -> list[dict[str, Any]]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM courses ORDER BY weekday, start_time").fetchall()]


def delete_course(course_id: int) -> bool:
    with connection() as db:
        cursor = db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        return cursor.rowcount > 0


def courses_by_weekday(weekday: int) -> list[Course]:
    rows = list_courses()
    return [{"name": row["course_code"], "start": row["start_time"], "end": row["end_time"]} for row in rows if row["weekday"] == weekday]
