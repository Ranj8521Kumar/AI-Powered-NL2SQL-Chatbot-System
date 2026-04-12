"""
vanna_setup.py
==============
Initialises the Vanna 2.0 Agent (v0.1.0 package) with:
  - Groq LLM via OpenAI-compatible integration
  - ToolRegistry with RunSqlTool + VisualizeDataTool
  - DemoAgentMemory (in-process store)
  - A simple anonymous UserResolver

Usage:
    from vanna_setup import get_agent, get_memory, make_request_context
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Vanna 2.0 core ─────────────────────────────────────────────────────────────
from vanna import Agent, AgentConfig, ToolRegistry
from vanna.core.user import UserResolver, User
from vanna.core.user.request_context import RequestContext
from vanna.tools.run_sql import RunSqlTool
from vanna.tools.visualize_data import VisualizeDataTool
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService   # Groq is OpenAI-compatible

# ── Config ─────────────────────────────────────────────────────────────────────
DB_PATH    = str(Path(__file__).parent / os.getenv("DB_PATH", "clinic.db"))
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE  = "https://api.groq.com/openai/v1"

# ── Singleton holders ──────────────────────────────────────────────────────────
_agent:  Agent | None = None
_memory: DemoAgentMemory | None = None


# ── Anonymous UserResolver ─────────────────────────────────────────────────────

class AnonUserResolver(UserResolver):
    """
    Resolves every request to a single default 'user' group member.
    Suitable for demo / local deployments with no authentication.
    """

    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(
            id="demo-user",
            username="demo",
            email="demo@clinic.local",
            group_memberships=["users"],
        )


# ── Shared memory ──────────────────────────────────────────────────────────────

def get_memory() -> DemoAgentMemory:
    """Return (or lazily create) the shared DemoAgentMemory singleton."""
    global _memory
    if _memory is None:
        _memory = DemoAgentMemory(max_items=1000)
    return _memory


# ── Agent factory ──────────────────────────────────────────────────────────────

def get_agent() -> Agent:
    """
    Return (or lazily create) the Vanna 2.0 Agent singleton.

    Wiring:
        LLM    → Groq (llama-3.3-70b-versatile) via OpenAI-compatible endpoint
        DB     → SqliteRunner → clinic.db
        Tools  → RunSqlTool + VisualizeDataTool, accessible to 'users' group
        Memory → DemoAgentMemory (shared with seed_memory.py)
        Auth   → AnonUserResolver (all requests map to demo user)
    """
    global _agent
    if _agent is not None:
        return _agent

    if not GROQ_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set.\n"
            "Copy .env.example to .env and add your Groq API key.\n"
            "Get one free at https://console.groq.com"
        )

    # 1. LLM ─────────────────────────────────────────────────────────────────
    llm_service = OpenAILlmService(
        model=GROQ_MODEL,
        api_key=GROQ_KEY,
        base_url=GROQ_BASE,
    )

    # 2. Tool registry ────────────────────────────────────────────────────────
    tools = ToolRegistry()
    tools.register_local_tool(
        RunSqlTool(sql_runner=SqliteRunner(database_path=DB_PATH)),
        access_groups=["users"],
    )
    tools.register_local_tool(
        VisualizeDataTool(),
        access_groups=["users"],
    )

    # 3. Agent ────────────────────────────────────────────────────────────────
    _agent = Agent(
        llm_service=llm_service,
        tool_registry=tools,
        user_resolver=AnonUserResolver(),
        agent_memory=get_memory(),
        config=AgentConfig(),
    )

    return _agent


# ── Request context helper ─────────────────────────────────────────────────────

def make_request_context(remote_ip: str = "127.0.0.1") -> RequestContext:
    """Build a minimal RequestContext for API calls."""
    return RequestContext(
        cookies={},
        headers={},
        remote_addr=remote_ip,
        query_params={},
        metadata={},
    )
