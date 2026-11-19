# SQL & Database Analytics Agent

Ask questions in plain English; an LLM (Groq) writes SQL, the app checks it is safe, runs it,
**fixes its own mistakes (up to 3 retries)**, and shows a table + Plotly chart.

- **Repository**: [Insert your GitHub URL]

## Architecture
```
user question ─► NeMo Guardrails + regex input check ─► LangGraph:
  inspect_schema ─► generate_sql ─► execute_query ─┬─ ok ─► results + Plotly chart
                         ▲                         │
                         └──── reflection ◄── DB error (max 3 retries)
```
`execute_query` first runs the SQL through a **sqlglot AST filter** that allows exactly one read-only
`SELECT` (INSERT/UPDATE/DELETE/DROP/ALTER/CREATE and multi-statement queries are rejected).

## Project layout
```
app.py                  Streamlit dashboard (entry point)
app/db.py               SQLAlchemy engine + schema reflection
app/graph.py            LangGraph state machine + reflection loop + Groq LLM
app/safety.py           AST SQL safety filter (sqlglot)
app/guardrails.py       Input guardrails (regex layer + NeMo Guardrails)
guardrails_config/      NeMo Guardrails config (config.yml, rails.co)
tests/                  pytest suite (no API key needed)
seed_db.py              Creates sample.db with the `orders` table
```

## Installation
1. Create and activate a virtual environment (PyCharm does this for you).
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in:
   ```
   GROQ_API_KEY=your_groq_key      # free key from console.groq.com
   DATABASE_URL=sqlite:///sample.db
   ```
   Optional: `GROQ_MODEL=llama-3.3-70b-versatile` (change if Groq retires the model).
4. Seed the database: `python seed_db.py`
5. Run the UI: `streamlit run app.py`
6. Run tests: `pytest`

## Database
SQLite by default (`sample.db`, table `orders(id, order_date, customer, amount)`).
For PostgreSQL set `DATABASE_URL=postgresql+psycopg2://user:pass@host/db` and `pip install psycopg2-binary`.

## Verification test cases
1. **Self-correction**: tick *Demo self-correction* in the sidebar and ask
   `Show orders sorted by date.` The first query uses the wrong column `created_at`, the database
   errors, the reflection node retries, and the corrected query using `order_date` is shown
   in the logs panel.
2. **Injection block**: enter `DROP TABLE orders; --`. A security warning appears and the
   database is never queried; `orders` stays intact.
3. **Tests**: `pytest` (covers AST filter, guardrails, self-correction loop, retry cap).
