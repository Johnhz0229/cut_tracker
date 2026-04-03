# Cut Tracker

A multi-user fat-loss tracking web app. Log your food, activity, and weight daily. DeepSeek AI parses natural language inputs into per-item macros and calculates your calorie deficit with full P&L-style breakdown — food intake → TEF → BMR → exercise → net energy.

## Features

- **AI food parsing** — describe what you ate in plain English; DeepSeek V3 extracts per-item macros (protein, carbs, fat, calories) including per-100g nutritional basis
- **P&L energy breakdown** — Gross intake → TEF deduction → Net intake → TDEE burn → Net energy, color-coded green (deficit) / red (surplus)
- **Accurate calorie burn** — NEAT activity multiplier (1.1–1.5) selected daily + separate exercise EAT via conservative MET defaults
- **TEF accounting** — protein 25%, carbs 8%, fat 3% thermic effect deducted from intake
- **Macro goals** — set protein/carbs/fat targets in Setup; goal badges shown on every log and history entry
- **History** — full P&L breakdown for every past day, same layout as the Log tab
- **Trends** — weight and deficit charts, 7-day/30-day averages, weight change since start
- **CSV export** — one-click download of all records
- **Multi-user** — bcrypt-hashed passwords, session tokens, user-scoped data isolation
- **Admin panel** — hidden at `/admin`, create/delete users via `ADMIN_SECRET`

---

## Quick Start

**1. Install dependencies**

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Or with pip:

```bash
pip install -r requirements.txt
```

**2. Set up environment**

```bash
cp .env.example .env
# Edit .env — add DEEPSEEK_API_KEY and ADMIN_SECRET at minimum
```

Get a DeepSeek API key at https://platform.deepseek.com

**3. Run**

```bash
python main.py
```

Open http://localhost:8000 in your browser.

**4. Create your account**

Go to `/admin`, enter your `ADMIN_SECRET`, and create a user. Then log in at the main page.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `ADMIN_SECRET` | Yes | Secret key for the `/admin` panel |
| `PORT` | No | Server port (default: `8000`) |
| `DB_PATH` | No | SQLite file path (default: `records.db`) |

---

## How the Calculation Works

```
Gross intake (food kcal)
  − TEF (protein 25% / carbs 8% / fat 3%)
= Net intake

  − BMR × activity multiplier  (NEAT)
  − Exercise calories (EAT via MET formula)
= TDEE (total daily energy expenditure)

Net energy = Net intake − TDEE
  Negative → deficit (green) ✓
  Positive → surplus (red)  ✗
```

**BMR**: Mifflin-St Jeor formula  
**Activity multiplier**: 1.1 (rest day) → 1.5 (very active), NEAT only — exercise is tracked separately  
**Exercise**: MET × weight_kg × duration_hours, conservative defaults, intensity-adjusted only if explicitly stated

---

## Deploy on Railway

1. Push this repo to GitHub.
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Add environment variables: `DEEPSEEK_API_KEY`, `ADMIN_SECRET`.
4. Set start command: `python main.py`
5. For persistent data, add a Railway Volume and set `DB_PATH` to a path inside it.

---

## Data

- All data lives in `records.db` (SQLite) — set `DB_PATH` env var to change location.
- Export any time via History tab → **Export CSV**.
- `database.py` is intentionally separated for easy swap to PostgreSQL.

---

## Cost Estimate

Each "Analyze & Save" makes one DeepSeek V3 API call (~500 input tokens, ~150 output tokens).

**~$0.0001 per log entry** at current DeepSeek pricing.  
Logging every day for a year ≈ **$0.04**.
