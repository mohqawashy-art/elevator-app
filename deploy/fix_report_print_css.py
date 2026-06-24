#!/usr/bin/env python3
"""إزالة قواعد CSS المكسورة بعد patch الطباعة."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates"

ORPHAN = re.compile(
    r"\n/\* print styles [^\n]*reports-print\.css \*/\n.*?\n\}\n",
    re.S,
)


def main() -> None:
    for path in sorted(ROOT.glob("report*.html")):
        text = path.read_text(encoding="utf-8")
        new = ORPHAN.sub("\n", text, count=1)
        if new != text:
            path.write_text(new, encoding="utf-8")
            print("fixed", path.name)


if __name__ == "__main__":
    main()
