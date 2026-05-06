"""
Universe import module.
Fetches and stores all static universe data from ESI:
  categories → groups → types → regions → constellations → systems → stations

This is a one-time import. Re-running is safe due to upsert pattern.
Expected runtime: 2-4 hours (due to ~40,000 type detail calls)
"""

from datetime import datetime, timezone
from tqdm import tqdm

from etl.esi import esi_get, esi_get_all_pages
from etl.db import upsert


def now():
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------
# CATEGORIES
# ----------------------------------------------------------------

def import_categories(conn):
    print("\n[1/7] Importing categories...")
    category_ids = esi_get("/universe/categories/")

    rows = []
    for cid in tqdm(category_ids, desc="Categories"):
        data = esi_get(f"/universe/categories/{cid}")
        rows.append({
            "category_id": data["category_id"],
            "name":        data["name"],
            "published":   data.get("published", True),
            "fetched_at":  now(),
        })

    upsert(conn, "categories", rows, "category_id")
    print(f"  ✓ {len(rows)} categories imported")


# ----------------------------------------------------------------
# GROUPS
# ----------------------------------------------------------------

def import_groups(conn):
    print("\n[2/7] Importing groups...")
    group_ids = esi_get("/universe/groups/")

    # ESI paginates groups - fetch all pages
    group_ids = esi_get_all_pages("/universe/groups/")

    rows = []
    for gid in tqdm(group_ids, desc="Groups"):
        data = esi_get(f"/universe/groups/{gid}")
        rows.append({
            "group_id":    data["group_id"],
            "category_id": data["category_id"],
            "name":        data["name"],
            "published":   data.get("published", True),
            "fetched_at":  now(),
        })

    upsert(conn, "groups", rows, "group_id")
    print(f"  ✓ {len(rows)} groups imported")


# ----------------------------------------------------------------
# TYPES
# ----------------------------------------------------------------

def import_types(conn):
    print("\n[3/7] Importing types (~40,000 items, this will take a while)...")
    type_ids = esi_get_all_pages("/universe/types/")

    rows = []
    skipped = 0

    for tid in tqdm(type_ids, desc="Types"):
        try:
            data = esi_get(f"/universe/types/{tid}")

            # Skip types with no group (malformed ESI data)
            if "group_id" not in data:
                skipped += 1
                continue

            rows.append({
                "type_id":          data["type_id"],
                "group_id":         data["group_id"],
                "name":             data.get("name", ""),
                "description":      data.get("description", ""),
                "volume":           data.get("volume"),
                "packaged_volume":  data.get("packaged_volume"),
                "published":        data.get("published", True),
                "fetched_at":       now(),
            })

            # Batch upsert every 500 rows to avoid memory buildup
            if len(rows) >= 500:
                upsert(conn, "types", rows, "type_id")
                rows = []

        except Exception as e:
            print(f"  [WARN] Failed type {tid}: {e}")
            skipped += 1
            continue

    # Final batch
    if rows:
        upsert(conn, "types", rows, "type_id")

    print(f"  ✓ Types imported ({skipped} skipped)")


# ----------------------------------------------------------------
# REGIONS
# ----------------------------------------------------------------

def import_regions(conn):
    print("\n[4/7] Importing regions...")
    region_ids = esi_get("/universe/regions/")

    region_rows = []
    constellation_ids = []

    for rid in tqdm(region_ids, desc="Regions"):
        data = esi_get(f"/universe/regions/{rid}")
        region_rows.append({
            "region_id":   data["region_id"],
            "name":        data.get("name", ""),
            "description": data.get("description", ""),
            "fetched_at":  now(),
        })
        constellation_ids.extend(data.get("constellations", []))

    upsert(conn, "regions", region_rows, "region_id")
    print(f"  ✓ {len(region_rows)} regions imported")

    return constellation_ids


# ----------------------------------------------------------------
# CONSTELLATIONS
# ----------------------------------------------------------------

