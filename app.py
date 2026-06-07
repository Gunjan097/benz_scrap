import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk

from fetcher import login, fetch_all
from exporter import export
from batch import read_credentials, run_school

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

_PREVIEW_COLS = ("grno", "studentname", "class", "fathername", "phone1", "dob", "address")
_COL_WIDTHS   = {"grno": 60, "studentname": 190, "class": 55,
                 "fathername": 165, "phone1": 110, "dob": 90, "address": 220}

_BATCH_COLS  = ("username", "status", "records", "photos", "note")
_BATCH_WIDTHS = {"username": 100, "status": 110, "records": 80, "photos": 80, "note": 320}

_STATUS_COLORS = {
    "Pending":  "gray",
    "Running":  "#2196f3",
    "Done":     "#4caf50",
    "Error":    "#e05252",
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Response Extractor")
        self.geometry("1050x700")
        self.minsize(750, 520)

        # single-school state
        self._all: list = []
        self._visible: list = []
        self._animating = False
        self._anim_val  = 0.0
        self._anim_dir  = 1

        # batch state
        self._cred_path   = tk.StringVar(value="")
        self._out_dir     = tk.StringVar(value="")
        self._credentials: list = []
        self._batch_items: dict = {}   # username → iid in treeview
        self._batch_running = False

        self._build_ui()

    # ═══════════════════════════════════════════════════════════════════════════
    # TOP-LEVEL LAYOUT
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkTabview(self, corner_radius=8)
        tabs.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        tabs.add("Single School")
        tabs.add("Batch Export")

        self._build_single(tabs.tab("Single School"))
        self._build_batch(tabs.tab("Batch Export"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SINGLE SCHOOL TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_single(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # login row
        lf = ctk.CTkFrame(parent, corner_radius=8)
        lf.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        lf.grid_columnconfigure(1, weight=1)
        lf.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(lf, text="Username:", width=84).grid(row=0, column=0, padx=(12,6), pady=10)
        self._s_user = tk.StringVar()
        ctk.CTkEntry(lf, textvariable=self._s_user,
                     placeholder_text="Enter username").grid(
            row=0, column=1, padx=6, pady=10, sticky="ew")

        ctk.CTkLabel(lf, text="Password:", width=76).grid(row=0, column=2, padx=(14,6), pady=10)
        self._s_pwd = tk.StringVar()
        pe = ctk.CTkEntry(lf, textvariable=self._s_pwd, show="*",
                          placeholder_text="Enter password")
        pe.grid(row=0, column=3, padx=6, pady=10, sticky="ew")
        pe.bind("<Return>", lambda _: self._s_fetch())

        ctk.CTkLabel(lf, text="Max Records:", width=90).grid(row=0, column=4, padx=(14,4), pady=10)
        self._s_limit = tk.StringVar(value="150")
        ctk.CTkEntry(lf, textvariable=self._s_limit, width=70,
                     placeholder_text="0=all").grid(row=0, column=5, padx=(0,8), pady=10)

        self._s_btn = ctk.CTkButton(lf, text="Login & Fetch", width=130, command=self._s_fetch)
        self._s_btn.grid(row=0, column=6, padx=(4,12), pady=10)

        # controls row
        cf = ctk.CTkFrame(parent, corner_radius=8)
        cf.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        cf.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(cf, text="Filter by Class:").grid(row=0, column=0, padx=(12,6), pady=8)
        self._s_cls = tk.StringVar(value="All")
        self._s_cls_menu = ctk.CTkOptionMenu(cf, variable=self._s_cls,
                                              values=["All"], command=self._s_filter, width=110)
        self._s_cls_menu.grid(row=0, column=1, padx=6, pady=8)
        self._s_count = ctk.CTkLabel(cf, text="", text_color="gray")
        self._s_count.grid(row=0, column=2, padx=12)

        self._s_export_btn = ctk.CTkButton(cf, text="Export to Excel", width=140,
                                            state="disabled", command=self._s_export)
        self._s_export_btn.grid(row=0, column=4, padx=(6,12), pady=8)

        # table
        tf = ctk.CTkFrame(parent, corner_radius=8)
        tf.grid(row=2, column=0, padx=8, pady=4, sticky="nsew")
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)

        ttk.Style().configure("Treeview", rowheight=24)
        ttk.Style().configure("Treeview.Heading", font=("", 10, "bold"))

        self._s_tree = ttk.Treeview(tf, columns=_PREVIEW_COLS, show="headings",
                                     selectmode="browse")
        for c in _PREVIEW_COLS:
            self._s_tree.heading(c, text=c.upper())
            self._s_tree.column(c, width=_COL_WIDTHS.get(c, 100), anchor="w",
                                minwidth=40, stretch=True)
        vsb = ttk.Scrollbar(tf, orient="vertical",   command=self._s_tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self._s_tree.xview)
        self._s_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._s_tree.grid(row=0, column=0, sticky="nsew", padx=(4,0), pady=(4,0))
        vsb.grid(row=0, column=1, sticky="ns",  pady=(4,0))
        hsb.grid(row=1, column=0, sticky="ew",  padx=(4,0))

        # progress + status
        self._s_progress = ctk.CTkProgressBar(parent, height=10, corner_radius=5)
        self._s_progress.set(0)
        self._s_progress.grid(row=3, column=0, padx=8, pady=(4,2), sticky="ew")
        self._s_progress.grid_remove()

        self._s_status = ctk.CTkLabel(parent, text="Enter credentials and click Login & Fetch.",
                                       anchor="w", text_color="gray", height=26)
        self._s_status.grid(row=4, column=0, padx=12, pady=(0,6), sticky="ew")

    # ═══════════════════════════════════════════════════════════════════════════
    # BATCH EXPORT TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_batch(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # top controls
        tf = ctk.CTkFrame(parent, corner_radius=8)
        tf.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        tf.grid_columnconfigure(1, weight=1)
        tf.grid_columnconfigure(3, weight=1)

        # credentials file
        ctk.CTkButton(tf, text="Import Credentials", width=150,
                      command=self._b_import).grid(row=0, column=0, padx=(12,8), pady=10)
        self._b_cred_lbl = ctk.CTkLabel(tf, text="No file selected",
                                         text_color="gray", anchor="w")
        self._b_cred_lbl.grid(row=0, column=1, padx=(0,16), pady=10, sticky="ew")

        # output folder
        ctk.CTkButton(tf, text="Output Folder", width=130,
                      command=self._b_outdir).grid(row=0, column=2, padx=8, pady=10)
        self._b_out_lbl = ctk.CTkLabel(tf, text="No folder selected",
                                        text_color="gray", anchor="w")
        self._b_out_lbl.grid(row=0, column=3, padx=(0,16), pady=10, sticky="ew")

        # limit + run button
        ctk.CTkLabel(tf, text="Max Records:", width=90).grid(row=0, column=4, padx=(8,4), pady=10)
        self._b_limit = tk.StringVar(value="0")
        ctk.CTkEntry(tf, textvariable=self._b_limit, width=70,
                     placeholder_text="0=all").grid(row=0, column=5, padx=(0,8), pady=10)

        self._b_run_btn = ctk.CTkButton(tf, text="Run All", width=110,
                                         fg_color="#2e7d32", hover_color="#1b5e20",
                                         command=self._b_run)
        self._b_run_btn.grid(row=0, column=6, padx=(4,12), pady=10)

        # batch progress table
        bf = ctk.CTkFrame(parent, corner_radius=8)
        bf.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        bf.grid_rowconfigure(0, weight=1)
        bf.grid_columnconfigure(0, weight=1)

        self._b_tree = ttk.Treeview(bf, columns=_BATCH_COLS, show="headings",
                                     selectmode="browse")
        headers = {"username": "School ID", "status": "Status",
                   "records": "Records", "photos": "Photos", "note": "Note / Path"}
        for c in _BATCH_COLS:
            self._b_tree.heading(c, text=headers[c])
            self._b_tree.column(c, width=_BATCH_WIDTHS[c], anchor="w",
                                minwidth=40, stretch=(c == "note"))
        # row tags for colour
        self._b_tree.tag_configure("running", foreground="#2196f3")
        self._b_tree.tag_configure("done",    foreground="#4caf50")
        self._b_tree.tag_configure("error",   foreground="#e05252")

        bvsb = ttk.Scrollbar(bf, orient="vertical",   command=self._b_tree.yview)
        bhsb = ttk.Scrollbar(bf, orient="horizontal", command=self._b_tree.xview)
        self._b_tree.configure(yscrollcommand=bvsb.set, xscrollcommand=bhsb.set)
        self._b_tree.grid(row=0, column=0, sticky="nsew", padx=(4,0), pady=(4,0))
        bvsb.grid(row=0, column=1, sticky="ns",  pady=(4,0))
        bhsb.grid(row=1, column=0, sticky="ew",  padx=(4,0))

        # progress + status
        self._b_progress = ctk.CTkProgressBar(parent, height=10, corner_radius=5)
        self._b_progress.set(0)
        self._b_progress.grid(row=2, column=0, padx=8, pady=(4,2), sticky="ew")
        self._b_progress.grid_remove()

        self._b_status = ctk.CTkLabel(parent,
                                       text="Import a credentials file and choose an output folder.",
                                       anchor="w", text_color="gray", height=26)
        self._b_status.grid(row=3, column=0, padx=12, pady=(0,6), sticky="ew")

    # ═══════════════════════════════════════════════════════════════════════════
    # SINGLE SCHOOL ACTIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def _s_fetch(self):
        u, p = self._s_user.get().strip(), self._s_pwd.get()
        if not u or not p:
            messagebox.showwarning("Missing", "Enter username and password.")
            return
        raw = self._s_limit.get().strip()
        try:
            limit = int(raw) if raw else 0
            if limit < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Max Records must be ≥ 0 (0 = fetch all).")
            return
        self._s_btn.configure(state="disabled", text="Logging in…")
        self._s_set_status("Logging in…")
        self._s_start_bounce()
        threading.Thread(target=self._s_worker, args=(u, p, limit), daemon=True).start()

    def _s_worker(self, u, p, limit):
        try:
            token, cls = login(u, p)
            self.after(0, self._s_btn.configure, {"text": "Fetching…"})
            label = f"up to {limit:,}" if limit else "all"
            self.after(0, self._s_set_status, f"Fetching {label} records…")
            records = fetch_all(token, cls, limit=limit,
                                progress_cb=lambda d, t: self.after(
                                    0, self._s_set_status, f"Fetching… {d:,} / {t:,}"))
            self.after(0, self._s_done, records, None)
        except Exception as e:
            self.after(0, self._s_done, None, str(e))

    def _s_done(self, records, err):
        self._s_btn.configure(state="normal", text="Login & Fetch")
        self._s_stop_progress()
        if err:
            self._s_set_status(f"Error: {err}", error=True)
            messagebox.showerror("Error", err)
            return
        self._all = records
        classes = sorted({str(r.get("class", "")) for r in records if r.get("class")})
        self._s_cls_menu.configure(values=["All"] + classes)
        self._s_cls.set("All")
        self._s_filter()
        self._s_export_btn.configure(state="normal")
        self._s_set_status(f"Fetched {len(records):,} records.")

    def _s_filter(self, _=None):
        sel = self._s_cls.get()
        self._visible = (self._all if sel == "All"
                         else [r for r in self._all if str(r.get("class", "")) == sel])
        self._s_tree.delete(*self._s_tree.get_children())
        for r in self._visible:
            self._s_tree.insert("", "end", values=tuple(
                str(r.get(c, "") or "") for c in _PREVIEW_COLS))
        self._s_count.configure(text=f"{len(self._visible):,} record(s)", text_color="white")

    def _s_export(self):
        if not self._visible:
            messagebox.showwarning("No data", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile="students.xlsx",
        )
        if not path:
            return
        self._s_export_btn.configure(state="disabled", text="Exporting…")
        self._s_set_status("Downloading photos and exporting…")
        self._s_start_bounce()
        threading.Thread(target=self._s_export_worker, args=(path,), daemon=True).start()

    def _s_export_worker(self, path):
        try:
            total = len(self._visible)

            def _cb(done, t):
                self.after(0, self._s_set_progress, done, t)
                self.after(0, self._s_set_status, f"Downloading photos… {done:,} / {t:,}")

            n = export(self._visible, path, progress_cb=_cb)
            msg = f"Exported {total:,} records  |  {n}/{total} photos saved  →  {path}"
            self.after(0, self._s_stop_progress)
            self.after(0, self._s_export_btn.configure,
                       {"state": "normal", "text": "Export to Excel"})
            self.after(0, self._s_set_status, msg)
            self.after(600, messagebox.showinfo, "Done", msg)
        except Exception as e:
            self.after(0, self._s_stop_progress)
            self.after(0, self._s_export_btn.configure,
                       {"state": "normal", "text": "Export to Excel"})
            self.after(0, self._s_set_status, f"Export error: {e}", True)
            self.after(0, messagebox.showerror, "Export Error", str(e))

    # ── Single school progress helpers ─────────────────────────────────────────

    def _s_start_bounce(self):
        self._animating = True
        self._anim_val, self._anim_dir = 0.0, 1
        self._s_progress.grid()
        self._s_tick()

    def _s_tick(self):
        if not self._animating:
            return
        self._anim_val += 0.025 * self._anim_dir
        if self._anim_val >= 1.0:
            self._anim_val, self._anim_dir = 1.0, -1
        elif self._anim_val <= 0.0:
            self._anim_val, self._anim_dir = 0.0, 1
        self._s_progress.set(self._anim_val)
        self.after(25, self._s_tick)

    def _s_set_progress(self, done, total):
        self._animating = False
        self._s_progress.grid()
        self._s_progress.set(done / total if total else 0)

    def _s_stop_progress(self):
        self._animating = False
        self._s_progress.set(1)
        self.after(400, self._s_progress.grid_remove)

    def _s_set_status(self, msg, error=False):
        self._s_status.configure(text=msg,
                                  text_color="#e05252" if error else "gray")

    # ═══════════════════════════════════════════════════════════════════════════
    # BATCH ACTIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def _b_import(self):
        path = filedialog.askopenfilename(
            title="Select credentials file",
            filetypes=[("Spreadsheet", "*.xlsx *.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            creds = read_credentials(path)
        except Exception as e:
            messagebox.showerror("Read Error", str(e))
            return
        if not creds:
            messagebox.showwarning("Empty", "No credentials found in the file.")
            return
        self._credentials = creds
        name = os.path.basename(path)
        self._b_cred_lbl.configure(
            text=f"{name}  ({len(creds)} school(s))", text_color="white")
        self._b_populate_table()
        self._b_status.configure(text=f"Loaded {len(creds)} school(s). Choose output folder and click Run All.",
                                   text_color="gray")

    def _b_outdir(self):
        d = filedialog.askdirectory(title="Select output folder")
        if not d:
            return
        self._out_dir.set(d)
        self._b_out_lbl.configure(text=d, text_color="white")

    def _b_populate_table(self):
        self._b_tree.delete(*self._b_tree.get_children())
        self._batch_items.clear()
        for u, _ in self._credentials:
            iid = self._b_tree.insert("", "end",
                                       values=(u, "Pending", "—", "—", ""))
            self._batch_items[u] = iid

    def _b_run(self):
        if not self._credentials:
            messagebox.showwarning("No credentials", "Import a credentials file first.")
            return
        out = self._out_dir.get().strip()
        if not out:
            messagebox.showwarning("No folder", "Choose an output folder first.")
            return
        raw = self._b_limit.get().strip()
        try:
            limit = int(raw) if raw else 0
            if limit < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Max Records must be ≥ 0.")
            return
        if self._batch_running:
            return

        self._batch_running = True
        self._b_run_btn.configure(state="disabled", text="Running…")
        self._b_populate_table()
        self._b_progress.set(0)
        self._b_progress.grid()
        self._b_status.configure(text="Starting batch…", text_color="gray")
        threading.Thread(target=self._b_worker,
                         args=(list(self._credentials), out, limit),
                         daemon=True).start()

    def _b_worker(self, creds, out_dir, limit):
        total = len(creds)
        for idx, (u, p) in enumerate(creds):
            self.after(0, self._b_set_row, u, "Running", "…", "—", "")

            def _prog(stage, done, t, _u=u):
                if stage == "fetch":
                    self.after(0, self._b_set_row, _u, "Fetching", f"{done}/{t}", "—", "")
                else:
                    self.after(0, self._b_set_row, _u, "Photos", "✓", f"{done}/{t}", "")

            try:
                result = run_school(u, p, out_dir, limit=limit, progress_cb=_prog)
                self.after(0, self._b_set_row, u, "Done ✓",
                           str(result["records"]),
                           str(result["photos"]),
                           result["path"], "done")
            except Exception as e:
                self.after(0, self._b_set_row, u, "Error ✗", "—", "—", str(e), "error")

            self.after(0, self._b_progress.set, (idx + 1) / total)
            self.after(0, self._b_status.configure,
                       {"text": f"Processing {idx + 1} / {total}…", "text_color": "gray"})

        done_count = sum(1 for u, _ in creds
                         if "Done" in (self._b_tree.item(self._batch_items[u], "values")[1]))
        msg = f"Batch complete — {done_count}/{total} schools exported to: {out_dir}"
        self.after(0, self._b_status.configure, {"text": msg, "text_color": "#4caf50"})
        self.after(0, self._b_run_btn.configure, {"state": "normal", "text": "Run All"})
        self._batch_running = False

    def _b_set_row(self, username, status, records, photos, note, tag="running"):
        iid = self._batch_items.get(username)
        if not iid:
            return
        self._b_tree.item(iid, values=(username, status, records, photos, note), tags=(tag,))
        self._b_tree.see(iid)
