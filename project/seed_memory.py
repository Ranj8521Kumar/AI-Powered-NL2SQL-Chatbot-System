"""
seed_memory.py
==============
Pre-seeds DemoAgentMemory with 15 high-quality Q&A pairs.

Vanna 2.0 stores "tool usage" records — each entry is a question
with the tool name + args that correctly answered it.  We simulate
this by calling save_tool_usage() with the RunSqlTool name and the
known-correct SQL as the argument.

Categories:
  Patient queries    (4) — count, city filter, gender, repeat visitors
  Doctor queries     (3) — appointments/doctor, busiest, by specialization
  Appointment queries(3) — status count, monthly, doctor-wise
  Financial queries  (3) — total revenue, unpaid invoices, avg cost
  Time-based queries (2) — last 3 months, monthly trend

Run:
    python seed_memory.py
Or import:
    from seed_memory import seed_sync
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.core.tool import ToolContext
from vanna.core.user.models import User
from vanna_setup import get_memory


# ── Q&A Pair Definition ────────────────────────────────────────────────────────

class QAPair(NamedTuple):
    question: str
    sql:      str
    category: str


QA_PAIRS: list[QAPair] = [

    # ── Patient Queries ──────────────────────────────────────────────────────
    QAPair(
        "How many patients do we have?",
        "SELECT COUNT(*) AS total_patients FROM patients",
        "patient",
    ),
    QAPair(
        "List all patients from Mumbai",
        "SELECT first_name, last_name, gender, date_of_birth, phone "
        "FROM patients WHERE city = 'Mumbai' ORDER BY last_name",
        "patient",
    ),
    QAPair(
        "Which city has the most patients?",
        "SELECT city, COUNT(*) AS patient_count FROM patients "
        "GROUP BY city ORDER BY patient_count DESC LIMIT 1",
        "patient",
    ),
    QAPair(
        "Show the count of male and female patients",
        "SELECT gender, COUNT(*) AS count FROM patients "
        "GROUP BY gender ORDER BY count DESC",
        "patient",
    ),

    # ── Doctor Queries ────────────────────────────────────────────────────────
    QAPair(
        "How many appointments does each doctor have?",
        "SELECT d.name, COUNT(a.id) AS appointment_count "
        "FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id "
        "GROUP BY d.id, d.name ORDER BY appointment_count DESC",
        "doctor",
    ),
    QAPair(
        "Who is the busiest doctor?",
        "SELECT d.name, d.specialization, COUNT(a.id) AS total_appointments "
        "FROM doctors d JOIN appointments a ON a.doctor_id = d.id "
        "GROUP BY d.id, d.name, d.specialization "
        "ORDER BY total_appointments DESC LIMIT 1",
        "doctor",
    ),
    QAPair(
        "Show all doctors grouped by specialization",
        "SELECT specialization, COUNT(*) AS doctor_count FROM doctors "
        "GROUP BY specialization ORDER BY doctor_count DESC",
        "doctor",
    ),

    # ── Appointment Queries ───────────────────────────────────────────────────
    QAPair(
        "How many appointments are completed, scheduled, and cancelled?",
        "SELECT status, COUNT(*) AS count FROM appointments "
        "GROUP BY status ORDER BY count DESC",
        "appointment",
    ),
    QAPair(
        "Show appointments per month for this year",
        "SELECT strftime('%Y-%m', appointment_date) AS month, "
        "COUNT(*) AS appointment_count FROM appointments "
        "WHERE strftime('%Y', appointment_date) = strftime('%Y', 'now') "
        "GROUP BY month ORDER BY month",
        "appointment",
    ),
    QAPair(
        "Which doctor had the most completed appointments?",
        "SELECT d.name, COUNT(a.id) AS completed_count "
        "FROM doctors d JOIN appointments a ON a.doctor_id = d.id "
        "WHERE a.status = 'Completed' GROUP BY d.id, d.name "
        "ORDER BY completed_count DESC LIMIT 5",
        "appointment",
    ),

    # ── Financial Queries ─────────────────────────────────────────────────────
    QAPair(
        "What is the total revenue from paid invoices?",
        "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'",
        "financial",
    ),
    QAPair(
        "Show all unpaid and overdue invoices with patient names",
        "SELECT p.first_name || ' ' || p.last_name AS patient_name, "
        "i.total_amount, i.status, i.due_date "
        "FROM invoices i JOIN patients p ON p.id = i.patient_id "
        "WHERE i.status IN ('Pending', 'Overdue') ORDER BY i.due_date",
        "financial",
    ),
    QAPair(
        "What is the average invoice amount?",
        "SELECT ROUND(AVG(total_amount), 2) AS avg_invoice_amount FROM invoices",
        "financial",
    ),

    # ── Time-Based Queries ────────────────────────────────────────────────────
    QAPair(
        "How many appointments were there in the last 3 months?",
        "SELECT COUNT(*) AS appointments_last_3_months FROM appointments "
        "WHERE appointment_date >= date('now', '-3 months')",
        "time",
    ),
    QAPair(
        "Show monthly revenue trend for the last 12 months",
        "SELECT strftime('%Y-%m', invoice_date) AS month, "
        "SUM(total_amount) AS revenue FROM invoices "
        "WHERE invoice_date >= date('now', '-12 months') AND status = 'Paid' "
        "GROUP BY month ORDER BY month",
        "time",
    ),
]


# ── Tool context helper ────────────────────────────────────────────────────────

def _make_tool_context(memory: DemoAgentMemory) -> ToolContext:
    """Build a minimal ToolContext for memory seeding."""
    return ToolContext(
        user=User(
            id="seeder",
            username="seeder",
            email="seeder@clinic.local",
            group_memberships=["users"],
        ),
        conversation_id="seed-session",
        request_id="seed",
        agent_memory=memory,
        metadata={},
    )


# ── Seeding logic ──────────────────────────────────────────────────────────────

async def _seed_async(verbose: bool = True) -> int:
    """
    Async inner loop — save_tool_usage is a coroutine in Vanna 2.0.
    Returns number of pairs successfully seeded.
    """
    memory  = get_memory()
    context = _make_tool_context(memory)
    seeded  = 0

    for pair in QA_PAIRS:
        try:
            await memory.save_tool_usage(
                question=pair.question,
                tool_name="RunSqlTool",
                args={"sql": pair.sql},
                context=context,
                success=True,
                metadata={"category": pair.category},
            )
            seeded += 1
            if verbose:
                print(f"  [{pair.category.upper():12s}] {pair.question[:65]}")
        except Exception as exc:
            if verbose:
                print(f"  [WARNING] Failed to seed: {pair.question[:50]} — {exc}")

    # Write JSON snapshot for documentation / debugging
    snapshot_path = Path(__file__).parent / "memory_seed.json"
    snapshot_path.write_text(
        json.dumps(
            [{"question": p.question, "sql": p.sql, "category": p.category} for p in QA_PAIRS],
            indent=2,
        ),
        encoding="utf-8",
    )

    if verbose:
        print(f"\n  {seeded}/{len(QA_PAIRS)} pairs seeded into DemoAgentMemory")
        print(f"  Snapshot written → {snapshot_path}")

    return seeded


def seed_sync(verbose: bool = True) -> int:
    """
    Synchronous wrapper around _seed_async().

    Called from main.py on startup (inside an already-running event loop)
    or from the command line (where no loop exists yet).

    Returns:
        Number of pairs successfully seeded.
    """
    import asyncio

    try:
        # If we are inside a running event loop (e.g. FastAPI startup),
        # schedule the coroutine as a task and return immediately.
        loop = asyncio.get_running_loop()
        loop.create_task(_seed_async(verbose=verbose))
        # Return optimistic count; actual seeding happens as background task
        return len(QA_PAIRS)
    except RuntimeError:
        # No running loop → we are in a standalone script, run normally
        return asyncio.run(_seed_async(verbose=verbose))


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Seeding DemoAgentMemory with Q&A pairs ...\n")
    count = seed_sync(verbose=True)
    if count == 0:
        print("\n[ERROR] No pairs were seeded.")
        sys.exit(1)
    print("\nDone.")
