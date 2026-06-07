import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from fetcher import login, fetch_all
from exporter import export

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

_COLS = ("grno", "studentname", "class", "fathername", "phone1", "dob", "address")
_WIDTHS = {"grno": 60, "studentname": 190, "class": 55,
           "fathername": 165, "phone1": 110, "dob": 90, "address": 220}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Response Extractor")
        self.geometry("1000x640")
        self.minsize(700, 480)
        self._all: list = []
        self._visible: list = []
        self._animating = False
        self._anim_val = 0.0
        self._anim_dir = 1
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # table expands

        # ── Login row ──────────────────────────────────────────────────────
        login_frame = ctk.CTkFrame(self, corner_radius=8)
        login_frame.grid(row=0, column=0, padx=12, pady=(12, 5), sticky="ew")
        login_frame.grid_columnconfigure(1, weight=1)
        login_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(login_frame, text="Username:", width=84).grid(
            row=0, column=0, padx=(12, 6), pady=12)
        self._user = tk.StringVar()
        ctk.CTkEntry(login_frame, textvariable=self._user,
                     placeholder_text="Enter username").grid(
            row=0, column=1, padx=6, pady=12, sticky="ew")

        ctk.CTkLabel(login_frame, text="Password:", width=76).grid(
            row=0, column=2, padx=(14, 6), pady=12)
        self._pwd = tk.StringVar()
        pwd_entry = ctk.CTkEntry(login_frame, textvariable=self._pwd,
                                  show="*", placeholder_text="Enter password")
        pwd_entry.grid(row=0, column=3, padx=6, pady=12, sticky="ew")
        pwd_entry.bind("<Return>", lambda _: self._fetch())

        ctk.CTkLabel(login_frame, text="Max Records:", width=90).grid(
            row=0, column=4, padx=(14, 4), pady=12)
        self._limit = tk.StringVar(value="150")
        ctk.CTkEntry(login_frame, textvariable=self._limit, width=70,
                     placeholder_text="0=all").grid(
            row=0, column=5, padx=(0, 8), pady=12)

        self._btn = ctk.CTkButton(login_frame, text="Login & Fetch",
                                   width=130, command=self._fetch)
        self._btn.grid(row=0, column=6, padx=(4, 12), pady=12)

        # ── Controls row ───────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, corner_radius=8)
        ctrl.grid(row=1, column=0, padx=12, pady=5, sticky="ew")
        ctrl.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(ctrl, text="Filter by Class:").grid(
            row=0, column=0, padx=(12, 6), pady=8)
        self._cls_var = tk.StringVar(value="All")
        self._cls_menu = ctk.CTkOptionMenu(ctrl, variable=self._cls_var,
                                            values=["All"], command=self._filter,
                                            width=110)
        self._cls_menu.grid(row=0, column=1, padx=6, pady=8)

        self._count = ctk.CTkLabel(ctrl, text="", text_color="gray")
        self._count.grid(row=0, column=2, padx=12)

        self._export_btn = ctk.CTkButton(ctrl, text="Export to Excel",
                                          width=140, state="disabled",
                                          command=self._export)
        self._export_btn.grid(row=0, column=4, padx=(6, 12), pady=8)

        # ── Table ──────────────────────────────────────────────────────────
        tbl = ctk.CTkFrame(self, corner_radius=8)
        tbl.grid(row=2, column=0, padx=12, pady=5, sticky="nsew")
        tbl.grid_rowconfigure(0, weight=1)
        tbl.grid_columnconfigure(0, weight=1)

        ttk.Style().configure("Treeview", rowheight=24)
        ttk.Style().configure("Treeview.Heading", font=("", 10, "bold"))

        self._tree = ttk.Treeview(tbl, columns=_COLS, show="headings",
                                   selectmode="browse")
        for c in _COLS:
            self._tree.heading(c, text=c.upper())
            self._tree.column(c, width=_WIDTHS.get(c, 100), anchor="w",
                              minwidth=40, stretch=True)
        vsb = ttk.Scrollbar(tbl, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tbl, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=(4, 0))
        vsb.grid(row=0, column=1, sticky="ns",  pady=(4, 0))
        hsb.grid(row=1, column=0, sticky="ew",  padx=(4, 0))

        # ── Progress bar ───────────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(self, height=10, corner_radius=5)
        self._progress.set(0)
        self._progress.grid(row=3, column=0, padx=12, pady=(4, 2), sticky="ew")
        self._progress.grid_remove()          # hidden until a task starts

        # ── Status bar ─────────────────────────────────────────────────────
        self._status = ctk.CTkLabel(self, text="Enter credentials and click Login & Fetch.",
                                     anchor="w", text_color="gray", height=26)
        self._status.grid(row=4, column=0, padx=14, pady=(0, 8), sticky="ew")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _fetch(self):
        u, p = self._user.get().strip(), self._pwd.get()
        if not u or not p:
            messagebox.showwarning("Missing", "Enter username and password.")
            return
        raw = self._limit.get().strip()
        try:
            limit = int(raw) if raw else 0
            if limit < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Max Records must be a positive number (or 0 for all).")
            return
        self._btn.configure(state="disabled", text="Logging in…")
        self._set_status("Logging in…")
        self._start_bounce()
        threading.Thread(target=self._worker, args=(u, p, limit), daemon=True).start()

    def _worker(self, u, p, limit):
        try:
            token, cls = login(u, p)
            label = f"up to {limit:,}" if limit else "all"
            self.after(0, self._set_status, f"Fetching {label} records…")
            self.after(0, self._btn.configure, {"text": "Fetching…"})
            records = fetch_all(
                token, cls, limit=limit,
                progress_cb=lambda done, total: self.after(
                    0, self._set_status, f"Fetching… {done:,} / {total:,}"),
            )
            self.after(0, self._done, records, None)
        except Exception as e:
            self.after(0, self._done, None, str(e))

    def _done(self, records, err):
        self._btn.configure(state="normal", text="Login & Fetch")
        self._stop_progress()
        if err:
            self._set_status(f"Error: {err}", error=True)
            messagebox.showerror("Error", err)
            return
        self._all = records
        classes = sorted({str(r.get("class", "")) for r in records if r.get("class")})
        self._cls_menu.configure(values=["All"] + classes)
        self._cls_var.set("All")
        self._filter()
        self._export_btn.configure(state="normal")
        self._set_status(f"Fetched {len(records):,} records.")

    def _filter(self, _=None):
        sel = self._cls_var.get()
        self._visible = (self._all if sel == "All"
                         else [r for r in self._all if str(r.get("class", "")) == sel])
        self._tree.delete(*self._tree.get_children())
        for r in self._visible:
            self._tree.insert("", "end", values=tuple(
                str(r.get(c, "") or "") for c in _COLS))
        self._count.configure(
            text=f"{len(self._visible):,} record(s)", text_color="white")

    def _export(self):
        if not self._visible:
            messagebox.showwarning("No data", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile="student_data.xlsx",
        )
        if not path:
            return
        self._export_btn.configure(state="disabled", text="Exporting…")
        self._set_status("Exporting and downloading photos…")
        self._start_bounce()
        threading.Thread(target=self._export_worker,
                         args=(path,), daemon=True).start()

    def _export_worker(self, path):
        try:
            total = len(self._visible)

            def _on_photo_progress(done, t):
                self.after(0, self._set_progress, done, t)
                self.after(0, self._set_status,
                           f"Downloading photos… {done:,} / {t:,}")

            downloaded = export(self._visible, path, progress_cb=_on_photo_progress)
            msg = (f"Exported {total:,} records  |  "
                   f"{downloaded} / {total} photos saved  →  {path}")
            self.after(0, self._stop_progress)
            self.after(0, self._export_btn.configure,
                       {"state": "normal", "text": "Export to Excel"})
            self.after(0, self._set_status, msg)
            self.after(600, messagebox.showinfo, "Done", msg)
        except Exception as e:
            self.after(0, self._stop_progress)
            self.after(0, self._export_btn.configure,
                       {"state": "normal", "text": "Export to Excel"})
            self.after(0, self._set_status, f"Export error: {e}", True)
            self.after(0, messagebox.showerror, "Export Error", str(e))

    # ── Progress helpers ──────────────────────────────────────────────────────

    def _start_bounce(self):
        """Show progress bar with a bouncing animation (indeterminate)."""
        self._animating = True
        self._anim_val = 0.0
        self._anim_dir = 1
        self._progress.grid()
        self._tick()

    def _tick(self):
        if not self._animating:
            return
        self._anim_val += 0.025 * self._anim_dir
        if self._anim_val >= 1.0:
            self._anim_val = 1.0
            self._anim_dir = -1
        elif self._anim_val <= 0.0:
            self._anim_val = 0.0
            self._anim_dir = 1
        self._progress.set(self._anim_val)
        self.after(25, self._tick)

    def _set_progress(self, done: int, total: int):
        """Switch to determinate mode and update fill."""
        self._animating = False
        self._progress.grid()
        self._progress.set(done / total if total else 0)

    def _stop_progress(self):
        self._animating = False
        self._progress.set(1)
        self.after(400, self._progress.grid_remove)

    def _set_status(self, msg, error=False):
        self._status.configure(text=msg,
                                text_color="#e05252" if error else "gray")
