import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "records.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY,
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
        # migrate existing DBs that predate macro goal columns
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_profile)")}
        for col in ("protein_goal_g", "carbs_goal_g", "fat_goal_g"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE user_profile ADD COLUMN {col} REAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_records (
                id INTEGER PRIMARY KEY,
                date TEXT UNIQUE,
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
                created_at TEXT
            )
        """)
        # migrate existing DBs
        dr_cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_records)")}
        if "activity_multiplier" not in dr_cols:
            conn.execute("ALTER TABLE daily_records ADD COLUMN activity_multiplier REAL")


# ── Profile ──────────────────────────────────────────────────────────────────

def upsert_profile(data: dict) -> dict:
    with db() as conn:
        existing = conn.execute("SELECT id FROM user_profile WHERE id = 1").fetchone()
        if existing:
            conn.execute("""
                UPDATE user_profile
                SET height_cm=?, weight_kg=?, age=?, sex=?,
                    protein_goal_g=?, carbs_goal_g=?, fat_goal_g=?
                WHERE id=1
            """, (data["height_cm"], data["weight_kg"], data["age"], data["sex"],
                  data.get("protein_goal_g"), data.get("carbs_goal_g"), data.get("fat_goal_g")))
        else:
            conn.execute("""
                INSERT INTO user_profile (id, height_cm, weight_kg, age, sex,
                    protein_goal_g, carbs_goal_g, fat_goal_g, created_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (data["height_cm"], data["weight_kg"], data["age"], data["sex"],
                  data.get("protein_goal_g"), data.get("carbs_goal_g"), data.get("fat_goal_g")))
        row = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
        return dict(row)


def get_profile() -> Optional[dict]:
    with db() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
        return dict(row) if row else None


# ── Daily Records ─────────────────────────────────────────────────────────────

def upsert_record(data: dict) -> dict:
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_records WHERE date=?", (data["date"],)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE daily_records SET
                    weight_kg=?, food_description=?, activity_description=?,
                    exercise_description=?, protein_g=?, carbs_g=?, fat_g=?,
                    calories_food=?, tef_protein=?, tef_carbs=?, tef_fat=?,
                    tef_total=?, calories_burned_exercise=?, activity_multiplier=?,
                    tdee=?, deficit=?, llm_notes=?
                WHERE date=?
            """, (
                data["weight_kg"], data["food_description"], data["activity_description"],
                data["exercise_description"], data["protein_g"], data["carbs_g"], data["fat_g"],
                data["calories_food"], data["tef_protein"], data["tef_carbs"], data["tef_fat"],
                data["tef_total"], data["calories_burned_exercise"], data["activity_multiplier"],
                data["tdee"], data["deficit"], data["llm_notes"], data["date"],
            ))
        else:
            conn.execute("""
                INSERT INTO daily_records (
                    date, weight_kg, food_description, activity_description,
                    exercise_description, protein_g, carbs_g, fat_g,
                    calories_food, tef_protein, tef_carbs, tef_fat,
                    tef_total, calories_burned_exercise, activity_multiplier,
                    tdee, deficit, llm_notes, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """, (
                data["date"], data["weight_kg"], data["food_description"],
                data["activity_description"], data["exercise_description"],
                data["protein_g"], data["carbs_g"], data["fat_g"],
                data["calories_food"], data["tef_protein"], data["tef_carbs"], data["tef_fat"],
                data["tef_total"], data["calories_burned_exercise"], data["activity_multiplier"],
                data["tdee"], data["deficit"], data["llm_notes"],
            ))
        row = conn.execute("SELECT * FROM daily_records WHERE date=?", (data["date"],)).fetchone()
        return dict(row)


def get_records(days: Optional[int] = None) -> list[dict]:
    with db() as conn:
        if days:
            rows = conn.execute("""
                SELECT * FROM daily_records
                WHERE date >= date('now', ?)
                ORDER BY date DESC
            """, (f"-{days} days",)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM daily_records ORDER BY date DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_record_by_date(date: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_records WHERE date=?", (date,)
        ).fetchone()
        return dict(row) if row else None


def delete_record(date: str) -> bool:
    with db() as conn:
        cur = conn.execute("DELETE FROM daily_records WHERE date=?", (date,))
        return cur.rowcount > 0


def get_summary() -> dict:
    with db() as conn:
        def avg_over_days(col, n):
            row = conn.execute(f"""
                SELECT AVG({col}) FROM daily_records
                WHERE date >= date('now', '-{n} days')
            """).fetchone()
            return row[0]

        avg_deficit_7d = avg_over_days("deficit", 7)
        avg_deficit_30d = avg_over_days("deficit", 30)
        avg_protein_7d = avg_over_days("protein_g", 7)
        avg_tef_7d = avg_over_days("tef_total", 7)

        days_logged = conn.execute("SELECT COUNT(*) FROM daily_records").fetchone()[0]

        weights = conn.execute(
            "SELECT weight_kg FROM daily_records WHERE weight_kg IS NOT NULL ORDER BY date DESC LIMIT 1"
        ).fetchone()
        current_weight = weights[0] if weights else None

        first = conn.execute(
            "SELECT weight_kg FROM daily_records WHERE weight_kg IS NOT NULL ORDER BY date ASC LIMIT 1"
        ).fetchone()
        start_weight = first[0] if first else None

        weight_change = None
        if current_weight is not None and start_weight is not None:
            weight_change = current_weight - start_weight

        profile = conn.execute("SELECT weight_kg FROM user_profile WHERE id=1").fetchone()
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
