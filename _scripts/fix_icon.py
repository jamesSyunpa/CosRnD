from PIL import Image
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ICO = os.path.join(ROOT, 'Icon.ico')
OUT_ICO = os.path.join(ROOT, 'Icon.ico')  # 덮어쓰기

# 원하는 정사각 사이즈 목록 (일반적으로 포함되는 크기)
TARGET_SIZES = [256, 128, 64, 48, 32, 16]

def make_square(img: Image.Image, fill=(0, 0, 0, 0)) -> Image.Image:
    """비정사각 이미지를 정사각형으로 패딩(가운데 정렬)합니다."""
    w, h = img.size
    if w == h:
        return img
    side = max(w, h)
    sq = Image.new('RGBA', (side, side), fill)
    # 가운데 배치
    x = (side - w) // 2
    y = (side - h) // 2
    sq.paste(img, (x, y))
    return sq

def load_best_source() -> Image.Image:
    """ICO의 첫 프레임을 불러와 정사각형으로 만들어 소스 이미지를 반환."""
    im = Image.open(SRC_ICO)
    # 첫 프레임을 베이스로 사용
    try:
        im.seek(0)
    except Exception:
        pass
    im = im.convert('RGBA')
    im = make_square(im)
    return im

def build_square_ico():
    if not os.path.exists(SRC_ICO):
        raise FileNotFoundError(f"Icon ico not found: {SRC_ICO}")

    base = load_best_source()

    # 각 타겟 크기별로 리사이즈한 이미지를 준비
    images = []
    for sz in TARGET_SIZES:
        img = base.resize((sz, sz), Image.LANCZOS)
        images.append(img)

    # 첫 이미지를 기준으로 .ico 저장, sizes 메타 포함
    # Pillow는 'sizes' 인자로 (width,height) 튜플 목록을 받음
    sizes = [(sz, sz) for sz in TARGET_SIZES]
    images[0].save(OUT_ICO, format='ICO', sizes=sizes)
    print(f"[OK] Rebuilt square Icon.ico with sizes: {sizes}")

if __name__ == '__main__':
    build_square_ico()
