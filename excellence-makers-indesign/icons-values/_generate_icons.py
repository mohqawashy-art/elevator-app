"""Generate transparent PNG icons for Excellence Makers Values page."""
from PIL import Image, ImageDraw
import math
import os

OUT = os.path.dirname(os.path.abspath(__file__))
OUT_ONLY = os.path.join(OUT, "icon-only")
os.makedirs(OUT_ONLY, exist_ok=True)

SIZE = 1024
GOLD = (196, 163, 90, 255)  # #C4A35A
NAVY = (11, 42, 74, 255)  # #0B2A4A
STROKE = max(18, SIZE // 48)
CIRCLE_STROKE = max(22, SIZE // 40)


def new_canvas():
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))


def draw_circle(draw):
    m = int(SIZE * 0.08)
    draw.ellipse([m, m, SIZE - m, SIZE - m], outline=GOLD, width=CIRCLE_STROKE)


def center():
    return SIZE // 2, SIZE // 2


def icon_quality(draw):
    cx, cy = center()
    r = int(SIZE * 0.16)
    draw.ellipse(
        [cx - r, cy - int(SIZE * 0.20) - r, cx + r, cy - int(SIZE * 0.20) + r],
        outline=NAVY,
        width=STROKE,
    )
    s = int(SIZE * 0.07)
    oy = cy - int(SIZE * 0.20)
    draw.polygon(
        [(cx, oy - s), (cx + int(s * 0.7), oy), (cx, oy + s), (cx - int(s * 0.7), oy)],
        outline=NAVY,
    )
    top = cy - int(SIZE * 0.04)
    draw.line(
        [(cx - int(SIZE * 0.06), top), (cx - int(SIZE * 0.12), cy + int(SIZE * 0.22))],
        fill=NAVY,
        width=STROKE,
    )
    draw.line(
        [(cx + int(SIZE * 0.06), top), (cx + int(SIZE * 0.12), cy + int(SIZE * 0.22))],
        fill=NAVY,
        width=STROKE,
    )
    draw.line(
        [
            (cx - int(SIZE * 0.12), cy + int(SIZE * 0.22)),
            (cx - int(SIZE * 0.02), cy + int(SIZE * 0.12)),
        ],
        fill=NAVY,
        width=STROKE,
    )
    draw.line(
        [
            (cx + int(SIZE * 0.12), cy + int(SIZE * 0.22)),
            (cx + int(SIZE * 0.02), cy + int(SIZE * 0.12)),
        ],
        fill=NAVY,
        width=STROKE,
    )


def icon_safety(draw):
    cx, cy = center()
    top = cy - int(SIZE * 0.22)
    bot = cy + int(SIZE * 0.24)
    w = int(SIZE * 0.22)
    pts = [
        (cx, top),
        (cx + w, top + int(SIZE * 0.08)),
        (cx + w, cy + int(SIZE * 0.02)),
        (cx, bot),
        (cx - w, cy + int(SIZE * 0.02)),
        (cx - w, top + int(SIZE * 0.08)),
    ]
    draw.line(pts + [pts[0]], fill=NAVY, width=STROKE, joint="curve")
    draw.line(
        [
            (cx - int(SIZE * 0.10), cy),
            (cx - int(SIZE * 0.02), cy + int(SIZE * 0.10)),
            (cx + int(SIZE * 0.12), cy - int(SIZE * 0.10)),
        ],
        fill=NAVY,
        width=STROKE,
        joint="curve",
    )


