# -*- coding: utf-8 -*-
"""Optional PySide6 GUI for FR2 DCI Helper (not used by the default frozen EXE).

From this directory, with PySide6 installed:  python fr2_qt_gui.py
Default launcher is fr2_tk_gui (tkinter) via FR2_dci_helper.py --gui.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime

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


def _build_palette(dark: bool):
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    if dark:
        bg = QColor(0x1E, 0x1E, 0x1E)
        fg = QColor(0xD4, 0xD4, 0xD4)
        base = QColor(0x1E, 0x1E, 0x1E)
        alt_base = QColor(0x2D, 0x2D, 0x2D)
        btn = QColor(0x3C, 0x3C, 0x3C)
        highlight = QColor(0x26, 0x4F, 0x78)
    else:
        bg = QColor(0xF0, 0xF0, 0xF0)
        fg = QColor(0x1A, 0x1A, 0x1A)
        base = QColor(0xFF, 0xFF, 0xFF)
        alt_base = QColor(0xF5, 0xF5, 0xF5)
        btn = QColor(0xE0, 0xE0, 0xE0)
        highlight = QColor(0x00, 0x78, 0xD4)
    pal.setColor(QPalette.Window, bg)
    pal.setColor(QPalette.WindowText, fg)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, alt_base)
    pal.setColor(QPalette.Text, fg)
    pal.setColor(QPalette.Button, btn)
    pal.setColor(QPalette.ButtonText, fg)
    pal.setColor(QPalette.Highlight, highlight)
    pal.setColor(QPalette.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    pal.setColor(QPalette.PlaceholderText, QColor(0x88, 0x88, 0x88))
    return pal


def main() -> int:
    try:
        from PySide6.QtCore import QProcess, QUrl
        from PySide6.QtGui import QDesktopServices, QFont, QIcon, QTextCursor
        from PySide6.QtWidgets import (
            QApplication,
            QButtonGroup,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPlainTextEdit,
            QPushButton,
            QRadioButton,
            QVBoxLayout,
            QWidget,
        )
    except (ImportError, OSError) as exc:
        print("ERROR: could not load PySide6 / Qt (GUI unavailable).", file=sys.stderr)
        print(f"  {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"  Interpreter: {sys.executable}", file=sys.stderr)
        try:
            import site as _site

            print(f"  site.ENABLE_USER_SITE: {_site.ENABLE_USER_SITE}", file=sys.stderr)
            us = _site.getusersitepackages()
            if us and isinstance(us, str):
                print(f"  User site-packages: {us}", file=sys.stderr)
        except Exception:
            pass
        if os.environ.get("PYTHONNOUSERSITE"):
            print(
                "  PYTHONNOUSERSITE is set; user-level installs (typical for Store Python) are hidden.",
                file=sys.stderr,
            )
        print(
            "\nTry (use the same interpreter that runs this script):\n"
            "  python -m pip install --user --force-reinstall PySide6\n"
            "If you use `python -S` or PYTHONNOUSERSITE, use a venv instead, or unset those.\n"
            "If the message mentions DLL load / WinRT / Qt6*, reinstall PySide6 and install the "
            "Microsoft VC++ Redistributable (x64).\n",
            file=sys.stderr,
        )
        if os.environ.get("FR2_DCI_GUI_DEBUG"):
            import traceback

            traceback.print_exc()
        return 1

    settings = _load_settings()
    ws_saved = (settings.get("wireshark_dir") or "").strip() or _default_wireshark_dir()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dark_initial = bool(settings.get("dark_mode", False))
    app.setPalette(_build_palette(dark_initial))

    class Fr2MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("FR2 DCI Helper")
            self.resize(780, 720)
            self.setMinimumSize(580, 620)

            ico = _gui_window_icon_path()
            if ico:
                self.setWindowIcon(QIcon(ico))

            self._last_outdir: str | None = None
            self._proc: QProcess | None = None

            central = QWidget()
            self.setCentralWidget(central)
            root = QVBoxLayout(central)

            head = QHBoxLayout()
            ttl = QLabel("FR2 DCI Helper")
            f = ttl.font()
            f.setPointSize(12)
            f.setBold(True)
            ttl.setFont(f)
            head.addWidget(ttl)
            head.addStretch()
            self._dark_cb = QCheckBox("Dark mode")
            self._dark_cb.setChecked(dark_initial)
            self._dark_cb.toggled.connect(self._on_dark_toggled)
            head.addWidget(self._dark_cb)
            root.addLayout(head)

            line1 = QFrame()
            line1.setFrameShape(QFrame.HLine)
            line1.setFrameShadow(QFrame.Sunken)
            root.addWidget(line1)

            form = QGroupBox("Run configuration")
            grid = QGridLayout(form)
            pad = 6
            r = 0

            grid.addWidget(QLabel("RRC file:"), r, 0)
            self._file_edit = QLineEdit()
            self._file_edit.setMinimumWidth(400)
            grid.addWidget(self._file_edit, r, 1)
            b1 = QPushButton("Browse…")
            b1.clicked.connect(self._browse_rrc)
            grid.addWidget(b1, r, 2)
            r += 1

            grid.addWidget(QLabel("RRC source:"), r, 0)
            self._src_combo = QComboBox()
            self._src_combo.addItems(["auto", "reconfig", "setup"])
            self._src_combo.setCurrentIndex(0)
            grid.addWidget(self._src_combo, r, 1, 1, 2)
            r += 1

            grid.addWidget(QLabel("Detail level:"), r, 0)
            fmt_w = QWidget()
            fmt_l = QHBoxLayout(fmt_w)
            fmt_l.setContentsMargins(0, 0, 0, 0)
            self._fmt_group: list[QRadioButton] = []
            self._fmt_btn_group = QButtonGroup(self)
            for lbl, val in (
                ("Full tables", "full"),
                ("Summary only", "summary"),
                ("Quiet (config only)", "quiet"),
            ):
                rb = QRadioButton(lbl)
                rb.setProperty("fmt_value", val)
                self._fmt_btn_group.addButton(rb)
                fmt_l.addWidget(rb)
                self._fmt_group.append(rb)
            self._fmt_group[0].setChecked(True)
            grid.addWidget(fmt_w, r, 1, 1, 2)
            r += 1

            grid.addWidget(QLabel("Output folder:"), r, 0)
            self._out_edit = QLineEdit()
            grid.addWidget(self._out_edit, r, 1)
            b2 = QPushButton("Browse…")
            b2.clicked.connect(self._browse_out)
            grid.addWidget(b2, r, 2)
            r += 1

            grid.addWidget(QLabel("Wireshark folder:"), r, 0)
            self._ws_edit = QLineEdit(ws_saved)
            grid.addWidget(self._ws_edit, r, 1)
            b3 = QPushButton("Browse…")
            b3.clicked.connect(self._browse_ws)
            grid.addWidget(b3, r, 2)
            r += 1

            hint = QLabel(
                "Config files are copied here automatically after each successful run."
            )
            hf = hint.font()
            hf.setPointSize(8)
            hint.setFont(hf)
            hint.setStyleSheet("color: #888888;")
            grid.addWidget(hint, r, 1, 1, 2)
            r += 1

            self._show_opt = QCheckBox(
                "Show conditional / optional field tables (DCI 0_1 · 1_1)"
            )
            grid.addWidget(self._show_opt, r, 1, 1, 2)
            r += 1

            self._no_cfg = QCheckBox("Analysis only — do not write config files")
            grid.addWidget(self._no_cfg, r, 1, 1, 2)

            grid.setColumnStretch(1, 1)
            for i in range(r + 1):
                grid.setRowMinimumHeight(i, pad)
            root.addWidget(form)

            line2 = QFrame()
            line2.setFrameShape(QFrame.HLine)
            line2.setFrameShadow(QFrame.Sunken)
            root.addWidget(line2)

            bar = QHBoxLayout()
            self._run_btn = QPushButton("▶  Run")
            self._run_btn.clicked.connect(self._run)
            self._open_btn = QPushButton("Open output folder")
            self._open_btn.setEnabled(False)
            self._open_btn.clicked.connect(self._open_outdir)
            self._open_ws_btn = QPushButton("Open Wireshark folder")
            self._open_ws_btn.clicked.connect(self._open_wsdir)
            self._clear_btn = QPushButton("Clear output")
            self._clear_btn.clicked.connect(self._clear_out)
            bar.addWidget(self._run_btn)
            bar.addWidget(self._open_btn)
            bar.addWidget(self._open_ws_btn)
            bar.addWidget(self._clear_btn)
            bar.addStretch()
            root.addLayout(bar)

            self._out = QPlainTextEdit()
            self._out.setReadOnly(True)
            self._out.setFont(QFont("Consolas", 9))
            self._out.setMinimumHeight(280)
            root.addWidget(self._out, stretch=1)

            sb = self.statusBar()
            sb.showMessage("Ready.")

            self._ws_edit.textChanged.connect(self._sync_ws_btn)
            self._sync_ws_btn()

        def _fmt_value(self) -> str:
            for rb in self._fmt_group:
                if rb.isChecked():
                    return str(rb.property("fmt_value"))
            return "full"

        def _on_dark_toggled(self, checked: bool) -> None:
            QApplication.instance().setPalette(_build_palette(checked))
            _save_settings(
                {
                    "dark_mode": checked,
                    "wireshark_dir": self._ws_edit.text().strip(),
                }
            )

        def _sync_ws_btn(self) -> None:
            d = self._ws_edit.text().strip()
            self._open_ws_btn.setEnabled(bool(d and os.path.isdir(d)))

        def _browse_rrc(self) -> None:
            p, _ = QFileDialog.getOpenFileName(
                self,
                "Select RRC text file",
                "",
                "Text files (*.txt);;All files (*.*)",
            )
            if p:
                self._file_edit.setText(p)

        def _browse_out(self) -> None:
            p = QFileDialog.getExistingDirectory(self, "Select output folder for config files")
            if p:
                self._out_edit.setText(p)

        def _browse_ws(self) -> None:
            start = self._ws_edit.text().strip() or os.path.expandvars(r"%APPDATA%\Wireshark")
            p = QFileDialog.getExistingDirectory(
                self, "Select Wireshark profiles folder", start
            )
            if p:
                self._ws_edit.setText(p)

        def append_out(self, text: str) -> None:
            text = _ANSI_RE.sub("", text)
            cur = self._out.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._out.setTextCursor(cur)
            self._out.insertPlainText(text)

        def _copy_to_wireshark(self, src_dir: str) -> None:
            ws_dir = self._ws_edit.text().strip()
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
                self.append_out(
                    "\nBacked up previous Wireshark file(s) to:\n"
                    f"  {backup_root}\n"
                    + "\n".join(f"  {os.path.basename(p)}" for p in backed)
                    + "\n"
                )
            if copied:
                self.append_out(
                    f"\nCopied to Wireshark folder ({ws_dir}):\n"
                    + "\n".join(f"  {c}" for c in copied)
                    + "\n"
                )
                if skipped:
                    self.statusBar().showMessage("Copied to Wireshark with warnings; see log.")
                else:
                    self.statusBar().showMessage(f"Done. Also copied to Wireshark: {ws_dir}")
            if skipped:
                for fn, err in skipped:
                    self.append_out(f"\nWARNING: skipped {fn}: {err}\n")
                if not copied:
                    if backed:
                        self.statusBar().showMessage(
                            "Backup ok but copy to Wireshark failed; see log."
                        )
                    else:
                        self.statusBar().showMessage("Could not copy to Wireshark; see log.")
            _save_settings(
                {
                    "dark_mode": self._dark_cb.isChecked(),
                    "wireshark_dir": ws_dir,
                }
            )

        def _run(self) -> None:
            rrc_file = self._file_edit.text().strip()
            if not rrc_file:
                self.statusBar().showMessage("ERROR: no RRC file selected.")
                return

            self._out.clear()
            outdir = self._out_edit.text().strip() or None
            self._last_outdir = outdir or os.path.dirname(os.path.abspath(rrc_file))

            if getattr(sys, "frozen", False):
                cmd0 = [sys.executable, rrc_file]
            else:
                helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FR2_dci_helper.py")
                cmd0 = [sys.executable, helper, rrc_file]
            cmd = cmd0 + [
                "--rrc-source",
                self._src_combo.currentText(),
                "--format",
                self._fmt_value(),
                "--no-color",
            ]
            if outdir:
                cmd += ["--output-dir", outdir]
            if self._show_opt.isChecked():
                cmd.append("--show-optional")
            if self._no_cfg.isChecked():
                cmd.append("--no-config")

            self._run_btn.setEnabled(False)
            self._open_btn.setEnabled(False)
            self._open_ws_btn.setEnabled(False)
            self.statusBar().showMessage("Running…")

            self._proc = QProcess(self)
            self._proc.setProgram(cmd[0])
            self._proc.setArguments(cmd[1:])
            self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self._proc.readyReadStandardOutput.connect(self._on_proc_read)
            self._proc.finished.connect(lambda *_: self._on_proc_finished())
            self._proc.start()
            if not self._proc.waitForStarted(5000):
                self.append_out(
                    f"\nERROR: could not start process: {self._proc.errorString()}\n"
                )
                self._proc = None
                self._run_btn.setEnabled(True)
                self._sync_ws_btn()
                self.statusBar().showMessage("Could not start analysis process.")

        def _on_proc_read(self) -> None:
            if not self._proc:
                return
            data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
            if data:
                self.append_out(data)

        def _on_proc_finished(self) -> None:
            code = self._proc.exitCode() if self._proc else -1
            self._proc = None
            self._run_btn.setEnabled(True)
            self._sync_ws_btn()
            if code == 0:
                self.statusBar().showMessage(f"Done. Config files: {self._last_outdir}")
                self._open_btn.setEnabled(True)
                if not self._no_cfg.isChecked() and self._last_outdir:
                    self._copy_to_wireshark(self._last_outdir)
            else:
                self.statusBar().showMessage(f"Finished with exit code {code}.")

        def _open_outdir(self) -> None:
            d = self._last_outdir
            if d and os.path.isdir(d):
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.normpath(d)))

        def _open_wsdir(self) -> None:
            d = self._ws_edit.text().strip()
            if not d:
                self.statusBar().showMessage("Set the Wireshark folder path above, then try again.")
                return
            if not os.path.isdir(d):
                self.statusBar().showMessage(f"Not a valid folder: {d}")
                return
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.normpath(d))):
                self.statusBar().showMessage("Could not open Wireshark folder.")

        def _clear_out(self) -> None:
            self._out.clear()
            self.statusBar().showMessage("Ready.")

        def closeEvent(self, event) -> None:
            _save_settings(
                {
                    "dark_mode": self._dark_cb.isChecked(),
                    "wireshark_dir": self._ws_edit.text().strip(),
                }
            )
            super().closeEvent(event)

    w = Fr2MainWindow()
    w.show()
    return app.exec()


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
