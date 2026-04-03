import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "records.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        # ── Auth tables ───────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT
            )
        """)

        # ── user_profile ──────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
                height_cm REAL,
                weight_kg REAL,
                age INTEGER,
                sex TEXT,
                activity_level TEXT,
                protein_goal_g REAL,
                carbs_goal_g REAL,
                fat_goal_g REAL,
                created_at TEXT
            )
        """)
        up_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_profile)")}
        for col in ("protein_goal_g", "carbs_goal_g", "fat_goal_g"):
            if col not in up_cols:
                conn.execute(f"ALTER TABLE user_profile ADD COLUMN {col} REAL")
        if "user_id" not in up_cols:
            conn.execute("ALTER TABLE user_profile ADD COLUMN user_id INTEGER")

        # ── daily_records ─────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_records (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                date TEXT NOT NULL,
                weight_kg REAL,
                food_description TEXT,
                activity_description TEXT,
                exercise_description TEXT,
                protein_g REAL,
                carbs_g REAL,
                fat_g REAL,
                calories_food REAL,
                tef_protein REAL,
                tef_carbs REAL,
                tef_fat REAL,
                tef_total REAL,
                calories_burned_exercise REAL,
                activity_multiplier REAL,
                tdee REAL,
                deficit REAL,
                llm_notes TEXT,
                food_items_json TEXT,
                created_at TEXT,
                UNIQUE(user_id, date)
            )
        """)
        dr_cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_records)")}
        for col, typ in [("activity_multiplier", "REAL"), ("user_id", "INTEGER"),
                         ("food_items_json", "TEXT")]:
            if col not in dr_cols:
                conn.execute(f"ALTER TABLE daily_records ADD COLUMN {col} {typ}")


# ── Auth ──────────────────────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> dict:
    with db() as conn:
        try:
            conn.execute("""
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, datetime('now'))
            """, (username, password_hash))
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            return dict(row)
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' already taken")


def get_user_by_username(username: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        return dict(row) if row else None


def create_session(token: str, user_id: int) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO sessions (token, user_id, created_at)
            VALUES (?, ?, datetime('now'))
        """, (token, user_id))