def icon_commitment(draw):
    cx, cy = center()
    r = int(SIZE * 0.22)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=NAVY, width=STROKE)
    draw.line([(cx, cy), (cx, cy - int(SIZE * 0.12))], fill=NAVY, width=STROKE)
    draw.line(
        [(cx, cy), (cx + int(SIZE * 0.10), cy + int(SIZE * 0.04))],
        fill=NAVY,
        width=STROKE,
    )
    for ang in (0, 90, 180, 270):
        rad = math.radians(ang)
        x1 = cx + int((r - STROKE * 2) * math.sin(rad))
        y1 = cy - int((r - STROKE * 2) * math.cos(rad))
        x2 = cx + int((r - STROKE * 4.5) * math.sin(rad))
        y2 = cy - int((r - STROKE * 4.5) * math.cos(rad))
        draw.line([(x1, y1), (x2, y2)], fill=NAVY, width=max(10, STROKE // 2))


def icon_innovation(draw):
    cx, cy = center()
    r = int(SIZE * 0.16)
    by = cy - int(SIZE * 0.06)
    draw.ellipse([cx - r, by - r, cx + r, by + r], outline=NAVY, width=STROKE)
    nw = int(SIZE * 0.08)
    draw.line(
        [(cx - nw, by + int(SIZE * 0.12)), (cx - nw, cy + int(SIZE * 0.10))],
        fill=NAVY,
        width=STROKE,
    )
    draw.line(
        [(cx + nw, by + int(SIZE * 0.12)), (cx + nw, cy + int(SIZE * 0.10))],
        fill=NAVY,
        width=STROKE,
    )
    draw.line(
        [(cx - nw, cy + int(SIZE * 0.12)), (cx + nw, cy + int(SIZE * 0.12))],
        fill=NAVY,
        width=STROKE,
    )
    draw.line(
        [(cx - nw, cy + int(SIZE * 0.18)), (cx + nw, cy + int(SIZE * 0.18))],
        fill=NAVY,
        width=STROKE,
    )
    for ang in (-50, -25, 25, 50):
        rad = math.radians(ang)
        x1 = cx + int((r + STROKE) * math.sin(rad))
        y1 = by - int((r + STROKE) * math.cos(rad))
        x2 = cx + int((r + STROKE * 3.2) * math.sin(rad))
        y2 = by - int((r + STROKE * 3.2) * math.cos(rad))
        draw.line([(x1, y1), (x2, y2)], fill=NAVY, width=max(12, STROKE // 2))


def icon_transparency(draw):
    cx, cy = center()
    left = cx - int(SIZE * 0.16)
    right = cx + int(SIZE * 0.10)
    top = cy - int(SIZE * 0.22)
    bot = cy + int(SIZE * 0.20)
    fold = int(SIZE * 0.08)
    draw.line(
        [
            (left, top),
            (right - fold, top),
            (right, top + fold),
            (right, bot),
            (left, bot),
            (left, top),
        ],
        fill=NAVY,
        width=STROKE,
        joint="curve",
    )
    draw.line(
        [(right - fold, top), (right - fold, top + fold), (right, top + fold)],
        fill=NAVY,
        width=STROKE,
    )
    for yoff in (0.02, 0.08, 0.14):
        y = cy - int(SIZE * (0.08 - yoff))
        draw.line(
            [(left + int(SIZE * 0.04), y), (right - int(SIZE * 0.04), y)],
            fill=NAVY,
            width=max(10, STROKE // 2),
        )
    mx, my = cx + int(SIZE * 0.14), cy + int(SIZE * 0.08)
    mr = int(SIZE * 0.11)
    draw.ellipse([mx - mr, my - mr, mx + mr, my + mr], outline=NAVY, width=STROKE)
    draw.line(
        [
            (mx + int(mr * 0.7), my + int(mr * 0.7)),
            (mx + int(SIZE * 0.16), my + int(SIZE * 0.16)),
        ],
        fill=NAVY,
        width=STROKE,
    )


def icon_partnership(draw):
    cx, cy = center()

    def person(px, head_y, scale=1.0):
        hr = int(SIZE * 0.055 * scale)
        draw.ellipse(
            [px - hr, head_y - hr, px + hr, head_y + hr], outline=NAVY, width=STROKE
        )
        body_top = head_y + hr + int(SIZE * 0.02)
        body_bot = body_top + int(SIZE * 0.14 * scale)
        bw = int(SIZE * 0.09 * scale)
        draw.arc(
            [px - bw, body_top - int(SIZE * 0.02), px + bw, body_bot],
            0,
            180,
            fill=NAVY,
            width=STROKE,
        )
        draw.line(
            [(px - bw, body_top + int(SIZE * 0.04)), (px - bw, body_bot)],
            fill=NAVY,
            width=STROKE,
        )
        draw.line(
            [(px + bw, body_top + int(SIZE * 0.04)), (px + bw, body_bot)],
            fill=NAVY,
            width=STROKE,
        )

    person(cx - int(SIZE * 0.16), cy - int(SIZE * 0.08), 0.95)
    person(cx + int(SIZE * 0.16), cy - int(SIZE * 0.08), 0.95)
    person(cx, cy - int(SIZE * 0.16), 1.1)


ICONS = [
    ("value-quality", "الجودة", icon_quality),
    ("value-safety", "السلامة", icon_safety),
    ("value-commitment", "الالتزام", icon_commitment),
    ("value-innovation", "الابتكار", icon_innovation),
    ("value-transparency", "الشفافية", icon_transparency),
    ("value-partnership", "الشراكة", icon_partnership),
]


def main():
    for en, ar, fn in ICONS:
        img = new_canvas()
        draw = ImageDraw.Draw(img)
        draw_circle(draw)
        fn(draw)
        path = os.path.join(OUT, f"{en}.png")
        img.save(path, "PNG")
        print("saved", path)

        img2 = new_canvas()
        draw2 = ImageDraw.Draw(img2)
        fn(draw2)
        path2 = os.path.join(OUT_ONLY, f"{en}.png")
        img2.save(path2, "PNG")
        print("saved", path2)

    print("DONE ->", OUT)


if __name__ == "__main__":
    main()
