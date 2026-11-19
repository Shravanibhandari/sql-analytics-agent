"""Streamlit dashboard. Run: streamlit run app.py"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from app.db import get_engine, get_schema_text
from app.graph import build_graph, groq_llm, initial_state
from app.guardrails import check_input

st.set_page_config(page_title="SQL & Database Analytics Agent", page_icon="📊", layout="wide")

EXAMPLES = [
    "Show orders sorted by date.",
    "Show the top 3 customers by total amount",
    "Show monthly sales trend",
    "Find the average order amount",
    "Total amount per customer",
    "Which customer has placed the most orders?",
]

if "question" not in st.session_state:
    st.session_state["question"] = ""


def set_question(q: str):
    st.session_state["question"] = q


# ---------------------------------------------------------------- sidebar
engine = get_engine()
with st.sidebar:
    st.header("System status")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        st.write(f"**Database:** 🟢 Connected ({engine.dialect.name})")
    except Exception as e:
        st.write("**Database:** 🔴 Not connected")
        st.caption(str(e))
    if os.getenv("GROQ_API_KEY"):
        st.write(f"**LLM:** 🟢 Groq ({os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')})")
    else:
        st.write("**LLM:** 🔴 GROQ_API_KEY missing in .env")
    st.write("**Security:** 🟢 NeMo Guardrails + AST filter")

    with st.expander("Database schema"):
        try:
            st.code(get_schema_text(engine))
        except Exception as e:
            st.caption(str(e))

    st.divider()
    demo = st.checkbox("Demo self-correction (tell LLM the date column is 'created_at')")

# ---------------------------------------------------------------- header
st.title("📊 SQL & Database Analytics Agent")
st.caption("Ask questions in plain English. The agent inspects your schema, writes SQL, "
           "validates it (AST read-only filter), runs it, and self-corrects on errors.")

st.subheader("Ask a question")
cols = st.columns(3)
for i, ex in enumerate(EXAMPLES):
    cols[i % 3].button(ex, key=f"ex{i}", width="stretch",
                       on_click=set_question, args=(ex,))

question = st.text_area("Your question", key="question",
                        placeholder="e.g. Show the top 3 customers by amount", height=90)
run = st.button("Run", type="primary")

# ---------------------------------------------------------------- run
if run:
    if not question.strip():
        st.warning("Please type a question first (or click one of the example buttons).")
        st.stop()

    if not check_input(question):
        st.error("🚫 Security warning: malicious input detected and blocked. "
                 "The database was not queried.")
        st.stop()

    hint = "The date column is called created_at." if demo else ""
    graph = build_graph(engine, groq_llm, first_attempt_hint=hint)
    with st.spinner("Thinking..."):
        try:
            st.session_state["result"] = graph.invoke(initial_state(question))
        except Exception as e:
            st.session_state.pop("result", None)
            st.error(f"Agent error (check GROQ_API_KEY / internet): {e}")
            st.stop()

# Results are kept in session_state so changing the chart type does not wipe them.
state = st.session_state.get("result")
if state:
    with st.expander("Generated SQL", expanded=True):
        st.code(state["generated_sql"], language="sql")
    with st.expander("Execution telemetry & self-correction logs"):
        for line in state["logs"]:
            st.write("•", line)
        st.write(f"Retries used: **{state['retry_count']}**")

    if state["error_message"]:
        st.error(state["error_message"])
    elif state["db_result"]:
        df = pd.DataFrame(state["db_result"])
        st.subheader("Results")
        st.dataframe(df, width="stretch")
        num = list(df.select_dtypes("number").columns)
        cat = list(df.select_dtypes(exclude="number").columns)
        if num and cat:
            kind = st.radio("Chart type", ["Bar", "Line", "Pie"], horizontal=True)
            x, y = cat[0], num[0]
            if kind == "Bar":
                fig = px.bar(df, x=x, y=y)
            elif kind == "Line":
                fig = px.line(df, x=x, y=y, markers=True)
            else:
                fig = px.pie(df, names=x, values=y)
            st.plotly_chart(fig, width="stretch")
    else:
        st.info("Query ran successfully but returned no rows.")