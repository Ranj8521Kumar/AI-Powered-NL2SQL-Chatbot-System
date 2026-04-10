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
    """Execute a validated SQL SELECT on clinic.db and return (columns, rows)."""
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
        return list(data[0].keys()), [list(r) for r in data]
    finally:
        conn.close()


# ── LLM-based SQL generation ───────────────────────────────────────────────────

async def _generate_sql_via_agent(question: str) -> str:
    """
    Call the Vanna Agent to generate SQL from a natural-language question.

    send_message() is an async generator that yields UiComponent objects.
    We collect all text components and extract the SQL from them.
    """
    from vanna_setup import make_request_context

    agent   = _get_agent()
    ctx     = make_request_context()
    sql_out = ""
    text_parts: list[str] = []

    async for component in agent.send_message(request_context=ctx, message=question):
        ctype = type(component).__name__

        # DataFrameComponent: agent ran the SQL and got results
        if hasattr(component, "data") and component.data is not None:
            continue  # We'll run SQL ourselves after validation

        # SimpleTextComponent / RichTextComponent — may contain SQL
        if hasattr(component, "text") and component.text:
            text_parts.append(str(component.text))

        # ArtifactComponent — often contains raw SQL
        if hasattr(component, "content") and component.content:
            text_parts.append(str(component.content))

    full_text = "\n".join(text_parts)
    sql_out = _extract_sql(full_text)

    if not sql_out:
        # Fallback: ask via plain LLM call with explicit prompt
        sql_out = await _ask_llm_direct(question)

    return sql_out.strip()


async def _ask_llm_direct(question: str) -> str:
    """
    Direct Groq chat completion call — used as fallback when the agent
    response contains no parseable SQL.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )

    schema = (
        "Tables: patients(id, first_name, last_name, gender, date_of_birth, city, email, phone, created_at), "
        "doctors(id, name, specialization, email, phone, years_experience), "
        "appointments(id, patient_id, doctor_id, appointment_date, status, notes), "
        "treatments(id, appointment_id, treatment_name, cost, description), "
        "invoices(id, patient_id, appointment_id, total_amount, status, invoice_date, due_date, paid_date)"
    )

    resp = await client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a SQLite expert. Database schema: {schema}. "
                    "Return ONLY the SQL SELECT query, no explanation, no markdown fences."
                ),
            },
            {"role": "user", "content": question},
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
            rows=rows,
            row_count=row_count,
            chart=chart_dict,
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
        log.error(f"[ERROR] {exc}\n{traceback.format_exc()}")
        return ChatResponse(
            message="An unexpected error occurred. Please try again.",
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
