import csv
import os

import openpyxl

from fetcher import login, fetch_all
from exporter import export


def read_credentials(filepath: str) -> list:
    """
    Reads a .xlsx or .csv file with username/password columns.
    Returns list of (username, password) tuples. Skips header row automatically.
    """
    ext = os.path.splitext(filepath)[1].lower()
    return _read_csv(filepath) if ext == ".csv" else _read_xlsx(filepath)


def _read_xlsx(filepath: str) -> list:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    creds = []
    for row in ws.iter_rows(values_only=True):
        if not row or row[0] is None:
            continue
        u = str(row[0]).strip()
        p = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        if u.lower() in ("username", "user", "id", "userid", "user_id"):
            continue
        if u and p:
            creds.append((u, p))
    wb.close()
    return creds


def _read_csv(filepath: str) -> list:
    creds = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            u = row[0].strip()
            p = row[1].strip() if len(row) > 1 else ""
            if u.lower() in ("username", "user", "id", "userid", "user_id"):
                continue
            if u and p:
                creds.append((u, p))
    return creds


def run_school(username: str, password: str, output_dir: str,
               limit: int = 0, progress_cb=None) -> dict:
    """
    Full pipeline for one school: login → fetch → export.
    progress_cb(stage, done, total) where stage is 'fetch' or 'photo'.
    Returns {"records": int, "photos": int, "path": str}.
    Raises on any failure.
    """
    school_dir = os.path.join(output_dir, str(username))
    os.makedirs(school_dir, exist_ok=True)
    xlsx_path = os.path.join(school_dir, "students.xlsx")

    token, class_name = login(username, password)

    records = fetch_all(
        token, class_name, limit=limit,
        progress_cb=lambda d, t: progress_cb("fetch", d, t) if progress_cb else None,
    )

    photos = export(
        records, xlsx_path,
        progress_cb=lambda d, t: progress_cb("photo", d, t) if progress_cb else None,
    )

    return {"records": len(records), "photos": photos, "path": xlsx_path}
