"""
main.py
=======
FastAPI backend for the AI-powered NL2SQL chatbot.

Key facts about Vanna 2.0's send_message():
  - It is ASYNC and returns AsyncGenerator[UiComponent, None]
  - Each yielded item is a UI component (text, dataframe, chart, …)
  - We collect all components then extract SQL + data from them

Endpoints:
  POST /chat    — NL question → SQL + results + chart (JSON)
  GET  /health  — system health check
  GET  /        — serves the frontend chat UI
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env")

from sql_validator import validate_sql
from chart_generator import generate_chart
from seed_memory import seed_sync, QA_PAIRS

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nl2sql")

# ── Constants ──────────────────────────────────────────────────────────────────
DB_PATH    = Path(__file__).parent / os.getenv("DB_PATH", "clinic.db")
STATIC_DIR = Path(__file__).parent / "static"

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI-Powered NL2SQL Chatbot",
    description="Natural Language to SQL — Vanna 2.0 + Groq + FastAPI",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Lazy singletons ────────────────────────────────────────────────────────────
_agent = None
_seeded = False


def _get_agent():
    """Lazy-load Vanna agent and seed memory on first call."""
    global _agent, _seeded
    if _agent is None:
        log.info("Initialising Vanna 2.0 Agent ...")
        from vanna_setup import get_agent
        _agent = get_agent()
        log.info("Agent ready.")
    if not _seeded:
        log.info("Seeding agent memory ...")
        seed_sync(verbose=False)
        _seeded = True
        log.info("Memory seeded (15 Q&A pairs).")
    return _agent


# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about the clinic database",
        examples=["How many patients do we have?"],
    )


class ChatResponse(BaseModel):
    message:          str
    sql_query:        str | None = None
    columns:          list[str]  = []
    rows:             list[list] = []
    row_count:        int        = 0
    chart:            dict | None = None
    chart_type:       str | None = None
    execution_time_ms: int       = 0
    error:            str | None = None


# ── Direct SQL path (bypasses agent for speed + reliability) ───────────────────

def _execute_sql(sql: str) -> tuple[list[str], list[list]]:
    """Execute a validated SQL SELECT on clinic.db and return (columns, rows) as pure Python."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"clinic.db not found at {DB_PATH}. Run 'python setup_database.py' first."
        )
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur  = conn.execute(sql)
        data = cur.fetchall()
        if not data:
            return [], []
        columns = list(data[0].keys())
        rows    = [_to_python(list(r)) for r in data]
        return columns, rows
    finally:
        conn.close()


def _to_python(obj):
    """
    Recursively convert numpy / pandas scalars to native Python types
    so Pydantic can serialize them without errors.
    """
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_python(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj



# ── LLM-based SQL generation ───────────────────────────────────────────────────

async def _generate_sql_via_agent(question: str) -> str:
    """
    Call the Vanna Agent to generate SQL from a natural-language question.

    send_message() is an async generator that yields UiComponent objects.
    We collect all text components and extract the SQL from them.
    If the Groq LLM returns 429, we re-raise so the chat() handler
    can trigger the Gemini fallback.
    """
    from vanna_setup import make_request_context

    agent   = _get_agent()
    ctx     = make_request_context()
    text_parts: list[str] = []
    rate_limit_error = None

    try:
        async for component in agent.send_message(request_context=ctx, message=question):
            # SimpleTextComponent / RichTextComponent — may contain SQL
            if hasattr(component, "text") and component.text:
                text_parts.append(str(component.text))
            # ArtifactComponent — often contains raw SQL
            if hasattr(component, "content") and component.content:
                text_parts.append(str(component.content))
    except Exception as agent_exc:
        err = str(agent_exc)
        if "429" in err or "rate_limit" in err.lower() or "Rate limit" in err:
            log.warning("[AGENT] Groq 429 inside Vanna agent — re-raising for fallback")
            raise  # let chat() catch it and trigger Gemini fallback
        log.warning(f"[AGENT] Non-fatal error: {agent_exc}")

    full_text = "\n".join(text_parts)
    sql_out   = _extract_sql(full_text)

    if not sql_out:
        # Agent gave no SQL — try a direct Groq call (may also raise 429)
        sql_out = await _ask_llm_direct(question, provider="groq")

    return sql_out.strip()


async def _ask_llm_direct(question: str, provider: str = "groq") -> str:
    """
    Direct chat completion call to the specified provider.

    provider: "groq"   -> Groq API (primary)
              "gemini" -> Google Gemini via native SDK (fallback)
    """
    schema = (
        "Tables: patients(id, first_name, last_name, gender, date_of_birth, city, email, phone, created_at), "
        "doctors(id, name, specialization, email, phone, years_experience), "
        "appointments(id, patient_id, doctor_id, appointment_date, status, notes), "
        "treatments(id, appointment_id, treatment_name, cost, description), "
        "invoices(id, patient_id, appointment_id, total_amount, status, invoice_date, due_date, paid_date)"
    )
    system_prompt = (
        f"You are a SQLite expert. Database schema: {schema}. "
        "Return ONLY the SQL SELECT query - no explanation, no markdown fences, no backticks."
    )

    if provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY", "")
        model   = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        if not api_key or api_key == "your-google-api-key-here":
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set in .env. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        import google.genai as genai
        genai_client = genai.Client(api_key=api_key)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: genai_client.models.generate_content(
                model=model,
                contents=system_prompt + "\n\nQuestion: " + question
            )
        )
        return response.text.strip()

    else:  # groq (default)
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1",
        )
        resp = await client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": question},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()



