import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "templates"
INPUT_RE = re.compile(r"<input\b[^>]*\btype=\"date\"[^>]*>", re.I)


def normalize_date_input(tag: str) -> str:
    if tag.count('type="date"') <= 1 and 'lang="en-GB"' in tag:
        return tag
    attrs = tag[6:-1].strip()
    chunks = re.findall(
        r'(\w[\w-]*)\s*=\s*(?:"[^"]*"|\'[^\']*\')|(\w[\w-]*)',
        attrs,
    )
    seen = {}
    order = []
    for key_quoted, key_bool in chunks:
        key = key_quoted or key_bool
        if not key:
            continue
        val_match = re.search(
            rf'{re.escape(key)}\s*=\s*("([^"]*)"|\'([^\']*)\')',
            attrs,
        )
        if val_match:
            value = val_match.group(2) if val_match.group(2) is not None else val_match.group(3)
            if key not in seen:
                order.append(key)
            seen[key] = f'{key}="{value}"'
        elif key_bool and key not in seen:
            order.append(key)
            seen[key] = key

    seen["type"] = 'type="date"'
    seen["lang"] = 'lang="en-GB"'
    if "type" not in order:
        order.append("type")
    if "lang" not in order:
        order.append("lang")

    deduped = []
    for key in order:
        if key in seen and seen[key] not in deduped:
            deduped.append(seen[key])
    for key in ("type", "lang"):
        item = seen[key]
        if item not in deduped:
            deduped.append(item)

    return "<input " + " ".join(deduped) + ">"


def main():
    patched = 0
    for path in ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        new_text = INPUT_RE.sub(lambda m: normalize_date_input(m.group(0)), text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            patched += 1
    print(f"fixed {patched} files")


if __name__ == "__main__":
    main()
