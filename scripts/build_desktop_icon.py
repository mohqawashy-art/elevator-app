"""إنشاء liftcore.ico من شعار البرنامج."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'static' / 'images' / 'liftcore-header-logo.png'
OUT = ROOT / 'static' / 'images' / 'liftcore.ico'


def main():
    if not SRC.exists():
        raise SystemExit(f'Missing logo: {SRC}')
    img = Image.open(SRC).convert('RGBA')
    # مربّع بخلفية داكنة لظهور أوضح في شريط المهام
    side = max(img.size)
    canvas = Image.new('RGBA', (side, side), (7, 10, 16, 255))
    ox = (side - img.width) // 2
    oy = (side - img.height) // 2
    canvas.paste(img, (ox, oy), img)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    canvas.save(OUT, format='ICO', sizes=sizes)
    print('Wrote', OUT)


if __name__ == '__main__':
    main()
