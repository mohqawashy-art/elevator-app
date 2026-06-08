import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "templates"
SCRIPT = '<script src="/static/liftcore-dates.js" defer></script>'
CSS_LINK = re.compile(r'(<link rel="stylesheet" href="/static/liftcore-layout\.css">)')
DATE_ATTR = re.compile(r'(<input\b(?![^>]*\blang=)([^>]*\btype="date"))', re.I)


def main():
    patched = 0
    for path in ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        original = text
        if "liftcore-layout.css" in text and "liftcore-dates.js" not in text:
            text = CSS_LINK.sub(r"\1\n" + SCRIPT, text, count=1)
        text = DATE_ATTR.sub(lambda m: m.group(1) + ' lang="en-GB"' + m.group(2), text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            patched += 1
    print(f"patched {patched} files")


if __name__ == "__main__":
    main()
