"""AST-based SQL safety filter (sqlglot). Only a single read-only SELECT is allowed."""
import sqlglot
from sqlglot import exp

FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
    exp.Create, exp.Command, exp.Merge, exp.TruncateTable,
)
ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)


def is_safe_select_only(sql_query: str) -> bool:
    """Return True only if sql_query is exactly one read-only SELECT statement."""
    if not sql_query or not sql_query.strip():
        return False
    try:
        statements = [s for s in sqlglot.parse(sql_query, read="sqlite") if s is not None]
    except Exception:
        return False  # unparseable -> reject
    if len(statements) != 1:
        return False  # blocks "SELECT 1; DROP TABLE x"
    tree = statements[0]
    if not isinstance(tree, ALLOWED_ROOTS):
        return False
    return not any(tree.find(node_type) for node_type in FORBIDDEN)
