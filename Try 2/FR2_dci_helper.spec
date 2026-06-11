# -*- mode: python ; coding: utf-8 -*-
#
# Default GUI is tkinter (stdlib) via fr2_tk_gui.py — typical onefile ~8–12 MB on Windows
# (Qt6 alone is usually ~20+ MB before Python + your script).
#
# Optional Qt GUI from source: set FR2_DCI_GUI=qt and pip install PySide6; do not use this
# spec as-is for Qt — you would need to re-add PySide6 hiddenimports / hooks.

_datas = [('FR2_dci_helper.ico', '.')]

a = Analysis(
    ['FR2_dci_helper.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=['fr2_tk_gui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "shiboken6",
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FR2_dci_helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['FR2_dci_helper.ico'],
)
