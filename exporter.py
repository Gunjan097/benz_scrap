import os
import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

_COLS = [
    "objectId", "qr", "photono", "grno", "class", "dob",
    "studentname", "fathername", "mothername", "address",
    "phone1", "phone2", "createdAt", "updatedAt", "photo_path",
]
_FILL  = PatternFill("solid", fgColor="1F4E79")
_FONT  = Font(bold=True, color="FFFFFF")
_ALIGN = Alignment(horizontal="center", vertical="center")


def export(records: list, xlsx_path: str, progress_cb=None) -> int:
    """
    Writes one 'Students' sheet to xlsx_path.
    Downloads photos into a photos/ subfolder next to the Excel file.
    The photo_path column holds the relative path: photos/<filename>
    Returns number of photos downloaded.
    """
    photo_dir = os.path.join(os.path.dirname(os.path.abspath(xlsx_path)), "photos")
    os.makedirs(photo_dir, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"

    for ci, col in enumerate(_COLS, 1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.fill, cell.font, cell.alignment = _FILL, _FONT, _ALIGN

    downloaded = 0
    total = len(records)

    for ri, r in enumerate(records, 2):
        photo     = r.get("photo") or {}
        url       = photo.get("url", "")
        name      = photo.get("name", "")
        local     = _download(url, name, photo_dir) if url else ""
        if local:
            downloaded += 1

        rel_path = os.path.join("photos", os.path.basename(local)) if local else ""

        for ci, col in enumerate(_COLS, 1):
            value = rel_path if col == "photo_path" else str(r.get(col, "") or "")
            ws.cell(row=ri, column=ci, value=value)

        if progress_cb:
            progress_cb(ri - 1, total)

    _autosize(ws)
    wb.save(xlsx_path)
    return downloaded


def _download(url: str, name: str, photo_dir: str) -> str:
    try:
        filename = name or url.split("/")[-1]
        dest = os.path.join(photo_dir, filename)
        if os.path.exists(dest):
            return dest
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            with open(dest, "wb") as f:
                f.write(resp.content)
            return dest
    except Exception:
        pass
    return ""


def _autosize(ws):
    for ci in range(1, ws.max_column + 1):
        max_len = 0
        for ri in range(1, ws.max_row + 1):
            val = ws.cell(ri, ci).value or ""
            max_len = max(max_len, len(str(val)))
        ws.column_dimensions[get_column_letter(ci)].width = min(max_len + 2, 45)
