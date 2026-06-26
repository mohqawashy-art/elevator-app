"""إنشاء أيقونات LiftCore (png للموقع وشريط المهام من ملف .ico)."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'static' / 'images'
OUT_ICO = OUT_DIR / 'liftcore.ico'
SRC_CANDIDATES = (
    OUT_DIR / 'liftcore-icon.png',
    OUT_DIR / 'liftcore-icon.ico',
    OUT_ICO,
    Path(r'E:\04-تنزيلات\Liftcore-icon.ico'),
)


def _load_best_image(src: Path) -> Image.Image:
    img = Image.open(src)
    if getattr(img, 'n_frames', 1) > 1:
        best = img
        best_area = 0
        for i in range(img.n_frames):
            img.seek(i)
            frame = img.copy().convert('RGBA')
            area = frame.width * frame.height
            if area > best_area:
                best_area = area
                best = frame
        return best
    return img.convert('RGBA')


def main():
    src = next((p for p in SRC_CANDIDATES if p.exists()), None)
    if not src:
        raise SystemExit(f'Missing icon source. Tried: {", ".join(str(p) for p in SRC_CANDIDATES)}')

    img = _load_best_image(src)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(OUT_ICO, format='ICO', sizes=sizes)
    print('Wrote', OUT_ICO)

    for px in (192, 512):
        out = OUT_DIR / f'icon-{px}.png'
        img.resize((px, px), Image.Resampling.LANCZOS).save(out, format='PNG')
        print('Wrote', out)


if __name__ == '__main__':
    main()
