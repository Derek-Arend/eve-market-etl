import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Return a psycopg2 connection to Supabase PostgreSQL."""
    return psycopg2.connect(
        host=os.environ["SUPABASE_HOST"],
        port=os.environ.get("SUPABASE_PORT", 5432),
        dbname=os.environ.get("SUPABASE_DB", "postgres"),
        user=os.environ.get("SUPABASE_USER", "postgres"),
        password=os.environ["SUPABASE_PASSWORD"],
        sslmode="require",
        connect_timeout=10,
    )


def upsert(conn, table: str, rows: list[dict], conflict_column: str):
    """
    Generic upsert helper.
    - rows: list of dicts, all with the same keys
    - conflict_column: the PRIMARY KEY column name
    """
    if not rows:
        return

    columns = list(rows[0].keys())
    values = [tuple(row[col] for col in columns) for row in rows]

    update_cols = [c for c in columns if c != conflict_column]
    update_clause = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in update_cols
    )

    sql = f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES %s
        ON CONFLICT ({conflict_column}) DO UPDATE SET
            {update_clause}
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, values)
    conn.commit()
