# -*- coding: utf-8 -*-
"""Flat tkinter GUI for FR2 DCI Helper (default; small PyInstaller footprint)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".fr2_dci_helper.json")


def _gui_window_icon_path() -> str | None:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = os.path.join(meipass, "FR2_dci_helper.ico")
            if os.path.isfile(p):
                return os.path.abspath(p)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        p = os.path.join(exe_dir, "FR2_dci_helper.ico")
        if os.path.isfile(p):
            return os.path.abspath(p)
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        here = os.getcwd()
    p = os.path.join(here, "FR2_dci_helper.ico")
    return os.path.abspath(p) if os.path.isfile(p) else None


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(d: dict) -> None:
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass


def _default_wireshark_dir() -> str:
    cand = os.path.join(
        os.environ.get("APPDATA", "") or os.path.expandvars("%APPDATA%"),
        "Wireshark",
    )
    return cand if os.path.isdir(cand) else ""


def _open_folder(path: str) -> bool:
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        return False
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except OSError:
        return False


class Fr2TkApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("FR2 DCI Helper")
        root.minsize(560, 560)
        root.geometry("760x680")

        ico = _gui_window_icon_path()
        if ico and os.name == "nt":
            try:
                root.iconbitmap(default=ico)
            except tk.TclError:
                pass

        settings = _load_settings()
        ws_saved = (settings.get("wireshark_dir") or "").strip() or _default_wireshark_dir()

        self._last_outdir: str | None = None
        self._running = False

        pad = {"padx": 6, "pady": 4}

        main = ttk.Frame(root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="FR2 DCI Helper", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", **pad
        )

        r = 1
        ttk.Label(main, text="RRC file:").grid(row=r, column=0, sticky="nw", **pad)
        self._file = ttk.Entry(main)
        self._file.grid(row=r, column=1, sticky="ew", **pad)
        ttk.Button(main, text="Browse…", command=self._browse_rrc).grid(
            row=r, column=2, **pad
        )
        r += 1

        ttk.Label(main, text="RRC source:").grid(row=r, column=0, sticky="w", **pad)
        self._src = ttk.Combobox(main, values=("auto", "reconfig", "setup"), width=12, state="readonly")
        self._src.set("auto")
        self._src.grid(row=r, column=1, sticky="w", **pad)
        r += 1

        ttk.Label(main, text="Detail level:").grid(row=r, column=0, sticky="nw", **pad)
        fmt_frame = ttk.Frame(main)
        fmt_frame.grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        self._fmt = tk.StringVar(value="full")
        for text, val in (
            ("Full tables", "full"),
            ("Summary only", "summary"),
            ("Quiet (config only)", "quiet"),
        ):
            ttk.Radiobutton(fmt_frame, text=text, value=val, variable=self._fmt).pack(
                anchor="w"
            )
        r += 1

        ttk.Label(main, text="Output folder:").grid(row=r, column=0, sticky="w", **pad)
        self._out = ttk.Entry(main)
        self._out.grid(row=r, column=1, sticky="ew", **pad)
        ttk.Button(main, text="Browse…", command=self._browse_out).grid(row=r, column=2, **pad)
        r += 1

        ttk.Label(main, text="Wireshark folder:").grid(row=r, column=0, sticky="w", **pad)
        self._ws = ttk.Entry(main)
        self._ws.insert(0, ws_saved)
        self._ws.grid(row=r, column=1, sticky="ew", **pad)
        ttk.Button(main, text="Browse…", command=self._browse_ws).grid(row=r, column=2, **pad)
        r += 1

        ttk.Label(
            main,
            text="Config files are copied here after each successful run (with backups).",
            font=("Segoe UI", 8),
            foreground="#666",
        ).grid(row=r, column=1, columnspan=2, sticky="w", padx=6)
        r += 1

        self._show_opt = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            main,
            text="Show conditional / optional field tables (DCI 0_1 · 1_1)",
            variable=self._show_opt,
        ).grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        r += 1

        self._no_cfg = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            main, text="Analysis only — do not write config files", variable=self._no_cfg
        ).grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        r += 1

        bar = ttk.Frame(main)
        bar.grid(row=r, column=0, columnspan=3, sticky="ew", **pad)
        self._run_btn = ttk.Button(bar, text="Run", command=self._run)
        self._run_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._open_btn = ttk.Button(bar, text="Open output folder", command=self._open_outdir, state=tk.DISABLED)
        self._open_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._open_ws_btn = ttk.Button(bar, text="Open Wireshark folder", command=self._open_wsdir)
        self._open_ws_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="Clear output", command=self._clear_out).pack(side=tk.LEFT)
        r += 1

        self._log = tk.Text(main, height=22, wrap="none", font=("Consolas", 9), state=tk.DISABLED)
        self._log.grid(row=r, column=0, columnspan=3, sticky="nsew", **pad)
        scroll_y = ttk.Scrollbar(main, orient="vertical", command=self._log.yview)
        scroll_y.grid(row=r, column=3, sticky="ns")
        self._log.configure(yscrollcommand=scroll_y.set)
        r += 1

        main.columnconfigure(1, weight=1)
        main.rowconfigure(r - 1, weight=1)

        self._status = tk.StringVar(value="Ready.")
        ttk.Label(main, textvariable=self._status, relief=tk.SUNKEN, anchor="w").grid(
            row=r, column=0, columnspan=4, sticky="ew", padx=6, pady=(4, 0)
        )

        self._ws.bind("<KeyRelease>", lambda _e: self._sync_ws_btn())
        self._sync_ws_btn()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _sync_ws_btn(self) -> None:
        d = self._ws.get().strip()
        self._open_ws_btn.configure(state=tk.NORMAL if (d and os.path.isdir(d)) else tk.DISABLED)

    def _browse_rrc(self) -> None:
        p = filedialog.askopenfilename(
            title="Select RRC text file",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if p:
            self._file.delete(0, tk.END)
            self._file.insert(0, p)

    def _browse_out(self) -> None:
        p = filedialog.askdirectory(title="Output folder for config files")
        if p:
            self._out.delete(0, tk.END)
            self._out.insert(0, p)

    def _browse_ws(self) -> None:
        start = self._ws.get().strip() or os.path.expandvars(r"%APPDATA%\Wireshark")
        kw: dict = {"title": "Wireshark profiles folder"}
        if os.path.isdir(start):
            kw["initialdir"] = start
        p = filedialog.askdirectory(**kw)
        if p:
            self._ws.delete(0, tk.END)
            self._ws.insert(0, p)
            self._sync_ws_btn()

    def _append(self, text: str) -> None:
        text = _ANSI_RE.sub("", text)
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, text)
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

    def _clear_out(self) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.configure(state=tk.DISABLED)
        self._status.set("Ready.")

    def _copy_to_wireshark(self, src_dir: str) -> None:
        ws_dir = self._ws.get().strip()
        if not ws_dir or not os.path.isdir(ws_dir):
            return
        backup_root = os.path.join(ws_dir, "fr2_dci_helper_backups")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        copied = []
        backed = []
        skipped = []
        for fname in ("dci_0_1_fields_config", "dci_1_1_fields_config"):
            src = os.path.join(src_dir, fname)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(ws_dir, fname)
            if os.path.isfile(dst):
                backup_name = f"{fname}.{ts}.bak"
                backup_path = os.path.join(backup_root, backup_name)
                try:
                    os.makedirs(backup_root, exist_ok=True)
                    shutil.copy2(dst, backup_path)
                    backed.append(backup_path)
                except OSError as exc:
                    skipped.append((fname, str(exc)))
                    continue
            try:
                shutil.copy2(src, dst)
                copied.append(fname)
            except OSError as exc:
                skipped.append((fname, str(exc)))

        if backed:
            self._append(
                "\nBacked up previous Wireshark file(s) to:\n"
                f"  {backup_root}\n"
                + "\n".join(f"  {os.path.basename(p)}" for p in backed)
                + "\n"
            )
        if copied:
            self._append(
                f"\nCopied to Wireshark folder ({ws_dir}):\n"
                + "\n".join(f"  {c}" for c in copied)
                + "\n"
            )
        for fn, err in skipped:
            self._append(f"\nWARNING: skipped {fn}: {err}\n")

        if copied and not skipped:
            self._status.set(f"Done. Also copied to Wireshark: {ws_dir}")
        elif skipped:
            self._status.set("Copy to Wireshark had warnings; see log.")
        _save_settings({"wireshark_dir": ws_dir})

    def _run(self) -> None:
        rrc_file = self._file.get().strip()
        if not rrc_file:
            self._status.set("ERROR: no RRC file selected.")
            messagebox.showwarning("FR2 DCI Helper", "Select an RRC text file first.")
            return
        if self._running:
            return

        self._clear_out()
        outdir = self._out.get().strip() or None
        self._last_outdir = outdir or os.path.dirname(os.path.abspath(rrc_file))

        if getattr(sys, "frozen", False):
            cmd0: list[str] = [sys.executable, rrc_file]
        else:
            helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FR2_dci_helper.py")
            cmd0 = [sys.executable, helper, rrc_file]
        cmd = cmd0 + [
            "--rrc-source",
            self._src.get(),
            "--format",
            self._fmt.get(),
            "--no-color",
        ]
        if outdir:
            cmd.extend(["--output-dir", outdir])
        if self._show_opt.get():
            cmd.append("--show-optional")
        if self._no_cfg.get():
            cmd.append("--no-config")

        self._running = True
        self._run_btn.configure(state=tk.DISABLED)
        self._open_btn.configure(state=tk.DISABLED)
        self._open_ws_btn.configure(state=tk.DISABLED)
        self._status.set("Running…")

        kw: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        def worker() -> None:
            code = -1
            try:
                proc = subprocess.Popen(cmd, **kw)
            except OSError as exc:
                self.root.after(0, lambda: self._append(f"\nERROR: could not start process: {exc}\n"))
                self.root.after(0, lambda: self._finished(-1))
                return
            assert proc.stdout is not None
            try:
                for line in iter(proc.stdout.readline, ""):
                    if line:
                        self.root.after(0, self._append, line)
                code = proc.wait()
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
            self.root.after(0, lambda c=code: self._finished(c))

        threading.Thread(target=worker, daemon=True).start()

    def _finished(self, code: int) -> None:
        self._running = False
        self._run_btn.configure(state=tk.NORMAL)
        self._sync_ws_btn()
        if code == 0:
            self._status.set(f"Done. Config files: {self._last_outdir}")
            self._open_btn.configure(state=tk.NORMAL)
            if not self._no_cfg.get() and self._last_outdir:
                self._copy_to_wireshark(self._last_outdir)
        else:
            self._status.set(f"Finished with exit code {code}.")

    def _open_outdir(self) -> None:
        d = self._last_outdir
        if d and os.path.isdir(d):
            if not _open_folder(d):
                self._status.set("Could not open output folder.")

    def _open_wsdir(self) -> None:
        d = self._ws.get().strip()
        if not d:
            self._status.set("Set the Wireshark folder path first.")
            return
        if not os.path.isdir(d):
            self._status.set(f"Not a valid folder: {d}")
            return
        if not _open_folder(d):
            self._status.set("Could not open Wireshark folder.")

    def _on_close(self) -> None:
        _save_settings({"wireshark_dir": self._ws.get().strip()})
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if os.name == "nt" and "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    Fr2TkApp(root)
    root.mainloop()
    return 0


def run() -> None:
    sys.exit(main())
