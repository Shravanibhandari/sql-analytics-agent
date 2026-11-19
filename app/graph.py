"""LangGraph SQL agent with a self-correction (reflection) loop."""
import os
import re
from typing import List, Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from sqlalchemy import text

from app.db import get_schema_text
from app.safety import is_safe_select_only

load_dotenv()
MAX_RETRIES = 3


class AgentState(TypedDict):
    user_query: str
    schema: str
    generated_sql: str
    db_result: Optional[List[dict]]
    error_message: Optional[str]
    retry_count: int
    logs: List[str]


def initial_state(question: str) -> AgentState:
    return {"user_query": question, "schema": "", "generated_sql": "", "db_result": None,
            "error_message": None, "retry_count": 0, "logs": []}


def clean_sql(raw: str) -> str:
    """Remove markdown fences the LLM may add, and a single trailing semicolon."""
    raw = raw.strip()
    m = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.S | re.I)
    if m:
        raw = m.group(1)
    raw = raw.strip()
    if raw.endswith(";") and raw.count(";") == 1:
        raw = raw[:-1].strip()
    return raw


def groq_llm(prompt: str) -> str:
    from langchain_groq import ChatGroq

    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return llm.invoke(prompt).content


def build_graph(engine, llm_fn, first_attempt_hint: str = ""):
    """llm_fn(prompt) -> str. Passing it in lets tests use a fake LLM.
    first_attempt_hint is extra text added to the FIRST prompt only (used for the demo mode)."""

    def inspect_schema_node(state: AgentState):
        return {"schema": get_schema_text(engine), "retry_count": 0,
                "logs": ["Schema inspected via SQLAlchemy reflection"]}

    def generate_sql_node(state: AgentState):
        prompt = (f"You are a SQLite expert.\nSchema:\n{state['schema']}\n\n"
                  f"Write ONE read-only SQLite SELECT query for: {state['user_query']}\n"
                  "Return only the SQL, no explanation.")
        if state.get("error_message"):
            prompt += (f"\n\nYour previous SQL failed:\n{state['generated_sql']}\n"
                       f"Database error: {state['error_message']}\n"
                       "Fix the query using only columns that exist in the schema.")
        elif first_attempt_hint:
            prompt += f"\n\nNote: {first_attempt_hint}"
        sql = clean_sql(llm_fn(prompt))
        return {"generated_sql": sql, "logs": state["logs"] + [f"Generated SQL: {sql}"]}

    def execute_query_node(state: AgentState):
        sql = state["generated_sql"]
        if not is_safe_select_only(sql):
            return {"error_message": "SECURITY: only a single read-only SELECT is allowed. Query blocked.",
                    "db_result": None, "logs": state["logs"] + ["BLOCKED by AST safety filter"]}
        try:
            with engine.connect() as conn:
                rows = [dict(r._mapping) for r in conn.execute(text(sql))]
            return {"db_result": rows, "error_message": None,
                    "logs": state["logs"] + [f"Executed OK: {len(rows)} rows"]}
        except Exception as e:
            msg = str(getattr(e, "orig", e))
            return {"error_message": msg, "db_result": None,
                    "logs": state["logs"] + [f"Database error: {msg}"]}

    def reflection_node(state: AgentState):
        n = state["retry_count"] + 1
        return {"retry_count": n,
                "logs": state["logs"] + [f"Self-correction attempt {n}/{MAX_RETRIES}: "
                                         f"asking LLM to fix the query"]}

    def route(state: AgentState):
        err = state.get("error_message")
        if not err or err.startswith("SECURITY"):
            return "end"
        return "reflect" if state["retry_count"] < MAX_RETRIES else "end"

    g = StateGraph(AgentState)
    g.add_node("inspect_schema_node", inspect_schema_node)
    g.add_node("generate_sql_node", generate_sql_node)
    g.add_node("execute_query_node", execute_query_node)
    g.add_node("reflection_node", reflection_node)
    g.set_entry_point("inspect_schema_node")
    g.add_edge("inspect_schema_node", "generate_sql_node")
    g.add_edge("generate_sql_node", "execute_query_node")
    g.add_conditional_edges("execute_query_node", route,
                            {"reflect": "reflection_node", "end": END})
    g.add_edge("reflection_node", "generate_sql_node")
    return g.compile()
