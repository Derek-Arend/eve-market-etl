"""
run_market_prices.py - Daily market prices import entrypoint.

Usage:
    python run_market_prices.py

Fetches global adjusted/average prices from /markets/prices.
Safe to re-run - uses upsert.
"""

from etl.db import get_client
from etl.market import run_market_prices

if __name__ == "__main__":
    client = get_client()
    run_market_prices(client)
