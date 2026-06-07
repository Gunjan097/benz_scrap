import requests

SERVER       = "https://school.probietech.com/parse"
APP_ID       = "zjDlXWqwIv"
_BATCH_SIZE  = 1000   # max records per Parse request

_HEADERS = {
    "X-Parse-Application-Id": APP_ID,
    "Content-Type": "application/json",
}


def login(username: str, password: str) -> tuple:
    """Returns (session_token, class_name)."""
    resp = requests.post(
        f"{SERVER}/login",
        json={"username": username, "password": password},
        headers=_HEADERS,
        timeout=15,
    )
    data = _json(resp)
    if "error" in data:
        raise ValueError(data["error"])
    token = data.get("sessionToken", "")
    if not token:
        raise ValueError("No session token received.")
    school_id = _school_id(data)
    return token, f"Students_{school_id}"


def fetch_all(token: str, class_name: str,
              limit: int = 0,
              progress_cb=None) -> list:
    """
    Fetches records from the server.
    limit = max total records to return (0 = fetch everything).
    Internally paginates in batches of up to 1000.
    """
    hdrs = {**_HEADERS, "X-Parse-Session-Token": token}
    records, skip = [], 0

    while True:
        remaining = (limit - len(records)) if limit else _BATCH_SIZE
        batch_size = min(remaining, _BATCH_SIZE)

        resp = requests.get(
            f"{SERVER}/classes/{class_name}",
            headers=hdrs,
            params={"limit": batch_size, "skip": skip, "count": 1},
            timeout=30,
        )
        data = _json(resp)
        if "error" in data:
            raise ValueError(data["error"])

        batch = data.get("results", [])
        total = data.get("count", 0)
        records.extend(batch)

        if progress_cb:
            progress_cb(len(records), total if not limit else min(limit, total))

        # Stop when: hit the limit, got fewer than requested, or nothing left
        if (limit and len(records) >= limit) or len(batch) < batch_size:
            break
        skip += batch_size

    return records


def _school_id(data: dict) -> str:
    field = data.get("schoolId")
    if isinstance(field, list) and field:
        return field[0].get("objectId", "") if isinstance(field[0], dict) else ""
    if isinstance(field, dict):
        return field.get("objectId", "")
    return str(field or "")


def _json(resp) -> dict:
    text = resp.text.strip()
    if not text:
        raise ValueError(f"Empty response from server (HTTP {resp.status_code}).")
    try:
        return resp.json()
    except Exception:
        raise ValueError(f"Server error (HTTP {resp.status_code}): {text[:200]}")
