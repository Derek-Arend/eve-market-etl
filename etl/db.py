import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def get_client() -> Client:
    """Return a Supabase HTTP API client."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def upsert(client: Client, table: str, rows: list[dict]):
    """
    Generic upsert helper using Supabase HTTP API.
    Supabase handles conflict resolution automatically on upsert.
    """
    if not rows:
        return

    # Supabase upsert handles ON CONFLICT automatically
    client.table(table).upsert(rows).execute()


def fetch_all(client, table: str, filters: dict = None) -> list[dict]:
    """
    Fetch all rows from a table, handling Supabase's 1000 row limit
    via pagination. Use this instead of .execute() for large tables.
    """
    page_size = 1000
    offset = 0
    results = []

    while True:
        query = client.table(table).select("*")
        
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        
        rows = query.range(offset, offset + page_size - 1).execute().data
        
        if not rows:
            break
            
        results.extend(rows)
        
        if len(rows) < page_size:
            break
            
        offset += page_size

    return results