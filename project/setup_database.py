"""
setup_database.py
=================
Creates and populates clinic.db with realistic dummy data.

Tables:
    patients      — 200 rows
    doctors       — 15 rows
    appointments  — 500 rows
    treatments    — 350 rows
    invoices      — 300 rows

Run:
    python setup_database.py
"""

import sqlite3
import random
from datetime import date, timedelta
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "clinic.db"
random.seed(42)

# ── Data Pools ─────────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav", "Aditya", "Akash", "Ananya", "Anjali", "Arjun", "Aryan", "Ayesha",
    "Deepak", "Deepika", "Dev", "Divya", "Gaurav", "Geeta", "Harsh", "Ishaan",
    "Ishita", "Jay", "Jaya", "Kabir", "Kajal", "Karan", "Kavya", "Kiara",
    "Kunal", "Lakshmi", "Manish", "Meera", "Mihir", "Mohan", "Nandini", "Neha",
    "Nikhil", "Nisha", "Om", "Pankaj", "Pooja", "Priya", "Rahul", "Raj",
    "Rajesh", "Ravi", "Reena", "Ritesh", "Rohit", "Roshni", "Sachin", "Samir",
    "Sanjay", "Sara", "Saurabh", "Shiv", "Shreya", "Simran", "Sneha", "Sonia",
    "Suresh", "Swati", "Tanvi", "Tarun", "Uday", "Uma", "Varun", "Veer",
    "Vidya", "Vikram", "Virat", "Vivek", "Yamini", "Yash", "Zara", "Zubin",
]

LAST_NAMES = [
    "Agarwal", "Bhatia", "Chaudhary", "Chopra", "Das", "Desai", "Dubey",
    "Ghosh", "Goyal", "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Kaur",
    "Khan", "Khanna", "Kumar", "Malhotra", "Mehta", "Mishra", "Nair",
    "Pandey", "Patel", "Pillai", "Rao", "Reddy", "Saxena", "Shah",
    "Sharma", "Singh", "Sinha", "Srivastava", "Tiwari", "Varma", "Verma", "Yadav",
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
]
CITY_WEIGHTS = [20, 18, 15, 12, 10, 8, 7, 5, 3, 2]

DOCTOR_PROFILES = [
    ("Dr. Arjun Sharma",    "Cardiology",    16),
    ("Dr. Priya Mehta",     "Dermatology",   12),
    ("Dr. Rohit Gupta",     "Orthopedics",   20),
    ("Dr. Ananya Singh",    "General",        8),
    ("Dr. Vikram Nair",     "Pediatrics",    14),
    ("Dr. Kavya Reddy",     "Cardiology",     9),
    ("Dr. Manish Joshi",    "Dermatology",   22),
    ("Dr. Deepika Patel",   "Orthopedics",    6),
    ("Dr. Sachin Verma",    "General",       18),
    ("Dr. Neha Kapoor",     "Pediatrics",    11),
    ("Dr. Karan Malhotra",  "Cardiology",     5),
    ("Dr. Simran Kaur",     "Dermatology",   17),
    ("Dr. Aditya Rao",      "Orthopedics",   13),
    ("Dr. Sneha Iyer",      "General",        7),
    ("Dr. Rahul Das",       "Pediatrics",    25),
]

TREATMENT_MAP = {
    "Dermatology":  ["Acne Treatment", "Skin Biopsy", "Chemical Peel", "Laser Therapy", "Eczema Management"],
    "Cardiology":   ["ECG", "Echocardiogram", "Stress Test", "Angiography", "Blood Pressure Management"],
    "Orthopedics":  ["X-Ray Analysis", "Joint Injection", "Physical Therapy", "Fracture Management", "MRI Review"],
    "General":      ["General Checkup", "Blood Test", "Vaccination", "Diabetes Management", "Fever Treatment"],
    "Pediatrics":   ["Child Checkup", "Growth Assessment", "Immunization", "Nutritional Counseling", "Allergy Test"],
}

APPT_STATUSES  = ["Scheduled", "Completed", "Cancelled"]
APPT_WEIGHTS   = [20, 60, 20]
INV_STATUSES   = ["Paid", "Pending", "Overdue"]
INV_WEIGHTS    = [60, 25, 15]


# ── Helpers ────────────────────────────────────────────────────────────────────

