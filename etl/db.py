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
