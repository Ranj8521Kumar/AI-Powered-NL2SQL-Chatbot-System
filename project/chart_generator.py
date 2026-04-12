"""
chart_generator.py
==================
Auto-generates Plotly charts from SQL query results.

Strategy:
  - Detects numeric columns automatically
  - Chooses chart type based on data shape:
      * 1 text + 1 numeric column  → bar chart
      * 1 text + 2 numeric columns → grouped bar
      * Date/month column detected → line chart
      * Single aggregate value     → no chart (not useful)
  - Returns Plotly figure as a JSON-serialisable dict.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


# ── Helpers ────────────────────────────────────────────────────────────────────

_DATE_PATTERNS = re.compile(
    r"(date|month|year|week|day|period|time)", re.IGNORECASE
)

_NUMERIC_TYPES = {"int64", "float64", "int32", "float32"}


def _is_date_like(col: str) -> bool:
    return bool(_DATE_PATTERNS.search(col))


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if str(df[c].dtype) in _NUMERIC_TYPES]


def _text_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if str(df[c].dtype) not in _NUMERIC_TYPES]


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_chart(
    columns: list[str],
    rows: list[list[Any]],
    question: str = "",
) -> dict | None:
    """
    Build a Plotly figure from query results.

    Args:
        columns: Column names from the SQL result set.
        rows:    Row data as a list of lists.
        question: Original NL question (used for title inference).

    Returns:
        A dict with keys ``{"data": [...], "layout": {...}}`` ready for
        ``JSON.stringify`` on the frontend, or ``None`` if no chart is useful.
    """
    if not columns or not rows:
        return None

    df = pd.DataFrame(rows, columns=columns)

    # Attempt numeric coercion for string-encoded numbers
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass

    num_cols  = _numeric_cols(df)
    text_cols = _text_cols(df)

    # Single scalar result — no chart useful
    if len(df) == 1 and len(num_cols) == 1 and len(text_cols) == 0:
        return None

    # Too many rows without a clear grouping column — skip
    if len(df) > 200:
        return None

    title = _infer_title(question)

    # ── Line chart: time-series data ──────────────────────────────────────────
    date_text_cols = [c for c in text_cols if _is_date_like(c)]
    if date_text_cols and num_cols:
        x_col = date_text_cols[0]
        y_col = num_cols[0]
        fig = px.line(
            df.sort_values(x_col),
            x=x_col,
            y=y_col,
            title=title,
            markers=True,
            color_discrete_sequence=["#4f8ef7"],
        )
        return _style_and_export(fig)

    # ── Bar chart: 1 category + 1 numeric ────────────────────────────────────
    if len(text_cols) >= 1 and len(num_cols) >= 1:
        x_col  = text_cols[0]
        y_cols = num_cols[:2]          # max 2 numeric columns

        if len(y_cols) == 1:
            fig = px.bar(
                df.sort_values(y_cols[0], ascending=False).head(20),
                x=x_col,
                y=y_cols[0],
                title=title,
                color_discrete_sequence=["#4f8ef7"],
            )
        else:
            fig = px.bar(
                df.head(20),
                x=x_col,
                y=y_cols,
                title=title,
                barmode="group",
            )
        return _style_and_export(fig)

    # ── Pie chart: 1 category + 1 small numeric set ──────────────────────────
    if len(text_cols) == 1 and len(num_cols) == 1 and len(df) <= 10:
        fig = px.pie(
            df,
            names=text_cols[0],
            values=num_cols[0],
            title=title,
        )
        return _style_and_export(fig)

    return None


def _infer_title(question: str) -> str:
    """Create a chart title from the original question."""
    if not question:
        return "Query Results"
    # Capitalise and trim
    return question.strip().rstrip("?").capitalize()


def _style_and_export(fig: go.Figure) -> dict:
    """Apply consistent dark-minimal styling and return as a JSON-safe dict."""
    fig.update_layout(
        paper_bgcolor="#1a1a1a",
        plot_bgcolor="#1a1a1a",
        font=dict(family="Inter, system-ui, sans-serif", color="#e0e0e0", size=13),
        title_font=dict(size=15, color="#ffffff"),
        xaxis=dict(gridcolor="#333333", zerolinecolor="#333333"),
        yaxis=dict(gridcolor="#333333", zerolinecolor="#333333"),
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(bgcolor="#1a1a1a", bordercolor="#333333"),
    )
    raw = fig.to_dict()
    return _make_json_safe(raw)


def _make_json_safe(obj):
    """
    Recursively convert numpy / pandas types to native Python so that
    Pydantic / json.dumps can serialise the Plotly figure dict.
    """
    import numpy as np

    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    # pandas Timestamp, etc.
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj

