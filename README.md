# FR2 DCI Helper

Parse **5G NR RRC text logs** to compute **DCI 0_1 / 1_1 / 0_0 / 1_0** bit widths per **3GPP TS 38.212** and emit **Wireshark** dissector field configs.

## What it does

- Ingests raw RRC captures (`rrcSetup`, `rrcReconfiguration`, NR-DC `mrdc-SecondaryCellGroup`, etc.)
- Computes **DCI 1_1** (PDSCH) and **DCI 0_1** (PUSCH) field bit widths from active BWP and cell-group parameters
- Computes **DCI 1_0 / 0_0** sizes for UE-specific and Common Search Space Type-3 fallback
- Prints **full** or **summary** reports; optional **quiet** mode for config-only output
- Generates Wireshark dissector configs: `dci_0_1_fields_config`, `dci_1_1_fields_config`
- Supports **NR-DC SCG** scoping, reconfiguration preference, and loose fill-in of cell identity when `spCellConfigCommon` is absent

## Requirements

- Python 3.10+ (stdlib **tkinter** GUI; no extra packages required for CLI or default GUI)
- Optional: **PySide6** for the Qt GUI (`pip install PySide6`; source use only, not bundled in the default EXE)

## Usage

```bash
cd "Try 2"
python FR2_dci_helper.py <rrc_log.txt>              # CLI, full output
python FR2_dci_helper.py --gui                      # tkinter GUI
python FR2_dci_helper.py log.txt --format summary   # compact summary + configs
```

Build a Windows one-file EXE (~10 MB):

```bash
cd "Try 2"
pip install pyinstaller
pyinstaller FR2_dci_helper.spec
```

Output: `dist/FR2_dci_helper.exe`

## Input

Use **live RRC text exports** (QCAT/QXDM, ASN.1-style logs). Do **not** pass saved tool output (`verify_*.txt` banners are rejected).

## Documentation

| File | Description |
|------|-------------|
| [`Try 2/TOOL_ARCHITECTURE.md`](Try%202/TOOL_ARCHITECTURE.md) | Architecture and decision flow |
| [`Try 2/3GPP_SPEC_TRACEABILITY.md`](Try%202/3GPP_SPEC_TRACEABILITY.md) | 3GPP clause ↔ code mapping |
| [`Try 2/requirements-gui.txt`](Try%202/requirements-gui.txt) | Optional GUI dependencies and troubleshooting |

## Layout

| Path | Role |
|------|------|
| `Try 2/FR2_dci_helper.py` | Core parser and DCI sizing engine |
| `Try 2/fr2_tk_gui.py` | Default GUI (bundled in EXE) |
| `Try 2/fr2_qt_gui.py` | Optional PySide6 GUI (source only) |
| `Try 2/FR2_dci_helper.spec` | PyInstaller spec (tkinter, ~10 MB EXE) |

## License

Add a license file if you intend to open-source this project publicly.
