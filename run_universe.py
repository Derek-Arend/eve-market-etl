"""
run_universe.py - One-time universe import entrypoint.

Usage:
    python run_universe.py

Expected runtime: 2-4 hours due to ~40,000 type detail calls.
Safe to re-run at any time - all inserts use upsert.
"""

from etl.db import get_connection
from etl.universe import run_universe_import

if __name__ == "__main__":
    conn = get_connection()
    try:
        run_universe_import(conn)
    finally:
        conn.close()
