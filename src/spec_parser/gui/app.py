"""Watt Spec Parser — customtkinter GUI.

Launch with:
    python -m spec_parser.gui.app
    python src/spec_parser/gui/app.py
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

# ── theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── column schemas (mirrors export/schemas.py) ────────────────────────────────
PIPE_COLS = ["PDF_File", "Service", "Pipe_Size_Range", "Thickness",
             "Insulation_Type", "Jacket_Required", "Notes"]
DUCT_COLS = ["PDF_File", "System", "Exposed", "Concealed", "Outdoor",
             "Insulation_Type", "Finish", "Notes"]
JACKET_COLS = ["PDF_File", "Location", "Application", "Jacket_Type",
               "Jacket_Material", "Rule_Text", "Confidence"]

PARSE_SCOPES = ["Full Scope", "HVAC Piping", "Plumbing Piping", "HVAC Duct", "Custom"]


# ─────────────────────────────────────────────────────────────────────────────
# Worker — runs in a background thread, posts to a queue
# ─────────────────────────────────────────────────────────────────────────────

def _run_parse(pdf_path: str, out_dir: str, scope: str, q: queue.Queue) -> None:
    """Background parse worker. Posts (kind, payload) tuples to *q*."""

    def post(kind: str, payload=None):
        q.put((kind, payload))

    try:
        post("log", f"Starting parse: {os.path.basename(pdf_path)}")
        post("log", f"Output directory: {out_dir}")
        os.makedirs(out_dir, exist_ok=True)

        # ── imports ──────────────────────────────────────────────────────────
        post("log", "Importing pipeline modules…")
        from spec_parser.extract.pdf_text import extract_pages
        from spec_parser.extract.table_extract import extract_schedule_tables
        from spec_parser.normalize.text_norm import normalize_text
        from spec_parser.detect.csi_sections import detect_source_sections
        from spec_parser.detect.section_classifier import classify_sections
        from spec_parser.parse.pipe_parser import parse_pipe_insulation
        from spec_parser.parse.duct_parser import parse_duct_insulation
        from spec_parser.parse.jacket_parser import parse_jacket_rules_from_pdf
        from spec_parser.export.excel import export_insulation_xlsx

        project_file = os.path.basename(pdf_path)

        # ── text extraction ───────────────────────────────────────────────────
        post("log", "Extracting pages with PyMuPDF…")
        pages_raw = extract_pages(pdf_path)
        post("log", f"  → {len(pages_raw)} pages extracted")

        post("log", "Normalizing text…")
        pages_norm = [
            type(p)(page_num=p.page_num, text=normalize_text(p.text))
            for p in pages_raw
        ]

        # ── section detection ─────────────────────────────────────────────────
        post("log", "Detecting CSI sections…")
        sections = detect_source_sections(project_file=project_file, pages=pages_norm)
        sections = classify_sections(sections)
        post("log", f"  → {len(sections)} sections detected")

        # ── table extraction ──────────────────────────────────────────────────
        post("log", "Extracting schedule tables with pdfplumber…")
        tables = extract_schedule_tables(pdf_path)
        post("log", f"  → {len(tables)} tables found")

        # ── pipe parsing ──────────────────────────────────────────────────────
        run_pipe = scope in ("Full Scope", "HVAC Piping", "Plumbing Piping", "Custom")
        pipe_rows: list[dict] = []
        if run_pipe:
            post("log", "Parsing pipe insulation…")
            pipe_rows = parse_pipe_insulation(tables, pdf_file=project_file)
            post("log", f"  → {len(pipe_rows)} pipe rows")
            # text fallback if empty
            if not pipe_rows:
                post("log", "  → Table parser yielded 0 rows, trying text fallback…")
                try:
                    from spec_parser.parse.text_fallback_parser import parse_pipe_insulation_text
                    pipe_rows = parse_pipe_insulation_text(pages_norm, pdf_file=project_file)
                    post("log", f"  → fallback: {len(pipe_rows)} pipe rows")
                except Exception as e:
                    post("log", f"  [warn] Text fallback failed: {e}")
            for r in pipe_rows:
                post("pipe_row", r)

        # ── duct parsing ──────────────────────────────────────────────────────
        run_duct = scope in ("Full Scope", "HVAC Duct", "Custom")
        duct_rows: list[dict] = []
        if run_duct:
            post("log", "Parsing duct insulation…")
            duct_rows = parse_duct_insulation(tables, pdf_file=project_file)
            post("log", f"  → {len(duct_rows)} duct rows")
            for r in duct_rows:
                post("duct_row", r)

        # ── jacket parsing ────────────────────────────────────────────────────
        post("log", "Parsing jacket rules…")
        jacket_rows = parse_jacket_rules_from_pdf(pdf_path, pdf_file=project_file)
        post("log", f"  → {len(jacket_rows)} jacket rules (prose scan)")
        # Also parse CSI outline-style jacket schedules (section 3.14 format)
        try:
            from spec_parser.parse.text_fallback_parser import parse_outline_jacket_schedule
            outline_jacket = parse_outline_jacket_schedule(
                [p.text for p in pages_norm],
                pdf_file=project_file,
            )
            if outline_jacket:
                post("log", f"  → {len(outline_jacket)} jacket rows (outline schedule)")
                jacket_rows.extend(outline_jacket)
        except Exception as e:
            post("log", f"  [warn] Jacket outline parse failed: {e}")
        post("log", f"  → {len(jacket_rows)} jacket rules total")
        for r in jacket_rows:
            post("jacket_row", r)

        # ── Excel export ──────────────────────────────────────────────────────
        post("log", "Writing Excel output…")
        xlsx_path = export_insulation_xlsx(
            sections=sections,
            pipe_rows=pipe_rows,
            duct_rows=duct_rows,
            jacket_rows=jacket_rows,
            out_dir=out_dir,
            filename="Insulation Report.xlsx",
        )
        post("log", f"  → {xlsx_path}")

        # ── summary ───────────────────────────────────────────────────────────
        total = len(pipe_rows) + len(duct_rows) + len(jacket_rows)
        post("summary", {
            "sections": len(sections),
            "pipe": len(pipe_rows),
            "duct": len(duct_rows),
            "jacket": len(jacket_rows),
            "total": total,
            "xlsx": xlsx_path,
            "out_dir": out_dir,
        })
        post("log", f"Done. {total} total rows extracted.")
        post("done", xlsx_path)

    except Exception as exc:
        import traceback
        post("log", f"ERROR: {exc}")
        post("log", traceback.format_exc())
        post("error", str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class SpecParserApp(TkinterDnD.DnDWrapper, ctk.CTk):
    def __init__(self):
        ctk.CTk.__init__(self)
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Watt Spec Parser")
        self.geometry("1300x820")
        self.minsize(1000, 660)

        self._pdf_path: str | None = None
        self._out_dir: str | None = None
        self._q: queue.Queue = queue.Queue()
        self._parsing = False

        self._build_ui()
        self._poll_queue()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        left = ctk.CTkFrame(self, width=380, corner_radius=0,
                            fg_color=("gray95", "gray10"))
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)

        row = 0

        # Title
        ctk.CTkLabel(left, text="Watt Spec Parser",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=row, column=0, padx=20, pady=(20, 4), sticky="w")
        row += 1

        ctk.CTkLabel(left, text="MEP insulation schedule extractor",
                     font=ctk.CTkFont(size=12), text_color="gray").grid(
            row=row, column=0, padx=20, pady=(0, 16), sticky="w")
        row += 1

        # ── PDF drop zone ─────────────────────────────────────────────────────
        ctk.CTkLabel(left, text="Input PDF", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=row, column=0, padx=20, pady=(0, 4), sticky="w")
        row += 1

        self._drop_frame = ctk.CTkFrame(left, height=90, corner_radius=10,
                                         border_width=2, border_color="#6c7ae0",
                                         fg_color="white")
        self._drop_frame.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
        self._drop_frame.grid_propagate(False)
        self._drop_frame.grid_columnconfigure(0, weight=1)
        self._drop_frame.grid_rowconfigure(0, weight=1)
        self._drop_frame.grid_rowconfigure(1, weight=1)

        self._drop_label = ctk.CTkLabel(
            self._drop_frame, text="Drag & Drop PDF Here\nor Click Browse",
            font=ctk.CTkFont(size=11), text_color="gray",
            wraplength=300)
        self._drop_label.grid(row=0, column=0, padx=10, pady=(10, 2))

        # Register drop zone for drag & drop
        self._drop_frame.drop_target_register(DND_FILES)
        self._drop_frame.dnd_bind("<<Drop>>", self._on_drop)
        self._drop_label.drop_target_register(DND_FILES)
        self._drop_label.dnd_bind("<<Drop>>", self._on_drop)

        ctk.CTkButton(self._drop_frame, text="Browse PDF…", width=130, height=28,
                      command=self._browse_pdf).grid(
            row=1, column=0, padx=10, pady=(0, 10))
        row += 1

        # ── Parse scope ───────────────────────────────────────────────────────
        ctk.CTkLabel(left, text="Parse Scope", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=row, column=0, padx=20, pady=(8, 4), sticky="w")
        row += 1

        self._scope_var = ctk.StringVar(value="Full Scope")
        scope_frame = ctk.CTkFrame(left, fg_color="transparent")
        scope_frame.grid(row=row, column=0, padx=20, sticky="ew")
        for i, scope in enumerate(PARSE_SCOPES):
            ctk.CTkRadioButton(scope_frame, text=scope, variable=self._scope_var,
                               value=scope).grid(
                row=i // 2, column=i % 2, padx=4, pady=2, sticky="w")
        row += 1

        # ── Parse button ──────────────────────────────────────────────────────
        self._parse_btn = ctk.CTkButton(
            left, text="Parse Spec", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#6c7ae0", hover_color="#5a68c8",
            command=self._start_parse)
        self._parse_btn.grid(row=row, column=0, padx=20, pady=(14, 8), sticky="ew")
        row += 1

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(left, mode="indeterminate")
        self._progress.grid(row=row, column=0, padx=20, pady=(0, 4), sticky="ew")
        self._progress.set(0)
        row += 1

        # ── Log box ───────────────────────────────────────────────────────────
        ctk.CTkLabel(left, text="Progress Log", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=row, column=0, padx=20, pady=(8, 2), sticky="w")
        row += 1

        self._log_box = ctk.CTkTextbox(left, height=180, font=ctk.CTkFont(
            family="Courier New", size=10), activate_scrollbars=True, wrap="word")
        self._log_box.grid(row=row, column=0, padx=20, pady=(0, 10), sticky="ew")
        self._log_box.configure(state="disabled")
        row += 1

        # ── Output chips ──────────────────────────────────────────────────────
        ctk.CTkLabel(left, text="Output Files", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=row, column=0, padx=20, pady=(4, 4), sticky="w")
        row += 1

        self._chip_frame = ctk.CTkFrame(left, fg_color="transparent")
        self._chip_frame.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
        self._chip_frame.grid_columnconfigure((0, 1), weight=1)
        row += 1

        # Placeholder chips (hidden until parse done)
        self._chips: list[ctk.CTkButton] = []
        self._xlsx_path: str | None = None

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=row, column=0, padx=20, pady=(0, 20), sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self._open_folder_btn = ctk.CTkButton(
            btn_row, text="Open Output Folder", state="disabled",
            command=self._open_folder)
        self._open_folder_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._open_xlsx_btn = ctk.CTkButton(
            btn_row, text="Open Report", state="disabled",
            command=self._open_xlsx)
        self._open_xlsx_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _build_right_panel(self):
        right = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray98", "gray15"))
        right.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Preview", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        # ── Tab view ──────────────────────────────────────────────────────────
        tab_view = ctk.CTkTabview(right)
        tab_view.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="nsew")

        self._pipe_tab = tab_view.add("Pipe Insulation")
        self._duct_tab = tab_view.add("Duct Insulation")
        self._jacket_tab = tab_view.add("Jacket Rules")

        for tab, cols in [
            (self._pipe_tab, PIPE_COLS),
            (self._duct_tab, DUCT_COLS),
            (self._jacket_tab, JACKET_COLS),
        ]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self._pipe_tree = self._make_tree(self._pipe_tab, PIPE_COLS)
        self._duct_tree = self._make_tree(self._duct_tab, DUCT_COLS)
        self._jacket_tree = self._make_tree(self._jacket_tab, JACKET_COLS)

        # ── Summary section ───────────────────────────────────────────────────
        summary_frame = ctk.CTkFrame(right, corner_radius=8)
        summary_frame.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(summary_frame, text="Parse Summary",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=4, padx=16, pady=(10, 4), sticky="w")

        self._sum_sections = self._make_stat(summary_frame, "Sections", 1, 0)
        self._sum_pipe = self._make_stat(summary_frame, "Pipe Rows", 1, 1)
        self._sum_duct = self._make_stat(summary_frame, "Duct Rows", 1, 2)
        self._sum_jacket = self._make_stat(summary_frame, "Jacket Rules", 1, 3)

        self._review_label = ctk.CTkLabel(
            summary_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._review_label.grid(row=2, column=0, columnspan=4, padx=16, pady=(4, 10), sticky="w")

    def _make_tree(self, parent, columns: list[str]) -> ttk.Treeview:
        frame = tk.Frame(parent, bg="#f5f5f5")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff",
                        foreground="#1a1a1a", rowheight=22,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#e8eaf6", foreground="#3c3f99",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#c5cae9")])

        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            selectmode="browse")
        for col in columns:
            width = 140 if col in ("Rule_Text", "Notes") else 90
            tree.heading(col, text=col.replace("_", " "))
            tree.column(col, width=width, minwidth=50, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        return tree

    def _make_stat(self, parent, label: str, row: int, col: int) -> ctk.CTkLabel:
        f = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"), corner_radius=6)
        f.grid(row=row, column=col, padx=8, pady=(4, 8), sticky="ew")
        ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10), text_color="gray").pack(pady=(4, 0))
        val = ctk.CTkLabel(f, text="—", font=ctk.CTkFont(size=20, weight="bold"))
        val.pack(pady=(0, 4))
        return val

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_drop(self, event):
        path = event.data.strip()
        # tkinterdnd2 on Windows wraps paths with spaces in curly braces
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]
        # If multiple files dropped, take the first
        if not path.lower().endswith(".pdf"):
            self._log("Drop ignored: not a PDF file.")
            return
        self._pdf_path = path
        self._drop_label.configure(text=os.path.basename(path), text_color="#3c3f99")

    def _browse_pdf(self):
        path = filedialog.askopenfilename(
            title="Select PDF spec",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self._pdf_path = path
            name = os.path.basename(path)
            self._drop_label.configure(text=name, text_color="#3c3f99")

    def _start_parse(self):
        if self._parsing:
            return
        if not self._pdf_path:
            self._log("Please select a PDF first.")
            return

        # Determine output directory next to the PDF
        pdf_dir = os.path.dirname(self._pdf_path)
        pdf_stem = os.path.splitext(os.path.basename(self._pdf_path))[0]
        self._out_dir = os.path.join(pdf_dir, "output", pdf_stem)

        # Clear state
        self._clear_tables()
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._clear_chips()
        self._sum_sections.configure(text="—")
        self._sum_pipe.configure(text="—")
        self._sum_duct.configure(text="—")
        self._sum_jacket.configure(text="—")
        self._review_label.configure(text="")
        self._open_folder_btn.configure(state="disabled")
        self._open_xlsx_btn.configure(state="disabled")

        self._parsing = True
        self._parse_btn.configure(state="disabled", text="Parsing…")
        self._progress.start()

        threading.Thread(
            target=_run_parse,
            args=(self._pdf_path, self._out_dir,
                  self._scope_var.get(), self._q),
            daemon=True,
        ).start()

    def _open_folder(self):
        if self._out_dir and os.path.isdir(self._out_dir):
            if sys.platform == "win32":
                os.startfile(self._out_dir)
            else:
                subprocess.Popen(["xdg-open", self._out_dir])

    def _open_xlsx(self):
        if self._xlsx_path and os.path.isfile(self._xlsx_path):
            if sys.platform == "win32":
                os.startfile(self._xlsx_path)
            else:
                subprocess.Popen(["xdg-open", self._xlsx_path])

    # ── Queue polling ─────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                self._handle_message(kind, payload)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _handle_message(self, kind: str, payload):
        if kind == "log":
            self._log(str(payload))
        elif kind == "pipe_row":
            self._append_row(self._pipe_tree, PIPE_COLS, payload)
        elif kind == "duct_row":
            self._append_row(self._duct_tree, DUCT_COLS, payload)
        elif kind == "jacket_row":
            self._append_row(self._jacket_tree, JACKET_COLS, payload)
        elif kind == "summary":
            self._on_summary(payload)
        elif kind == "done":
            self._on_done(payload)
        elif kind == "error":
            self._on_error(payload)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _append_row(self, tree: ttk.Treeview, cols: list[str], row: dict):
        values = [str(row.get(c, "")) for c in cols]
        tree.insert("", "end", values=values)

    def _clear_tables(self):
        for tree in (self._pipe_tree, self._duct_tree, self._jacket_tree):
            for item in tree.get_children():
                tree.delete(item)

    def _clear_chips(self):
        for w in self._chips:
            w.destroy()
        self._chips.clear()

    def _on_summary(self, summary: dict):
        self._sum_sections.configure(text=str(summary.get("sections", "—")))
        self._sum_pipe.configure(text=str(summary.get("pipe", "—")))
        self._sum_duct.configure(text=str(summary.get("duct", "—")))
        self._sum_jacket.configure(text=str(summary.get("jacket", "—")))

        total = summary.get("total", 0)
        flags = []
        if summary.get("pipe", 0) == 0:
            flags.append("No pipe rows detected")
        if summary.get("duct", 0) == 0:
            flags.append("No duct rows detected")
        if summary.get("jacket", 0) == 0:
            flags.append("No jacket rules detected")

        if flags:
            self._review_label.configure(
                text="Review flags: " + " · ".join(flags), text_color="#c0392b")
        else:
            self._review_label.configure(
                text=f"All checks passed — {total} rows extracted.", text_color="#27ae60")

        # Excel chip
        xlsx = summary.get("xlsx")
        if xlsx and os.path.isfile(xlsx):
            self._xlsx_path = xlsx
            chip = ctk.CTkButton(
                self._chip_frame,
                text="Insulation Report.xlsx",
                height=30, font=ctk.CTkFont(size=10),
                fg_color="#e8eaf6", text_color="#3c3f99",
                hover_color="#c5cae9", border_width=1, border_color="#9fa8da",
                command=self._open_xlsx)
            chip.grid(row=0, column=0, columnspan=2, padx=2, pady=2, sticky="ew")
            self._chips.append(chip)

    def _on_done(self, xlsx_path: str):
        self._parsing = False
        self._parse_btn.configure(state="normal", text="Parse Spec")
        self._progress.stop()
        self._progress.set(1)
        self._open_folder_btn.configure(state="normal")
        self._open_xlsx_btn.configure(state="normal")
        self._log("✓ Parse complete.")

    def _on_error(self, msg: str):
        self._parsing = False
        self._parse_btn.configure(state="normal", text="Parse Spec")
        self._progress.stop()
        self._progress.set(0)
        self._log(f"✗ Error: {msg}")


# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = SpecParserApp()
    app.mainloop()


if __name__ == "__main__":
    main()
