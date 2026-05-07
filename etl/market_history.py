"""
market_history.py - Market history import for active items only.

Strategy:
- Only fetch history for items with live orders in monitored regions
- Only keep last 30 days
- Run daily after market_prices

ESI endpoint: GET /markets/{region_id}/history/?type_id={type_id}
"""

from datetime import datetime, timezone, timedelta
from tqdm import tqdm

from etl.esi import esi_get
from etl.db import upsert, get_client


def now():
    return datetime.now(timezone.utc).isoformat()


def get_active_type_ids(client, region_id: int) -> list[int]:
    """Get all unique type IDs that have live orders in a region.
    Uses pagination to bypass Supabase's 1000 row default limit.
    """
    type_ids = set()
    page_size = 1000
    offset = 0

    while True:
        response = client.table("market_orders") \
            .select("type_id") \
            .eq("region_id", region_id) \
            .range(offset, offset + page_size - 1) \
            .execute()

        rows = response.data
        if not rows:
            break

        for row in rows:
            type_ids.add(row["type_id"])

        if len(rows) < page_size:
            break

        offset += page_size

    return list(type_ids)


def get_active_region_ids(client) -> list[int]:
    response = client.table("monitored_regions") \
        .select("region_id") \
        .eq("is_active", True) \
        .execute()
    return [row["region_id"] for row in response.data]


def import_history_for_region(client, region_id: int):
    """Fetch and store 30 days of history for all active items in a region."""
    print(f"\n  Fetching active type IDs for region {region_id}...")
    type_ids = get_active_type_ids(client, region_id)
    print(f"  Found {len(type_ids)} active types")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()

    rows = []
    skipped = 0

    for type_id in tqdm(type_ids, desc=f"History region {region_id}"):
        try:
            history = esi_get(f"/markets/{region_id}/history/", params={"type_id": type_id})

            for entry in history:
                if entry.get("date", "") < cutoff:
                    continue
                rows.append({
                    "region_id":   region_id,
                    "type_id":     type_id,
                    "date":        entry["date"],
                    "highest":     entry.get("highest"),
                    "lowest":      entry.get("lowest"),
                    "average":     entry.get("average"),
                    "volume":      entry.get("volume"),
                    "order_count": entry.get("order_count"),
                })

            # Batch upsert every 500 rows
            if len(rows) >= 500:
                upsert(client, "market_history", rows)
                rows = []

        except Exception as e:
            print(f"  [WARN] Failed history for type {type_id}: {e}")
            skipped += 1
            continue

    if rows:
        upsert(client, "market_history", rows)

    print(f"  ✓ History imported for region {region_id} ({skipped} skipped)")


def purge_old_history(client):
    """Remove history older than 30 days to keep storage lean."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    client.table("market_history").delete().lt("date", cutoff).execute()
    print(f"  ✓ Purged history older than {cutoff}")


def run_market_history(client):
    print("=" * 60)
    print("EVE Market History Import")
    print("=" * 60)

    region_ids = get_active_region_ids(client)

    if not region_ids:
        print("  [WARN] No active regions found.")
        return

    for region_id in region_ids:
        import_history_for_region(client, region_id)

    purge_old_history(client)

    print("\n✓ Market history import complete!")
