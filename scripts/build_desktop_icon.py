"""إنشاء أيقونات LiftCore (ico + png للتطبيق وشريط المهام)."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'static' / 'images' / 'liftcore-header-logo.png'
OUT_ICO = ROOT / 'static' / 'images' / 'liftcore.ico'
OUT_DIR = ROOT / 'static' / 'images'


def _square_canvas(img: Image.Image) -> Image.Image:
    side = max(img.size)
    canvas = Image.new('RGBA', (side, side), (7, 10, 16, 255))
    ox = (side - img.width) // 2
    oy = (side - img.height) // 2
    canvas.paste(img, (ox, oy), img)
    return canvas


def main():
    if not SRC.exists():
        raise SystemExit(f'Missing logo: {SRC}')
    img = Image.open(SRC).convert('RGBA')
    square = _square_canvas(img)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    square.save(OUT_ICO, format='ICO', sizes=sizes)
    print('Wrote', OUT_ICO)
    for px in (192, 512):
        out = OUT_DIR / f'icon-{px}.png'
        square.resize((px, px), Image.Resampling.LANCZOS).save(out, format='PNG')
        print('Wrote', out)


if __name__ == '__main__':
    main()
