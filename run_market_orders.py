"""
run_market_orders.py - Market orders import entrypoint.

Usage:
    python run_market_orders.py

Fetches live order book for all active monitored regions.
Safe to re-run - uses upsert.
"""

from etl.db import get_client
from etl.market import run_market_orders

if __name__ == "__main__":
    client = get_client()
    run_market_orders(client)