def get_user_from_token(token: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute("""
            SELECT u.* FROM users u
            JOIN sessions s ON s.user_id = u.id
            WHERE s.token = ?
        """, (token,)).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def get_all_users() -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT u.username, u.created_at,
                   COUNT(d.id) AS record_count
            FROM users u
            LEFT JOIN daily_records d ON d.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def delete_user_by_username(username: str) -> bool:
    with db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if not user:
            return False
        uid = user["id"]
        conn.execute("DELETE FROM sessions     WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM daily_records WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM user_profile  WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM users         WHERE id=?",      (uid,))
        return True


# ── Profile ───────────────────────────────────────────────────────────────────

def upsert_profile(data: dict, user_id: int) -> dict:
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM user_profile WHERE user_id=?", (user_id,)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE user_profile
                SET height_cm=?, weight_kg=?, age=?, sex=?,
                    protein_goal_g=?, carbs_goal_g=?, fat_goal_g=?
                WHERE user_id=?
            """, (data["height_cm"], data["weight_kg"], data["age"], data["sex"],
                  data.get("protein_goal_g"), data.get("carbs_goal_g"), data.get("fat_goal_g"),
                  user_id))
        else:
            conn.execute("""
                INSERT INTO user_profile
                    (user_id, height_cm, weight_kg, age, sex,
                     protein_goal_g, carbs_goal_g, fat_goal_g, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (user_id, data["height_cm"], data["weight_kg"], data["age"], data["sex"],
                  data.get("protein_goal_g"), data.get("carbs_goal_g"), data.get("fat_goal_g")))
        row = conn.execute(
            "SELECT * FROM user_profile WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(row)


def get_profile(user_id: int) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM user_profile WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


# ── Daily Records ─────────────────────────────────────────────────────────────

def upsert_record(data: dict, user_id: int) -> dict:
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_records WHERE user_id=? AND date=?",
            (user_id, data["date"])
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE daily_records SET
                    weight_kg=?, food_description=?, activity_description=?,
                    exercise_description=?, protein_g=?, carbs_g=?, fat_g=?,
                    calories_food=?, tef_protein=?, tef_carbs=?, tef_fat=?,
                    tef_total=?, calories_burned_exercise=?, activity_multiplier=?,
                    tdee=?, deficit=?, llm_notes=?, food_items_json=?
                WHERE user_id=? AND date=?
            """, (
                data["weight_kg"], data["food_description"], data["activity_description"],
                data["exercise_description"], data["protein_g"], data["carbs_g"], data["fat_g"],
                data["calories_food"], data["tef_protein"], data["tef_carbs"], data["tef_fat"],
                data["tef_total"], data["calories_burned_exercise"], data["activity_multiplier"],
                data["tdee"], data["deficit"], data["llm_notes"], data.get("food_items_json"),
                user_id, data["date"],
            ))
        else:
            conn.execute("""
                INSERT INTO daily_records (
                    user_id, date, weight_kg, food_description, activity_description,
                    exercise_description, protein_g, carbs_g, fat_g,
                    calories_food, tef_protein, tef_carbs, tef_fat,
                    tef_total, calories_burned_exercise, activity_multiplier,
                    tdee, deficit, llm_notes, food_items_json, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """, (
                user_id, data["date"], data["weight_kg"], data["food_description"],
                data["activity_description"], data["exercise_description"],
                data["protein_g"], data["carbs_g"], data["fat_g"],
                data["calories_food"], data["tef_protein"], data["tef_carbs"], data["tef_fat"],
                data["tef_total"], data["calories_burned_exercise"], data["activity_multiplier"],
                data["tdee"], data["deficit"], data["llm_notes"], data.get("food_items_json"),
            ))
        row = conn.execute(
            "SELECT * FROM daily_records WHERE user_id=? AND date=?",
            (user_id, data["date"])
        ).fetchone()
        return dict(row)


def get_records(user_id: int, days: Optional[int] = None) -> list[dict]:
    with db() as conn:
        if days:
            rows = conn.execute("""
                SELECT * FROM daily_records
                WHERE user_id=? AND date >= date('now', ?)
                ORDER BY date DESC
            """, (user_id, f"-{days} days")).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM daily_records WHERE user_id=? ORDER BY date DESC",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_record_by_date(date: str, user_id: int) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_records WHERE user_id=? AND date=?",
            (user_id, date)
        ).fetchone()
        return dict(row) if row else None


def delete_record(date: str, user_id: int) -> bool:
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM daily_records WHERE user_id=? AND date=?",
            (user_id, date)
        )
        return cur.rowcount > 0


def get_summary(user_id: int) -> dict:
    with db() as conn:
        def avg_over_days(col, n):
            row = conn.execute(f"""
                SELECT AVG({col}) FROM daily_records
                WHERE user_id=? AND date >= date('now', '-{n} days')
            """, (user_id,)).fetchone()
            return row[0]

        avg_deficit_7d  = avg_over_days("deficit", 7)
        avg_deficit_30d = avg_over_days("deficit", 30)
        avg_protein_7d  = avg_over_days("protein_g", 7)
        avg_tef_7d      = avg_over_days("tef_total", 7)

        days_logged = conn.execute(
            "SELECT COUNT(*) FROM daily_records WHERE user_id=?", (user_id,)
        ).fetchone()[0]

        weights = conn.execute("""
            SELECT weight_kg FROM daily_records
            WHERE user_id=? AND weight_kg IS NOT NULL
            ORDER BY date DESC LIMIT 1
        """, (user_id,)).fetchone()
        current_weight = weights[0] if weights else None

        first = conn.execute("""
            SELECT weight_kg FROM daily_records
            WHERE user_id=? AND weight_kg IS NOT NULL
            ORDER BY date ASC LIMIT 1
        """, (user_id,)).fetchone()
        start_weight = first[0] if first else None

        weight_change = (
            current_weight - start_weight
            if current_weight is not None and start_weight is not None
            else None
        )

        profile = conn.execute(
            "SELECT weight_kg FROM user_profile WHERE user_id=?", (user_id,)
        ).fetchone()
        profile_weight = profile[0] if profile else None

        from calculator import protein_target
        pt = protein_target(current_weight or profile_weight or 70)

        return {
            "avg_deficit_7d": avg_deficit_7d,
            "avg_deficit_30d": avg_deficit_30d,
            "avg_protein_7d": avg_protein_7d,
            "protein_target_g": pt,
            "days_logged": days_logged,
            "current_weight": current_weight,
            "start_weight": start_weight,
            "weight_change": weight_change,
            "avg_tef_7d": avg_tef_7d,
        }
