import json
import os
from openai import OpenAI

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=30.0,
        )
    return _client


SYSTEM_PROMPT = (
    "You are a precise sports nutrition analyst. "
    "Return ONLY a valid JSON object. No markdown, no explanation, no extra text."
)


def _build_user_prompt(
    food_description: str,
    activity_description: str,
    exercise_description: str,
    weight_kg: float,
    age: int,
    sex: str,
) -> str:
    # Pre-compute sanity-check burns at this bodyweight for common activities
    wt = weight_kg
    sanity = {
        "45min weight training": round(4.0 * wt * 0.75),
        "30min run":             round(8.0 * wt * 0.50),
        "60min cycling":         round(6.0 * wt * 1.00),
        "50min fitness class":   round(5.0 * wt * 0.833),
        "60min yoga/stretch":    round(2.5 * wt * 1.00),
    }
    sanity_str = "\n".join(f"  {k}: {v} kcal" for k, v in sanity.items())

    return f"""Analyze these inputs and return a JSON object.

=== FOOD ===
{food_description}

=== EXERCISE SESSION ===
{exercise_description}

=== USER ===
Weight: {weight_kg} kg | Age: {age} | Sex: {sex}

=== INSTRUCTIONS FOR calories_burned_exercise ===
Formula: MET × weight_kg × duration_hours

DEFAULT MET values — always use these unless the user explicitly states intensity:
  Weight training:              4.0
  Running (unspecified pace):   8.0
  Cycling (unspecified):        6.0
  Swimming laps:                6.0
  Fitness class / aerobics:     5.0
  HIIT / circuit training:      7.0
  Team sports:                  7.0
  Yoga / stretching / pilates:  2.5
  Brisk walking:                3.5
  Rest day / no exercise:       0

Intensity adjustment — ONLY apply if the user explicitly uses these words:
  "light" / "easy" / "recovery"  → reduce MET by 1.5
  "hard" / "intense" / "heavy"   → increase MET by 1.5
  "moderate" / "normal"          → keep default MET (no change)

Expected burns for THIS user ({weight_kg} kg) at default intensity:
{sanity_str}

RULES:
- Use the default MET unless intensity is explicitly stated. Do not infer intensity from context.
- Only count the deliberate exercise session. Steps and daily movement are already in the activity multiplier.
- If exercise is "rest day" or blank, return 0.
- If duration is not stated, assume: weights = 45 min, run = 30 min, class = 50 min, cycling = 60 min.
- If age > 40, reduce result by 5% per decade above 40.
- Do not round up. Err on the side of under-counting.

Return this exact JSON with no other text:
{{
  "protein_g": <number>,
  "carbs_g": <number>,
  "fat_g": <number>,
  "calories_burned_exercise": <number>,
  "notes": "<one sentence: MET used, duration assumed, confidence>"
}}"""


def _parse_response(content: str) -> dict:
    content = content.strip()
    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(content)


def analyze(
    food_description: str,
    activity_description: str,
    exercise_description: str,
    weight_kg: float,
    age: int,
    sex: str,
) -> dict:
    client = _get_client()
    user_prompt = _build_user_prompt(
        food_description, activity_description, exercise_description, weight_kg, age, sex
    )

    def attempt() -> dict:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return _parse_response(response.choices[0].message.content)

    try:
        return attempt()
    except (json.JSONDecodeError, ValueError):
        try:
            return attempt()
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(f"LLM returned unparseable JSON after two attempts: {e}")