def _extract_sql(text: str) -> str:
    """Pull the first SELECT statement from an LLM response."""
    # Strip ```sql ... ``` fences
    fenced = re.search(r"```(?:sql)?\s*((?:SELECT|WITH)[\s\S]+?)```", text, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    # First bare SELECT / WITH
    bare = re.search(r"((?:SELECT|WITH)\b[\s\S]+?)(?:;|$)", text, re.IGNORECASE)
    if bare:
        return bare.group(1).strip()
    return ""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    html = STATIC_DIR / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return {"message": "NL2SQL API running. Visit /api/docs"}


@app.get("/health", tags=["System"])
async def health():
    """Health check — DB connectivity + agent memory status."""
    db_ok = False
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("SELECT 1")
            conn.close()
            db_ok = True
        except Exception:
            pass

    return {
        "status": "ok",
        "database": "connected" if db_ok else "disconnected",
        "database_path": str(DB_PATH),
        "agent_memory_items": len(QA_PAIRS),
        "llm_provider": f"Groq ({os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')})",
        "version": "1.0.0",
    }


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Convert a natural language question → SQL → execute → return results + chart.

    Steps:
      1. Call Vanna Agent to generate SQL (async streaming)
      2. Validate SQL (SELECT-only, no dangerous keywords)
      3. Execute on clinic.db
      4. Auto-generate Plotly chart if results are numeric
      5. Return structured JSON
    """
    t0       = int(time.time() * 1000)
    question = request.question.strip()
    log.info(f"[CHAT] {question!r}")

    try:
        # ── 1. Generate SQL ────────────────────────────────────────────────
        sql = await _generate_sql_via_agent(question)
        log.info(f"[SQL] {sql[:120]}")

        if not sql:
            return ChatResponse(
                message="I could not generate a SQL query for that question. Please rephrase.",
                error="No SQL generated",
                execution_time_ms=int(time.time() * 1000) - t0,
            )

        # ── 2. Validate ───────────────────────────────────────────────────
        v = validate_sql(sql)
        if not v.is_valid:
            log.warning(f"[SQL BLOCKED] {v.error}")
            return ChatResponse(
                message=f"The generated query was rejected for safety reasons: {v.error}",
                sql_query=sql,
                error=v.error,
                execution_time_ms=int(time.time() * 1000) - t0,
            )

        # ── 3. Execute ────────────────────────────────────────────────────
        columns, rows = _execute_sql(sql)
        row_count     = len(rows)
        log.info(f"[DB] {row_count} rows × {len(columns)} cols")

        if row_count == 0:
            return ChatResponse(
                message="No data found for that query. Try adjusting your filters.",
                sql_query=sql,
                columns=columns,
                rows=[],
                row_count=0,
                execution_time_ms=int(time.time() * 1000) - t0,
            )

        # ── 4. Chart ──────────────────────────────────────────────────────
        chart_dict = generate_chart(columns, rows, question)
        chart_type = _detect_chart_type(chart_dict)

        # ── 5. Summary ────────────────────────────────────────────────────
        msg     = _build_message(question, row_count, columns, rows)
        elapsed = int(time.time() * 1000) - t0
        log.info(f"[DONE] {elapsed}ms | chart={chart_type}")

        return ChatResponse(
            message=msg,
            sql_query=sql,
            columns=columns,
            rows=_to_python(rows),
            row_count=row_count,
            chart=_to_python(chart_dict),
            chart_type=chart_type,
            execution_time_ms=elapsed,
        )

    except FileNotFoundError as exc:
        log.error(f"[DB] {exc}")
        return ChatResponse(
            message=str(exc),
            error=str(exc),
            execution_time_ms=int(time.time() * 1000) - t0,
        )
    except Exception as exc:
        err_str = str(exc)
        # Groq / OpenAI rate limit (429) — try Gemini fallback
        if "429" in err_str or "rate_limit" in err_str.lower() or "Rate limit" in err_str:
            log.warning("[RATE LIMIT] Groq limit hit — switching to Gemini fallback ...")
            return await _handle_with_gemini_fallback(question, t0)
        log.error(f"[ERROR] {exc}\n{traceback.format_exc()}")
        return ChatResponse(
            message="An unexpected error occurred. Please try again.",
            error=str(exc),
            execution_time_ms=int(time.time() * 1000) - t0,
        )


async def _handle_with_gemini_fallback(question: str, t0: int) -> "ChatResponse":
    """
    Full pipeline using Gemini as the SQL generator.
    Called automatically when Groq returns a 429 rate-limit error.
    """
    log.info("[GEMINI] Generating SQL via Gemini fallback ...")
    try:
        sql = await _ask_llm_direct(question, provider="gemini")
        sql = _extract_sql(sql) or sql.strip()
        log.info(f"[GEMINI SQL] {sql[:120]}")

        if not sql:
            return ChatResponse(
                message="Groq limit reached and Gemini could not generate SQL. Please try again later.",
                error="No SQL from fallback",
                execution_time_ms=int(time.time() * 1000) - t0,
            )

        v = validate_sql(sql)
        if not v.is_valid:
            return ChatResponse(
                message=f"Gemini generated an unsafe query: {v.error}",
                sql_query=sql,
                error=v.error,
                execution_time_ms=int(time.time() * 1000) - t0,
            )

        columns, rows = _execute_sql(sql)
        row_count = len(rows)
        chart_dict = generate_chart(columns, rows, question)
        chart_type = _detect_chart_type(chart_dict)
        msg = _build_message(question, row_count, columns, rows)
        elapsed = int(time.time() * 1000) - t0
        log.info(f"[GEMINI DONE] {elapsed}ms | rows={row_count} | chart={chart_type}")

        return ChatResponse(
            message=msg + "  *(answered via Gemini fallback — Groq limit reached)*",
            sql_query=sql,
            columns=columns,
            rows=_to_python(rows),
            row_count=row_count,
            chart=_to_python(chart_dict),
            chart_type=chart_type,
            execution_time_ms=elapsed,
        )

    except EnvironmentError as env_err:
        # GOOGLE_API_KEY not configured
        log.error(f"[GEMINI] Not configured: {env_err}")
        return ChatResponse(
            message=(
                "Groq API daily limit reached and no Gemini fallback is configured. "
                "Add GOOGLE_API_KEY to .env (free at aistudio.google.com/apikey)."
            ),
            error="rate_limit_exceeded; gemini_not_configured",
            execution_time_ms=int(time.time() * 1000) - t0,
        )
    except Exception as exc:
        err_str = str(exc)
        # Gemini also rate-limited?
        if "429" in err_str or "quota" in err_str.lower():
            return ChatResponse(
                message="Both Groq and Gemini have reached their limits. Please try again later.",
                error="all_providers_rate_limited",
                execution_time_ms=int(time.time() * 1000) - t0,
            )
        log.error(f"[GEMINI ERROR] {exc}\n{traceback.format_exc()}")
        return ChatResponse(
            message="Groq limit reached and Gemini fallback also failed. Please try again later.",
            error=str(exc),
            execution_time_ms=int(time.time() * 1000) - t0,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_message(question: str, row_count: int, columns: list, rows: list) -> str:
    if row_count == 1 and len(columns) == 1:
        value = rows[0][0]
        col   = columns[0].replace("_", " ")
        return f"The {col} is **{value}**."
    if row_count == 1:
        parts = [f"{c}: {v}" for c, v in zip(columns, rows[0])]
        return "Result — " + " | ".join(parts)
    return f"Found **{row_count}** result{'s' if row_count != 1 else ''}."


def _detect_chart_type(chart_dict: dict | None) -> str | None:
    if not chart_dict:
        return None
    data = chart_dict.get("data", [])
    return data[0].get("type") if data else None


# ── Dev entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
