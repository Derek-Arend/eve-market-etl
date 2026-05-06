import os
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

ESI_BASE_URL = os.environ.get("ESI_BASE_URL", "https://esi.evetech.net/latest")
ESI_USER_AGENT = os.environ.get("ESI_USER_AGENT", "eve-market-etl/1.0")

# ESI rate limit: 150 requests per second (we stay well under)
REQUEST_DELAY = 0.1  # 100ms between requests = ~10 req/sec, safe margin


session = requests.Session()
session.headers.update({
    "User-Agent": ESI_USER_AGENT,
    "Accept": "application/json",
})


@retry(
    retry=retry_if_exception_type((requests.exceptions.ConnectionError,
                                   requests.exceptions.Timeout)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
)
def esi_get(path: str, params: dict = None) -> any:
    """
    Make a GET request to ESI. Handles:
    - Rate limiting (built-in delay)
    - 420/503/504 backoff
    - Automatic retry on connection errors
    """
    url = f"{ESI_BASE_URL}{path}"
    time.sleep(REQUEST_DELAY)

    response = session.get(url, params=params, timeout=10)

    if response.status_code == 420:
        # ESI rate limit hit - back off
        retry_after = int(response.headers.get("X-ESI-Error-Limit-Reset", 60))
        print(f"  [ESI] Rate limited. Waiting {retry_after}s...")
        time.sleep(retry_after)
        return esi_get(path, params)

    if response.status_code in (503, 504):
        print(f"  [ESI] Server error {response.status_code}, retrying...")
        time.sleep(5)
        return esi_get(path, params)

    response.raise_for_status()
    return response.json()


def esi_get_all_pages(path: str, params: dict = None) -> list:
    """
    Fetch all pages from a paginated ESI endpoint.
    ESI uses X-Pages header to indicate total page count.
    """
    params = params or {}
    params["page"] = 1

    response = session.get(f"{ESI_BASE_URL}{path}", params=params, timeout=10)
    response.raise_for_status()

    total_pages = int(response.headers.get("X-Pages", 1))
    results = response.json()

    for page in range(2, total_pages + 1):
        params["page"] = page
        results.extend(esi_get(path, params))

    return results
