# AI-Powered NL2SQL System

A production-quality **Natural Language to SQL chatbot** built with **Vanna 2.0**, **FastAPI**, and **Groq LLM**. Ask plain-English questions about a clinic database and get back SQL, tabular results, and Plotly charts — all in a minimalist web UI.

---

## Architecture

```
User (Browser UI)
      │  HTTP Request
      ▼
FastAPI Backend  (POST /chat, GET /health)
      │  Validated Request
      ▼
Vanna 2.0 Agent
  ├─ Groq LLM  (llama-3.3-70b-versatile)  ← NL → SQL
  ├─ ToolRegistry  (RunSqlTool, VisualizeDataTool)
  └─ DemoAgentMemory  (15 pre-seeded Q&A pairs)
      │  Generated SQL
      ▼
SQL Validator  (SELECT-only, no dangerous keywords)
      │  Safe SQL
      ▼
SqliteRunner → clinic.db
  (patients · doctors · appointments · treatments · invoices)
      │  Results
      ▼
Output Layer
  ├─ Structured JSON  (columns + rows)
  ├─ Natural-language summary
  └─ Plotly chart (bar / line / pie — auto-detected)
      │  JSON Response
      ▼
User (rendered table + chart in browser)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Web Framework | FastAPI + Uvicorn |
| AI Framework | Vanna 2.0 |
| LLM Provider | **Groq** (`llama-3.3-70b-versatile`) |
| Database | SQLite (`clinic.db`) |
| Charts | Plotly |
| Data Processing | Pandas |
| Frontend | Vanilla HTML / CSS / JS |
| Config | python-dotenv |

---

## Project Structure

```
project/
├── setup_database.py   # Creates clinic.db with realistic dummy data
├── seed_memory.py      # Pre-seeds 15 Q&A pairs into DemoAgentMemory
├── vanna_setup.py      # Vanna 2.0 Agent initialisation (Groq)
├── main.py             # FastAPI application (POST /chat, GET /health)
├── sql_validator.py    # SQL safety validator (SELECT-only guard)
├── chart_generator.py  # Auto Plotly chart generation
├── requirements.txt    # All Python dependencies
├── .env.example        # Environment variable template
├── README.md           # This file
├── RESULTS.md          # 20-question test results
├── clinic.db           # Generated SQLite database
└── static/
    ├── index.html      # Chat UI
    ├── style.css       # Minimalist black/gray/white styling
    └── app.js          # Frontend logic
```

---

## Setup Instructions

### 1. Clone / copy the project
```bash
cd "e:\AI-Powered NL2SQL System\project"
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
# Copy the template
copy .env.example .env

# Open .env and set your Groq API key:
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
```

Get a free Groq key at → https://console.groq.com

### 5. Create the database
```bash
python setup_database.py
```
Expected output:
```
Creating schema ...
Inserting 15 doctors ...
Inserting 200 patients ...
Inserting 500 appointments ...
Inserting 350 treatments ...
Inserting 300 invoices ...

  Database created at: clinic.db
  Created 200 patients, 15 doctors, 500 appointments, 348 treatments, 298 invoices
```

### 6. Seed agent memory
```bash
python seed_memory.py
```
Expected output:
```
Seeding DemoAgentMemory with Q&A pairs ...

  [PATIENT     ] How many patients do we have?
  [PATIENT     ] List all patients from Mumbai
  ...
  15/15 pairs seeded into DemoAgentMemory
```

### 7. Start the API server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 8. Open the chat UI
Visit → **http://localhost:8000**

---

## API Documentation

Interactive docs available at → http://localhost:8000/api/docs

### `GET /health`

Returns system status.

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "database": "connected",
  "database_path": "clinic.db",
  "agent_memory_items": 15,
  "llm_provider": "Groq (llama-3.3-70b-versatile)",
  "version": "1.0.0"
}
```

---

### `POST /chat`

Ask a natural language question.

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'
```

**Response:**
```json
{
  "message": "The total_patients is **200**.",
  "sql_query": "SELECT COUNT(*) AS total_patients FROM patients",
  "columns": ["total_patients"],
  "rows": [[200]],
  "row_count": 1,
  "chart": null,
  "chart_type": null,
  "execution_time_ms": 843,
  "error": null
}
```

**Example with chart:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Show appointments per month"}'
```

---

## SQL Validation Rules

All AI-generated SQL is validated before execution:

| Rule | Detail |
|---|---|
| SELECT-only | `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` etc. are rejected |
| No dangerous keywords | `EXEC`, `xp_`, `sp_`, `GRANT`, `REVOKE`, `SHUTDOWN` are blocked |
| No system tables | Access to `sqlite_master`, `sqlite_schema` is blocked |
| Single statement | Stacked statements separated by `;` are rejected |

---

## Database Schema

### `patients`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto |
| first_name | TEXT | |
| last_name | TEXT | |
| gender | TEXT | Male / Female / Other |
| date_of_birth | DATE | |
| city | TEXT | 10 Indian cities |
| email | TEXT | Nullable (15% NULL) |
| phone | TEXT | Nullable (10% NULL) |
| created_at | DATETIME | |

### `doctors`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| specialization | TEXT | Cardiology, Dermatology, Orthopedics, General, Pediatrics |
| email | TEXT | Nullable |
| phone | TEXT | Nullable |
| years_experience | INTEGER | |

### `appointments`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| patient_id | FK → patients | |
| doctor_id | FK → doctors | |
| appointment_date | DATE | Last 12 months |
| status | TEXT | Scheduled / Completed / Cancelled |
| notes | TEXT | Nullable |

### `treatments`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| appointment_id | FK → appointments | Only for Completed appts |
| treatment_name | TEXT | Specialization-specific |
| cost | REAL | 50–5000 |
| description | TEXT | Nullable |

### `invoices`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| patient_id | FK → patients | |
| appointment_id | FK → appointments | |
| total_amount | REAL | 100–5000 |
| status | TEXT | Paid / Pending / Overdue |
| invoice_date | DATE | |
| due_date | DATE | invoice_date + 30 days |
| paid_date | DATE | Nullable |

---

## Switching LLM Providers

The code is fully modular. To switch providers, edit `vanna_setup.py`:

### Switch to Google Gemini
```python
from vanna.integrations.gemini import GeminiLlmService
llm_service = GeminiLlmService(
    model="gemini-2.5-flash",
    api_key=os.getenv("GOOGLE_API_KEY"),
)
```

### Switch to Ollama (local, no API key)
```python
from vanna.integrations.openai import OpenAILlmService
llm_service = OpenAILlmService(
    model="llama3",
    api_key="ollama",
    base_url="http://localhost:11434/v1",
)
```

---

## License

MIT — built as an internship assignment demonstration.
