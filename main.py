import csv
import io
import os
from datetime import date as Date

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import calculator
import database
import llm_client

load_dotenv()
database.init_db()

app = FastAPI(title="Fat Loss Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def ok(data):
    return {"success": True, "data": data, "error": None}


def err(msg: str, status: int = 400):
    raise HTTPException(status_code=status, detail={"success": False, "data": None, "error": msg})


# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileIn(BaseModel):
    height_cm: float
    weight_kg: float
    age: int
    sex: str
    protein_goal_g: float | None = None
    carbs_goal_g: float | None = None
    fat_goal_g: float | None = None


@app.post("/api/profile")
def create_profile(body: ProfileIn):
    if body.sex not in ("male", "female"):
        err("sex must be 'male' or 'female'")
    profile = database.upsert_profile(body.model_dump())
    return ok(profile)


@app.get("/api/profile")
def read_profile():
    profile = database.get_profile()
    if not profile:
        return ok(None)
    return ok(profile)


# ── Log ───────────────────────────────────────────────────────────────────────

class LogIn(BaseModel):
    date: str
    weight_kg: float
    food_description: str
    activity_description: str = ""
    exercise_description: str
    activity_multiplier: float = 1.2


@app.post("/api/log")
def log_day(body: LogIn):
    profile = database.get_profile()
    if not profile:
        err("Profile not set up. Please create a profile first.", 422)

    try:
        llm_data = llm_client.analyze(
            body.food_description,
            body.activity_description,
            body.exercise_description,
            body.weight_kg,
            profile["age"],
            profile["sex"],
        )
    except TimeoutError:
        err("AI analysis timed out. Try again.", 503)
    except RuntimeError as e:
        err(str(e), 503)

    protein_g = llm_data["protein_g"]
    carbs_g = llm_data["carbs_g"]
    fat_g = llm_data["fat_g"]
    calories_burned_exercise = llm_data["calories_burned_exercise"]
    llm_notes = llm_data.get("notes", "")

    tef = calculator.calculate_tef(protein_g, carbs_g, fat_g)
    calories_food = calculator.calculate_calories_food(protein_g, carbs_g, fat_g)
    bmr = calculator.calculate_bmr(
        body.weight_kg, profile["height_cm"], profile["age"], profile["sex"]
    )
    tdee = calculator.calculate_tdee(bmr, body.activity_multiplier, calories_burned_exercise)
    deficit = calculator.calculate_deficit(tdee, calories_food, tef["tef_total"])

    record = database.upsert_record({
        "date": body.date,
        "weight_kg": body.weight_kg,
        "food_description": body.food_description,
        "activity_description": body.activity_description,
        "exercise_description": body.exercise_description,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "calories_food": calories_food,
        **tef,
        "calories_burned_exercise": calories_burned_exercise,
        "activity_multiplier": body.activity_multiplier,
        "tdee": tdee,
        "deficit": deficit,
        "llm_notes": llm_notes,
    })
    return ok(record)


# ── Records ───────────────────────────────────────────────────────────────────

@app.get("/api/records")
def list_records(days: int = 30):
    records = database.get_records(days)
    return ok(records)


@app.get("/api/records/{date}")
def get_record(date: str):
    record = database.get_record_by_date(date)
    if not record:
        err(f"No record found for {date}", 404)
    return ok(record)


@app.delete("/api/records/{date}")
def delete_record(date: str):
    deleted = database.delete_record(date)
    if not deleted:
        err(f"No record found for {date}", 404)
    return ok({"deleted": date})


# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/api/summary")
def summary():
    data = database.get_summary()
    return ok(data)


# ── CSV Export ────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "date", "weight_kg", "calories_food", "tef_total", "net_intake", "tdee", "deficit",
    "protein_g", "carbs_g", "fat_g", "calories_burned_exercise",
    "food_description", "activity_description", "exercise_description", "llm_notes",
]


@app.get("/api/export/csv")
def export_csv(days: int = 0):
    records = database.get_records(days if days > 0 else None)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(CSV_COLUMNS)

    for r in records:
        net_intake = round((r.get("calories_food") or 0) - (r.get("tef_total") or 0), 1)
        row = []
        for col in CSV_COLUMNS:
            if col == "net_intake":
                row.append(net_intake)
            else:
                val = r.get(col)
                if isinstance(val, float):
                    row.append(round(val, 1))
                else:
                    row.append(val if val is not None else "")
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fat_loss_{Date.today()}.csv"},
    )


# ── Static frontend ───────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