def import_constellations(conn, constellation_ids):
    print("\n[5/7] Importing constellations...")

    constellation_rows = []
    system_ids = []

    for cid in tqdm(constellation_ids, desc="Constellations"):
        data = esi_get(f"/universe/constellations/{cid}")
        constellation_rows.append({
            "constellation_id": data["constellation_id"],
            "region_id":        data["region_id"],
            "name":             data.get("name", ""),
            "fetched_at":       now(),
        })
        system_ids.extend(data.get("systems", []))

    upsert(conn, "constellations", constellation_rows, "constellation_id")
    print(f"  ✓ {len(constellation_rows)} constellations imported")

    return system_ids


# ----------------------------------------------------------------
# SYSTEMS
# ----------------------------------------------------------------

def import_systems(conn, system_ids):
    print("\n[6/7] Importing systems...")

    system_rows = []
    station_ids = []

    for sid in tqdm(system_ids, desc="Systems"):
        data = esi_get(f"/universe/systems/{sid}")
        system_rows.append({
            "system_id":         data["system_id"],
            "constellation_id":  data["constellation_id"],
            "name":              data.get("name", ""),
            "security_status":   round(data.get("security_status", 0), 2),
            "fetched_at":        now(),
        })
        station_ids.extend(data.get("stations", []))

        # Batch upsert every 500
        if len(system_rows) >= 500:
            upsert(conn, "systems", system_rows, "system_id")
            system_rows = []

    if system_rows:
        upsert(conn, "systems", system_rows, "system_id")

    print(f"  ✓ Systems imported, {len(station_ids)} station IDs collected")
    return station_ids


# ----------------------------------------------------------------
# STATIONS
# ----------------------------------------------------------------

def import_stations(conn, station_ids):
    print("\n[7/7] Importing stations...")

    rows = []
    skipped = 0

    for sid in tqdm(station_ids, desc="Stations"):
        try:
            data = esi_get(f"/universe/stations/{sid}")
            rows.append({
                "station_id": data["station_id"],
                "system_id":  data["system_id"],
                "name":       data.get("name", ""),
                "type_id":    data.get("type_id"),
                "fetched_at": now(),
            })
        except Exception as e:
            print(f"  [WARN] Failed station {sid}: {e}")
            skipped += 1
            continue

    upsert(conn, "stations", rows, "station_id")
    print(f"  ✓ {len(rows)} stations imported ({skipped} skipped)")


# ----------------------------------------------------------------
# SEED MONITORED REGIONS
# ----------------------------------------------------------------

def seed_monitored_regions(conn):
    """Seed the 5 major trade hub regions for Phase 1."""
    print("\n[+] Seeding monitored regions (Phase 1 hubs)...")

    rows = [
        {"region_id": 10000002, "notes": "The Forge - Jita",      "is_active": True},
        {"region_id": 10000043, "notes": "Domain - Amarr",         "is_active": True},
        {"region_id": 10000030, "notes": "Heimatar - Rens",        "is_active": True},
        {"region_id": 10000032, "notes": "Sinq Laison - Dodixie",  "is_active": True},
        {"region_id": 10000042, "notes": "Metropolis - Hek",       "is_active": True},
    ]

    upsert(conn, "monitored_regions", rows, "region_id")
    print("  ✓ 5 hub regions marked as active")


# ----------------------------------------------------------------
# FULL UNIVERSE IMPORT ENTRYPOINT
# ----------------------------------------------------------------

def run_universe_import(conn):
    print("=" * 60)
    print("EVE Universe Import")
    print("=" * 60)

    import_categories(conn)
    import_groups(conn)
    import_types(conn)

    constellation_ids = import_regions(conn)
    system_ids = import_constellations(conn, constellation_ids)
    station_ids = import_systems(conn, system_ids)
    import_stations(conn, station_ids)

    seed_monitored_regions(conn)

    print("\n" + "=" * 60)
    print("✓ Universe import complete!")
    print("=" * 60)
