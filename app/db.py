"""Database layer: SQLAlchemy engine + schema reflection."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

load_dotenv()


def get_engine(url: str | None = None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///sample.db")
    return create_engine(url)


def get_schema_text(engine) -> str:
    """Use SQLAlchemy reflection to describe every table and column."""
    insp = inspect(engine)
    lines = []
    for table in insp.get_table_names():
        cols = [f"{c['name']} ({c['type']})" for c in insp.get_columns(table)]
        lines.append(f"Table {table}: " + ", ".join(cols))
    return "\n".join(lines)
