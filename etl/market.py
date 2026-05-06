"""
market.py - Market data import module.

Two functions:
1. import_market_prices()  - global adjusted/average prices, run daily
2. import_market_orders()  - live order book for active regions, run every 5 min
"""

from datetime import datetime, timezone
from tqdm import tqdm

from etl.esi import esi_get, esi_get_all_pages
from etl.db import upsert, get_client


def now():
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------
# MARKET PRICES (daily)
# Global adjusted/average prices from /markets/prices
# ----------------------------------------------------------------

def import_market_prices(client):
    print("\n[1/2] Importing global market prices...")

    data = esi_get("/markets/prices/")

    rows = []
    for item in data:
        # Skip items with no type_id
        if "type_id" not in item:
            continue
        rows.append({
            "type_id":        item["type_id"],
            "adjusted_price": item.get("adjusted_price"),
            "average_price":  item.get("average_price"),
            "fetched_at":     now(),
        })

    # Batch upsert in chunks of 500
    for i in range(0, len(rows), 500):
        upsert(client, "market_prices", rows[i:i+500])

    print(f"  ✓ {len(rows)} market prices imported")


# ----------------------------------------------------------------
# MARKET ORDERS (every 5 min)
# Live order book for all active monitored regions
# ----------------------------------------------------------------

def get_active_region_ids(client) -> list[int]:
    """Fetch region IDs where is_active = TRUE from monitored_regions."""
    response = client.table("monitored_regions")\
        .select("region_id")\
        .eq("is_active", True)\
        .execute()
    return [row["region_id"] for row in response.data]


def import_orders_for_region(client, region_id: int):
    """
    Fetch and upsert all orders for a single region.
    ESI paginates orders - we fetch all pages.
    """
    print(f"  Fetching orders for region {region_id}...")

    try:
        orders = esi_get_all_pages(
            f"/markets/{region_id}/orders/",
            params={"order_type": "all"}
        )
    except Exception as e:
        print(f"  [WARN] Failed to fetch orders for region {region_id}: {e}")
        return 0

    rows = []
    for order in orders:
        rows.append({
            "order_id":      order["order_id"],
            "region_id":     region_id,
            "type_id":       order["type_id"],
            "location_id":   order["location_id"],
            "system_id":     order.get("system_id"),
            "is_buy_order":  order["is_buy_order"],
            "price":         order["price"],
            "volume_total":  order["volume_total"],
            "volume_remain": order["volume_remain"],
            "min_volume":    order.get("min_volume", 1),
            "range":         order.get("range"),
            "duration":      order.get("duration"),
            "issued":        order.get("issued"),
            "fetched_at":    now(),
        })

    # Batch upsert in chunks of 500
    for i in range(0, len(rows), 500):
        upsert(client, "market_orders", rows[i:i+500])

    print(f"    ✓ {len(rows)} orders upserted for region {region_id}")
    return len(rows)


def import_market_orders(client):
    print("\n[2/2] Importing market orders for active regions...")

    region_ids = get_active_region_ids(client)

    if not region_ids:
        print("  [WARN] No active regions found in monitored_regions table.")
        return

    print(f"  Active regions: {region_ids}")

    total = 0
    for region_id in region_ids:
        total += import_orders_for_region(client, region_id)

    print(f"\n  ✓ Total orders upserted: {total}")


# ----------------------------------------------------------------
# ENTRYPOINTS
# ----------------------------------------------------------------

def run_market_prices(client):
    print("=" * 60)
    print("EVE Market Prices Import")
    print("=" * 60)
    import_market_prices(client)
    print("\n✓ Market prices import complete!")


def run_market_orders(client):
    print("=" * 60)
    print("EVE Market Orders Import")
    print("=" * 60)
    import_market_orders(client)
    print("\n✓ Market orders import complete!")
