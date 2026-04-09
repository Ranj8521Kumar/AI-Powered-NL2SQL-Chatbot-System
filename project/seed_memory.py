"""
seed_memory.py
==============
Pre-seeds the Vanna 2.0 DemoAgentMemory with 15 high-quality
question → SQL pairs so the agent has examples to learn from.

Categories covered:
  Patient queries   (4 pairs) — count, list, city filter, gender
  Doctor queries    (3 pairs) — appointments, busiest, specialization
  Appointment queries (3 pairs) — status, monthly, doctor-wise
  Financial queries (3 pairs) — revenue, unpaid, average cost
  Time-based queries (2 pairs) — last 3 months, monthly trend

Usage:
    python seed_memory.py            ← run standalone before starting server
    from seed_memory import seed     ← call seed() from main.py on startup
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from vanna_setup import get_memory


# ── Q&A Pair Definition ────────────────────────────────────────────────────────

class QAPair(NamedTuple):
    question: str
    sql: str
    category: str


QA_PAIRS: list[QAPair] = [

    # ── Patient Queries ──────────────────────────────────────────────────────
    QAPair(
        question="How many patients do we have?",
        sql="SELECT COUNT(*) AS total_patients FROM patients",
        category="patient",
    ),
    QAPair(
        question="List all patients from Mumbai",
        sql=(
            "SELECT first_name, last_name, gender, date_of_birth, phone "
            "FROM patients WHERE city = 'Mumbai' ORDER BY last_name"
        ),
        category="patient",
    ),
    QAPair(
        question="Which city has the most patients?",
        sql=(
            "SELECT city, COUNT(*) AS patient_count "
            "FROM patients "
            "GROUP BY city "
            "ORDER BY patient_count DESC "
            "LIMIT 1"
        ),
        category="patient",
    ),
    QAPair(
        question="Show the count of male and female patients",
        sql=(
            "SELECT gender, COUNT(*) AS count "
            "FROM patients "
            "GROUP BY gender "
            "ORDER BY count DESC"
        ),
        category="patient",
    ),

    # ── Doctor Queries ────────────────────────────────────────────────────────
    QAPair(
        question="How many appointments does each doctor have?",
        sql=(
            "SELECT d.name, COUNT(a.id) AS appointment_count "
            "FROM doctors d "
            "LEFT JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id, d.name "
            "ORDER BY appointment_count DESC"
        ),
        category="doctor",
    ),
    QAPair(
        question="Who is the busiest doctor?",
        sql=(
            "SELECT d.name, d.specialization, COUNT(a.id) AS total_appointments "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id, d.name, d.specialization "
            "ORDER BY total_appointments DESC "
            "LIMIT 1"
        ),
        category="doctor",
    ),
    QAPair(
        question="Show all doctors grouped by specialization",
        sql=(
            "SELECT specialization, COUNT(*) AS doctor_count "
            "FROM doctors "
            "GROUP BY specialization "
            "ORDER BY doctor_count DESC"
        ),
        category="doctor",
    ),

    # ── Appointment Queries ───────────────────────────────────────────────────
    QAPair(
        question="How many appointments are completed, scheduled, and cancelled?",
        sql=(
            "SELECT status, COUNT(*) AS count "
            "FROM appointments "
            "GROUP BY status "
            "ORDER BY count DESC"
        ),
        category="appointment",
    ),
    QAPair(
        question="Show appointments per month for this year",
        sql=(
            "SELECT strftime('%Y-%m', appointment_date) AS month, "
            "COUNT(*) AS appointment_count "
            "FROM appointments "
            "WHERE strftime('%Y', appointment_date) = strftime('%Y', 'now') "
            "GROUP BY month "
            "ORDER BY month"
        ),
        category="appointment",
    ),
    QAPair(
        question="Which doctor had the most completed appointments?",
        sql=(
            "SELECT d.name, COUNT(a.id) AS completed_count "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "WHERE a.status = 'Completed' "
            "GROUP BY d.id, d.name "
            "ORDER BY completed_count DESC "
            "LIMIT 5"
        ),
        category="appointment",
    ),

    # ── Financial Queries ─────────────────────────────────────────────────────
    QAPair(
        question="What is the total revenue from paid invoices?",
        sql=(
            "SELECT SUM(total_amount) AS total_revenue "
            "FROM invoices "
            "WHERE status = 'Paid'"
        ),
        category="financial",
    ),
    QAPair(
        question="Show all unpaid and overdue invoices with patient names",
        sql=(
            "SELECT p.first_name || ' ' || p.last_name AS patient_name, "
            "i.total_amount, i.status, i.due_date "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending', 'Overdue') "
            "ORDER BY i.due_date"
        ),
        category="financial",
    ),
    QAPair(
        question="What is the average invoice amount?",
        sql=(
            "SELECT ROUND(AVG(total_amount), 2) AS avg_invoice_amount "
            "FROM invoices"
        ),
        category="financial",
    ),

    # ── Time-Based Queries ────────────────────────────────────────────────────
    QAPair(
        question="How many appointments were there in the last 3 months?",
        sql=(
            "SELECT COUNT(*) AS appointments_last_3_months "
            "FROM appointments "
            "WHERE appointment_date >= date('now', '-3 months')"
        ),
        category="time",
    ),
    QAPair(
        question="Show monthly revenue trend for the last 12 months",
        sql=(
            "SELECT strftime('%Y-%m', invoice_date) AS month, "
            "SUM(total_amount) AS revenue "
            "FROM invoices "
            "WHERE invoice_date >= date('now', '-12 months') "
            "AND status = 'Paid' "
            "GROUP BY month "
            "ORDER BY month"
        ),
        category="time",
    ),
]


# ── Seeding Logic ──────────────────────────────────────────────────────────────

def seed(verbose: bool = True) -> int:
    """
    Load all QA_PAIRS into DemoAgentMemory.

    Tries the standard Vanna 2.0 memory API.  If the internal API
    differs from expectations, falls back to writing a JSON snapshot
    that can be used for manual verification.

    Returns:
        Number of pairs successfully seeded.
    """
    memory = get_memory()
    seeded = 0

    for pair in QA_PAIRS:
        try:
            # Primary approach: Vanna 2.0 DemoAgentMemory.save()
            # Stores a successful tool-use example (question → SQL)
            memory.save(
                question=pair.question,
                sql=pair.sql,
            )
            seeded += 1
            if verbose:
                print(f"  [{pair.category.upper():12s}] {pair.question[:60]}")
        except AttributeError:
            # Fallback: try alternative method names used in some builds
            for method in ("add", "add_item", "store", "insert"):
                fn = getattr(memory, method, None)
                if fn:
                    try:
                        fn(question=pair.question, sql=pair.sql)
                        seeded += 1
                        if verbose:
                            print(f"  [{pair.category.upper():12s}] {pair.question[:60]}")
                    except Exception:
                        pass
                    break
        except Exception as exc:
            if verbose:
                print(f"  [WARNING] Could not seed: {pair.question[:50]} — {exc}")

    # Always write a JSON snapshot for documentation / debugging
    snapshot_path = Path(__file__).parent / "memory_seed.json"
    snapshot = [
        {"question": p.question, "sql": p.sql, "category": p.category}
        for p in QA_PAIRS
    ]
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    if verbose:
        print(f"\n  {seeded}/{len(QA_PAIRS)} pairs seeded into DemoAgentMemory")
        print(f"  Snapshot written → {snapshot_path}")

    return seeded


# ── Standalone Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Seeding DemoAgentMemory with Q&A pairs ...\n")
    count = seed(verbose=True)
    if count == 0:
        print("\n[WARNING] No pairs were seeded. Check your Vanna 2.0 version.")
        sys.exit(1)
    print("\nSeeding complete.")
