"""
DrawMySTEP — Windows GUI for STEP/DXF conversion tools.

Tab 1: STEP → DXF/SVG/PDF  (step_laser backend)
Tab 2: DXF Rotator          (dxf_min_bound backend)

Run:
    python DrawMySTEP.py
"""

import queue
import sys
import threading
import traceback
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from step_laser.main import process_step_file
from dxf_min_bound.main import process_dxf


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------

class QueueWriter:
    """Redirects write() calls to a queue for thread-safe GUI log updates."""

    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, text: str):
        if text and text.strip():
            self.q.put(("log", text.rstrip()))

    def flush(self):
        pass


# ---------------------------------------------------------------------------

class ConverterTab(ctk.CTkFrame):
    """
    Reusable tab widget shared by both tools.

    process_fn     – callable(path: Path) -> None  (runs in a worker thread)
    glob_pattern   – e.g. "*.step"
    exclude_suffix – skip files whose stem ends with this (e.g. "_converted")
    file_types     – filedialog filetypes list
    button_label   – text on the action button
    """

    def __init__(self, parent, *, process_fn, glob_pattern,
                 exclude_suffix, file_types, button_label):
        super().__init__(parent, fg_color="transparent")
        self.pack(fill="both", expand=True, padx=10, pady=10)

        self.process_fn = process_fn
        self.glob_pattern = glob_pattern
        self.exclude_suffix = exclude_suffix
        self.file_types = file_types
        self._log_queue: queue.Queue = queue.Queue()

        # --- Path row -------------------------------------------------------
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(path_frame, text="Input:", width=50, anchor="w").pack(side="left")

        self.path_var = ctk.StringVar()
        self.path_entry = ctk.CTkEntry(
            path_frame,
            textvariable=self.path_var,
            placeholder_text="Select a file or folder…",
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(4, 4))

        ctk.CTkButton(
            path_frame, text="File…", width=70, command=self._browse_file
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            path_frame, text="Folder…", width=80, command=self._browse_folder
        ).pack(side="left")

        # --- Action button --------------------------------------------------
        self.run_btn = ctk.CTkButton(
            self, text=button_label, height=38, command=self._run
        )
        self.run_btn.pack(fill="x", pady=(0, 8))

        # --- Log ------------------------------------------------------------
        ctk.CTkLabel(self, text="Log:", anchor="w").pack(fill="x")
        self.log_box = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True)

        # --- Status bar -----------------------------------------------------
        self.status_var = ctk.StringVar(value="Ready.")
        ctk.CTkLabel(
            self, textvariable=self.status_var, anchor="w"
        ).pack(fill="x", pady=(4, 0))

    # -----------------------------------------------------------------------

    def _browse_file(self):
        path = filedialog.askopenfilename(filetypes=self.file_types)
        if path:
            self.path_var.set(path)

    def _browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)

    # -----------------------------------------------------------------------

    def _run(self):
        raw = self.path_var.get().strip()
        if not raw:
            self.status_var.set("No file or folder selected.")
            return

        p = Path(raw)
        if not p.exists():
            self.status_var.set(f"Path not found: {p}")
            return

        if p.is_file():
            paths = [p]
        else:
            paths = sorted(
                (
                    f for f in p.glob(self.glob_pattern)
                    if self.exclude_suffix is None
                    or not f.stem.endswith(self.exclude_suffix)
                ),
                key=lambda f: f.name.lower(),
            )

        if not paths:
            self._clear_log()
            self._append_log(f"No {self.glob_pattern} files found in: {p}")
            self.status_var.set("No files to process.")
            return

        self._clear_log()
        self._set_busy(True)
        self.status_var.set(f"Processing {len(paths)} file(s)…")

        thread = threading.Thread(
            target=self._worker, args=(paths,), daemon=True
        )
        thread.start()
        self.after(100, self._poll_queue)

    # -----------------------------------------------------------------------

    def _worker(self, paths: list):
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        writer = QueueWriter(self._log_queue)
        sys.stdout = writer
        sys.stderr = writer

        success = 0
        total = len(paths)
        try:
            for i, p in enumerate(paths, 1):
                self._log_queue.put(("log", f"[{i}/{total}] Processing: {p.name}"))
                try:
                    self.process_fn(p)
                    success += 1
                    self._log_queue.put(("log", "  Done.\n"))
                except Exception as e:
                    self._log_queue.put(("log", f"  ERROR: {e}"))
                    self._log_queue.put(("log", traceback.format_exc()))
                    self._log_queue.put(("log", ""))
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

        self._log_queue.put(("done", success, total))

    # -----------------------------------------------------------------------

    def _poll_queue(self):
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item[0] == "log":
                    self._append_log(item[1])
                elif item[0] == "done":
                    _, success, total = item
                    self._set_busy(False)
                    if success == total:
                        self.status_var.set(f"✓ {success}/{total} completed.")
                    else:
                        self.status_var.set(
                            f"⚠  {success}/{total} completed — see log for errors."
                        )
                    return
        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    # -----------------------------------------------------------------------

    def _append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_busy(self, busy: bool):
        self.run_btn.configure(state="disabled" if busy else "normal")


# ---------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DrawMySTEP")
        self.geometry("720x560")
        self.minsize(600, 450)

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=12)

        tabs.add("STEP → DXF / SVG / PDF")
        tabs.add("DXF Rotator")

        ConverterTab(
            tabs.tab("STEP → DXF / SVG / PDF"),
            process_fn=process_step_file,
            glob_pattern="*.step",
            exclude_suffix=None,
            file_types=[("STEP files", "*.step"), ("All files", "*.*")],
            button_label="Convert All  →  DXF / SVG / PDF",
        )

        ConverterTab(
            tabs.tab("DXF Rotator"),
            process_fn=process_dxf,
            glob_pattern="*.dxf",
            exclude_suffix="_rotated",
            file_types=[("DXF files", "*.dxf"), ("All files", "*.*")],
            button_label="Rotate to Horizontal",
        )


if __name__ == "__main__":
    App().mainloop()
