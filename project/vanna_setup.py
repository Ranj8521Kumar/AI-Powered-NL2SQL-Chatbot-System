"""
vanna_setup.py
==============
Initialises the Vanna 2.0 Agent with:
  - Groq LLM service  (OpenAI-compatible, model: llama-3.3-70b-versatile)
  - ToolRegistry      (RunSqlTool + VisualizeDataTool)
  - DemoAgentMemory   (in-process learning store)
  - CookieEmailUserResolver

Usage:
    from vanna_setup import get_agent
    agent = get_agent()
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment variables ─────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

# ── Vanna 2.0 imports ──────────────────────────────────────────────────────────
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import CookieEmailUserResolver
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory

# ── Groq uses the OpenAI-compatible integration ────────────────────────────────
from vanna.integrations.openai import OpenAILlmService


# ── Configuration ──────────────────────────────────────────────────────────────
DB_PATH    = str(Path(__file__).parent / os.getenv("DB_PATH", "clinic.db"))
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE  = "https://api.groq.com/openai/v1"

# ── Shared singleton ───────────────────────────────────────────────────────────
_agent:  Agent | None         = None
_memory: DemoAgentMemory | None = None


def get_memory() -> DemoAgentMemory:
    """
    Return (or lazily create) the shared DemoAgentMemory instance.

    Keeping a module-level singleton ensures seed_memory.py and main.py
    operate on the same in-process memory store.
    """
    global _memory
    if _memory is None:
        _memory = DemoAgentMemory(max_items=1000)
    return _memory


def get_agent() -> Agent:
    """
    Return (or lazily create) the Vanna 2.0 Agent singleton.

    Component wiring:
      LLM  → Groq via OpenAI-compatible endpoint
      DB   → SqliteRunner pointing at clinic.db
      Tools→ RunSqlTool (SQL execution) + VisualizeDataTool (charts)
      Mem  → DemoAgentMemory (shared with seed_memory.py)
      Auth → CookieEmailUserResolver (demo-friendly)
    """
    global _agent
    if _agent is not None:
        return _agent

    if not GROQ_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    # 1. LLM service ─────────────────────────────────────────────────────────
    llm_service = OpenAILlmService(
        model=GROQ_MODEL,
        api_key=GROQ_KEY,
        base_url=GROQ_BASE,
    )

    # 2. Tool registry ────────────────────────────────────────────────────────
    tools = ToolRegistry()

    sql_runner = SqliteRunner(database_path=DB_PATH)

    tools.register_local_tool(
        RunSqlTool(sql_runner=sql_runner),
        access_groups=["users"],
    )
    tools.register_local_tool(
        VisualizeDataTool(),
        access_groups=["users"],
    )

    # 3. Agent memory (shared singleton) ─────────────────────────────────────
    memory = get_memory()

    # 4. User resolver ────────────────────────────────────────────────────────
    user_resolver = CookieEmailUserResolver()

    # 5. Assemble the Agent ───────────────────────────────────────────────────
    _agent = Agent(
        llm_service=llm_service,
        tool_registry=tools,
        user_resolver=user_resolver,
        agent_memory=memory,
        config=AgentConfig(),
    )

    return _agent
