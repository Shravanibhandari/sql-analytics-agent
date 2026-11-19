"""Streamlit dashboard. Run: streamlit run app.py"""
import pandas as pd
import plotly.express as px
import streamlit as st

from app.db import get_engine
from app.graph import build_graph, groq_llm, initial_state
from app.guardrails import check_input

st.set_page_config(page_title="SQL Analytics Agent", layout="wide")
st.title("🧠 SQL Analytics Agent")
st.caption("Text-to-SQL with self-correction, AST safety filter and NeMo guardrails")

with st.sidebar:
    st.header("Settings")
    demo = st.checkbox("Demo self-correction (tell LLM the date column is 'created_at')")
    st.markdown("Example questions:\n- Show orders sorted by date.\n- Total amount per customer\n"
                "- Monthly sales trend")

question = st.text_input("Ask a question about your data", placeholder="Show orders sorted by date.")

if st.button("Run", type="primary") and question.strip():
    if not check_input(question):
        st.error("🚫 Security warning: malicious input detected and blocked. "
                 "The database was not queried.")
    else:
        hint = "The date column is called created_at." if demo else ""
        graph = build_graph(get_engine(), groq_llm, first_attempt_hint=hint)
        with st.spinner("Thinking..."):
            try:
                state = graph.invoke(initial_state(question))
            except Exception as e:
                st.error(f"Agent error (check your GROQ_API_KEY): {e}")
                st.stop()

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
