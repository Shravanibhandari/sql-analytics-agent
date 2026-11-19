import pytest
from sqlalchemy import create_engine, text
from app.graph import MAX_RETRIES, build_graph, initial_state


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE orders (id INTEGER, order_date TEXT)"))
        c.execute(text("INSERT INTO orders VALUES (2,'2026-02-01'),(1,'2026-01-01')"))
    return eng


def test_self_correction(engine):
    prompts = []

    def fake_llm(prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            return "SELECT * FROM orders ORDER BY created_at"   # wrong column
        return "SELECT * FROM orders ORDER BY order_date"        # corrected

    out = build_graph(engine, fake_llm).invoke(initial_state("orders by date"))
    assert len(prompts) == 2
    assert "created_at" in prompts[1] and "no such column" in prompts[1].lower()
    assert out["error_message"] is None
    assert out["retry_count"] == 1
    assert [r["id"] for r in out["db_result"]] == [1, 2]


def test_retry_cap(engine):
    out = build_graph(engine, lambda p: "SELECT nope FROM orders").invoke(initial_state("x"))
    assert out["retry_count"] == MAX_RETRIES
    assert out["error_message"]


def test_write_query_blocked_and_table_intact(engine):
    out = build_graph(engine, lambda p: "DROP TABLE orders").invoke(initial_state("x"))
    assert out["error_message"].startswith("SECURITY")
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM orders")).scalar() == 2