def rand_date(start: date, end: date) -> date:
    """Return a random date between start (inclusive) and end (inclusive)."""
    return start + timedelta(days=random.randint(0, (end - start).days))


def maybe_null(value, prob: float = 0.15):
    """Return None with probability *prob*, else return *value*."""
    return None if random.random() < prob else value


# ── Schema ─────────────────────────────────────────────────────────────────────

def create_schema(conn: sqlite3.Connection) -> None:
    """Drop existing tables and recreate schema."""
    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS treatments;
        DROP TABLE IF EXISTS appointments;
        DROP TABLE IF EXISTS doctors;
        DROP TABLE IF EXISTS patients;

        PRAGMA foreign_keys = ON;

        CREATE TABLE patients (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name    TEXT    NOT NULL,
            last_name     TEXT    NOT NULL,
            gender        TEXT    NOT NULL CHECK(gender IN ('Male','Female','Other')),
            date_of_birth DATE    NOT NULL,
            city          TEXT    NOT NULL,
            email         TEXT,
            phone         TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE doctors (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            specialization   TEXT    NOT NULL,
            email            TEXT,
            phone            TEXT,
            years_experience INTEGER NOT NULL
        );

        CREATE TABLE appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id       INTEGER NOT NULL REFERENCES patients(id),
            doctor_id        INTEGER NOT NULL REFERENCES doctors(id),
            appointment_date DATE    NOT NULL,
            status           TEXT    NOT NULL CHECK(status IN ('Scheduled','Completed','Cancelled')),
            notes            TEXT
        );

        CREATE TABLE treatments (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL REFERENCES appointments(id),
            treatment_name TEXT    NOT NULL,
            cost           REAL    NOT NULL,
            description    TEXT
        );

        CREATE TABLE invoices (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id     INTEGER NOT NULL REFERENCES patients(id),
            appointment_id INTEGER NOT NULL REFERENCES appointments(id),
            total_amount   REAL    NOT NULL,
            status         TEXT    NOT NULL CHECK(status IN ('Paid','Pending','Overdue')),
            invoice_date   DATE    NOT NULL,
            due_date       DATE    NOT NULL,
            paid_date      DATE
        );
    """)


# ── Inserters ──────────────────────────────────────────────────────────────────

def insert_doctors(conn: sqlite3.Connection) -> list:
    """Insert 15 doctors and return their IDs."""
    ids = []
    for name, spec, yrs in DOCTOR_PROFILES:
        parts = name.split()
        email = maybe_null(f"{parts[1].lower()}.{parts[-1].lower()}@clinic.in", 0.10)
        phone = maybe_null(f"+91-{random.randint(7000000000, 9999999999)}", 0.10)
        cur = conn.execute(
            "INSERT INTO doctors (name, specialization, email, phone, years_experience) VALUES (?,?,?,?,?)",
            (name, spec, email, phone, yrs),
        )
        ids.append(cur.lastrowid)
    return ids


def insert_patients(conn: sqlite3.Connection, n: int = 200) -> list:
    """Insert *n* patients and return their IDs."""
    ids = []
    for _ in range(n):
        first  = random.choice(FIRST_NAMES)
        last   = random.choice(LAST_NAMES)
        gender = random.choices(["Male", "Female", "Other"], weights=[48, 48, 4])[0]
        dob    = rand_date(date(1950, 1, 1), date(2008, 12, 31))
        city   = random.choices(CITIES, weights=CITY_WEIGHTS)[0]
        email  = maybe_null(f"{first.lower()}.{last.lower()}{random.randint(1,99)}@mail.com", 0.20)
        phone  = maybe_null(f"+91-{random.randint(7000000000, 9999999999)}", 0.10)
        cur = conn.execute(
            "INSERT INTO patients (first_name, last_name, gender, date_of_birth, city, email, phone) "
            "VALUES (?,?,?,?,?,?,?)",
            (first, last, gender, dob.isoformat(), city, email, phone),
        )
        ids.append(cur.lastrowid)
    return ids


def insert_appointments(conn: sqlite3.Connection, patient_ids: list, doctor_ids: list, n: int = 500) -> list:
    """
    Insert *n* appointments with realistic distribution.
    Returns list of (appt_id, patient_id, doctor_id, appt_date, status).
    """
    # Top 20 patients are frequent visitors (repeat visitors)
    p_weights = [10 if i < 20 else (3 if i < 60 else 1) for i in range(len(patient_ids))]
    # Some doctors are busier —  matches DOCTOR_PROFILES order
    d_weights  = [10, 9, 8, 7, 6, 8, 7, 6, 5, 5, 4, 4, 3, 3, 2]

    today = date.today()
    start = today - timedelta(days=365)
    records = []

    for _ in range(n):
        pid    = random.choices(patient_ids, weights=p_weights)[0]
        did    = random.choices(doctor_ids,  weights=d_weights)[0]
        adate  = rand_date(start, today)
        status = random.choices(APPT_STATUSES, weights=APPT_WEIGHTS)[0]
        notes  = maybe_null(f"Follow-up: {random.choice(['required', 'not required'])}", 0.50)
        cur = conn.execute(
            "INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, notes) "
            "VALUES (?,?,?,?,?)",
            (pid, did, adate.isoformat(), status, notes),
        )
        records.append((cur.lastrowid, pid, did, adate, status))

    return records


def insert_treatments(conn: sqlite3.Connection, appointments: list, n: int = 350) -> None:
    """Insert treatments only for Completed appointments."""
    doc_spec = {row[0]: row[1] for row in conn.execute("SELECT id, specialization FROM doctors")}

    completed = [
        (aid, pid, did, adate)
        for aid, pid, did, adate, status in appointments
        if status == "Completed"
    ]
    selected = random.sample(completed, min(n, len(completed)))

    for aid, pid, did, adate in selected:
        spec  = doc_spec.get(did, "General")
        tname = random.choice(TREATMENT_MAP.get(spec, TREATMENT_MAP["General"]))
        cost  = round(random.uniform(50.0, 5000.0), 2)
        desc  = maybe_null(f"Patient received {tname.lower()} treatment successfully.", 0.30)
        conn.execute(
            "INSERT INTO treatments (appointment_id, treatment_name, cost, description) VALUES (?,?,?,?)",
            (aid, tname, cost, desc),
        )


def insert_invoices(conn: sqlite3.Connection, appointments: list, n: int = 300) -> None:
    """Insert invoices for a subset of Completed appointments."""
    completed = [
        (aid, pid, adate)
        for aid, pid, did, adate, status in appointments
        if status == "Completed"
    ]
    selected = random.sample(completed, min(n, len(completed)))

    for aid, pid, adate in selected:
        total        = round(random.uniform(100.0, 5000.0), 2)
        status       = random.choices(INV_STATUSES, weights=INV_WEIGHTS)[0]
        invoice_date = adate + timedelta(days=random.randint(0, 3))
        due_date     = invoice_date + timedelta(days=30)
        paid_date    = None
        if status == "Paid":
            paid_date = (invoice_date + timedelta(days=random.randint(1, 25))).isoformat()

        conn.execute(
            "INSERT INTO invoices (patient_id, appointment_id, total_amount, status, "
            "invoice_date, due_date, paid_date) VALUES (?,?,?,?,?,?,?)",
            (pid, aid, total, status, invoice_date.isoformat(), due_date.isoformat(), paid_date),
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Orchestrate database creation and population."""
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"  Removed existing {DB_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("Creating schema ...")
    create_schema(conn)

    print("Inserting 15 doctors ...")
    doctor_ids = insert_doctors(conn)

    print("Inserting 200 patients ...")
    patient_ids = insert_patients(conn, 200)

    print("Inserting 500 appointments ...")
    appointments = insert_appointments(conn, patient_ids, doctor_ids, 500)

    print("Inserting 350 treatments ...")
    insert_treatments(conn, appointments, 350)

    print("Inserting 300 invoices ...")
    insert_invoices(conn, appointments, 300)

    conn.commit()

    # ── Summary ────────────────────────────────────────────────────────────────
    counts = {
        tbl: conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        for tbl in ("patients", "doctors", "appointments", "treatments", "invoices")
    }
    conn.close()

    print(f"\n  Database created at: {DB_PATH}")
    print(
        f"  Created {counts['patients']} patients, {counts['doctors']} doctors, "
        f"{counts['appointments']} appointments, {counts['treatments']} treatments, "
        f"{counts['invoices']} invoices"
    )


if __name__ == "__main__":
    main()
