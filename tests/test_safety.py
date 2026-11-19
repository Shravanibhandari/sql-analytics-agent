import pytest
from app.safety import is_safe_select_only


@pytest.mark.parametrize("sql", [
    "DELETE FROM users",
    "DROP TABLE orders; --",
    "UPDATE orders SET amount = 0",
    "INSERT INTO orders VALUES (1,'x','y',1)",
    "ALTER TABLE orders ADD COLUMN x INT",
    "SELECT 1; DROP TABLE orders",
    "",
])
def test_blocks_dangerous(sql):
    assert not is_safe_select_only(sql)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM orders",
    "SELECT customer, SUM(amount) FROM orders GROUP BY customer",
    "WITH t AS (SELECT * FROM orders) SELECT * FROM t",
])
def test_allows_select(sql):
    assert is_safe_select_only(sql)
