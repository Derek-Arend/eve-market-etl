"""
run_market_history.py - Market history import entrypoint.

Usage:
    python run_market_history.py

Fetches 30 days of history for active items only.
Safe to re-run - uses upsert. Purges data older than 30 days.
"""

from etl.db import get_client
from etl.market_history import run_market_history

if __name__ == "__main__":
    client = get_client()
    run_market_history(client)
