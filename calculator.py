def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161



def calculate_tdee(bmr: float, activity_multiplier: float, calories_burned_exercise: float) -> float:
    return bmr * activity_multiplier + calories_burned_exercise


def calculate_tef(protein_g: float, carbs_g: float, fat_g: float) -> dict:
    tef_protein = protein_g * 4 * 0.25
    tef_carbs = carbs_g * 4 * 0.08
    tef_fat = fat_g * 9 * 0.03
    tef_total = tef_protein + tef_carbs + tef_fat
    return {
        "tef_protein": tef_protein,
        "tef_carbs": tef_carbs,
        "tef_fat": tef_fat,
        "tef_total": tef_total,
    }


def calculate_calories_food(protein_g: float, carbs_g: float, fat_g: float) -> float:
    return protein_g * 4 + carbs_g * 4 + fat_g * 9


def calculate_deficit(tdee: float, calories_food: float, tef_total: float) -> float:
    net_intake = calories_food - tef_total
    return tdee - net_intake


def protein_target(weight_kg: float) -> float:
    return weight_kg * 2.0
