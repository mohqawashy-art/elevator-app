"""Remove tbody tr:hover and row transitions from all templates (stops EN flicker)."""

import re

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

HOVER_PATTERNS = [

    re.compile(r"\s*tbody tr:hover\{background:[^}]+\}\s*\n?"),

    re.compile(r"\s*\.card-table tr:hover td\{background:[^}]+\}\s*\n?"),

    re.compile(r"\s*\.card-table tr:hover\{background:[^}]+\}\s*\n?"),

    re.compile(r"\s*tbody tr:hover\{background:[^;]+;[^}]+\}\s*\n?"),

]

TRANSITION = re.compile(

    r"tbody tr\{([^}]*?)transition:var\(--trans\);\s*([^}]*)\}|"

    r"tbody tr\{([^}]*?);\s*transition:var\(--trans\)([^}]*)\}"

)





def strip_transition(match):

    if match.group(1) is not None:

        return "tbody tr{%s%s}" % (match.group(1), match.group(2))

    return "tbody tr{%s%s}" % (match.group(3), match.group(4))





n = 0

for path in ROOT.glob("templates/**/*.html"):

    if path.parts[-2] == "partials":

        continue

    text = path.read_text(encoding="utf-8")

    orig = text

    for pat in HOVER_PATTERNS:

        text = pat.sub("\n", text)

    text = TRANSITION.sub(strip_transition, text)

    if text != orig:

        path.write_text(text, encoding="utf-8")

        n += 1

        print("stripped", path.relative_to(ROOT))



print("done", n, "files")

