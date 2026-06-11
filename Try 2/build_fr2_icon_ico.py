# -*- coding: utf-8 -*-
"""Rebuild FR2_dci_helper.ico from cheetah_paw_icon_source.png (Pillow).

Run from Try 2:
  python build_fr2_icon_ico.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    here = Path(__file__).resolve().parent
    src = here / "cheetah_paw_icon_source.png"
    out = here / "FR2_dci_helper.ico"
    if not src.is_file():
        print(f"ERROR: missing {src.name} (cheetah paw master art)", file=sys.stderr)
        return 1
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    side = max(w, h)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - w) // 2, (side - h) // 2))
    big = sq.resize((256, 256), Image.Resampling.LANCZOS)
    big.save(
        out,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
