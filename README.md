# Cut Tracker

A local-first fat-loss tracking app. Log your food, activity, and weight daily. DeepSeek AI parses your natural language inputs into macros and calculates your calorie deficit with precise TEF accounting.

## Quick Start

**1. Install dependencies with uv**

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

**2. Set up environment**

```bash
cp .env.example .env
# Edit .env and add your DEEPSEEK_API_KEY
```

Get a DeepSeek API key at https://platform.deepseek.com

**3. Run**

```bash
python main.py
```

Open http://localhost:8000 in your browser.

---

## Deploy on Railway

1. Push this repo to GitHub.
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Select your repository.
4. In the Railway project settings, add an environment variable:
   - `DEEPSEEK_API_KEY` = your key
5. Railway auto-detects the Python app. Set the start command to:
   ```
   python main.py
   ```
6. (Optional) Add a custom domain under Settings → Networking.

**Data persistence on Railway:**
- By default SQLite writes to `records.db` in the project directory, which resets on redeploy.
- For persistence, add a Railway Volume and set the DB path via an env var, or switch to Railway's PostgreSQL add-on and update `database.py` to use `psycopg2`.

---

## Data

- Local: all data lives in `records.db` (SQLite) in the project root.
- Export any time via the History tab → **Export CSV**.
- The DB layer (`database.py`) is intentionally separated so you can swap the SQLite calls for PostgreSQL (`psycopg2`) with minimal changes.

---

## Cost Estimate

Each "Analyze & Save" call makes one DeepSeek V3 API request (~400 input tokens, ~100 output tokens).

**~$0.0001 per log entry** at current DeepSeek pricing.

Logging every day for a year costs roughly **$0.04**.
