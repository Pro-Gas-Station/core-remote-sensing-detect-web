# -*- coding: utf-8 -*-
"""从 Pexels / NASA 等公开图源下载展示用高清遥感影像（本地缓存，按类别图文对应）"""
import os
import sys
import io
import time
import urllib.request

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
except ImportError:
    print('请先安装: pip install pillow')
    sys.exit(1)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, 'templates', 'images', 'web')
THUMB_SIZE = 200
FULL_MAX = 1400
UA = 'Mozilla/5.0 (compatible; RS-Detect-Web/1.0)'

# Pexels 免费图库（可商用）— 按类别精选航拍/遥感主题
# 图源: https://www.pexels.com
PEXELS_SOURCES = {
    'banner_1': 1486222,       # 城市航拍
    'banner_2': 325152,        # 机场航拍
    'banner_3': 266679,        # 港口航拍
    'airplane': 325152,        # 机场（飞机）
    'ship': 91216,             # 货轮
    'storage_tank': 2376997,   # 工业储罐
    'baseball_diamond': 2099778,
    'tennis_court': 338504,
    'basketball_court': 266526,
    'ground_track_field': 2099779,
    'harbor': 266679,
    'bridge': 210113,
    'vehicle': 170811,
    'sample_1': 1486222,
    'sample_2': 325152,
    'sample_3': 266679,
    'sample_4': 91216,
}

# NASA 官方图（若可访问则覆盖 banner_3）
NASA_SOURCES = {
    'banner_3': 'https://images-assets.nasa.gov/image/PIA23645/PIA23645~orig.jpg',
}


def pexels_url(photo_id, width=1400):
    return (
        f'https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg'
        f'?auto=compress&cs=tinysrgb&w={width}'
    )


def download(url, retries=3, timeout=60):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if len(data) > 8000:
                return data
        except Exception:
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError('下载失败: ' + url[:80])


def enhance(img):
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.05)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=2))
    return img


def save_jpeg(img, path, quality=90):
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    img.save(path, 'JPEG', quality=quality, optimize=True)


def resize_full(img):
    w, h = img.size
    if max(w, h) <= FULL_MAX:
        return img
    ratio = FULL_MAX / max(w, h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)


def make_thumb(img):
    thumb = img.copy()
    thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
    return thumb


def process_bytes(name, raw):
    img = Image.open(io.BytesIO(raw))
    img = enhance(resize_full(img))
    full_path = os.path.join(OUT_DIR, name + '.jpg')
    thumb_path = os.path.join(OUT_DIR, name + '_thumb.jpg')
    save_jpeg(img, full_path)
    save_jpeg(make_thumb(img), thumb_path, quality=86)
    print(f'  OK  {name}  {img.size[0]}x{img.size[1]}')
    return True


def fetch_pexels(name, photo_id):
    print(f'  Pexels {name} (#{photo_id}) ...')
    raw = download(pexels_url(photo_id))
    return process_bytes(name, raw)


def fetch_url(name, url):
    print(f'  URL {name} ...')
    raw = download(url)
    return process_bytes(name, raw)


def make_avatar(name, top_color, bottom_color, label):
    size = 128
    img = Image.new('RGB', (size, size), top_color)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    draw.ellipse([20, 20, size - 20, size - 20], fill=(255, 255, 255, 40))
    draw.text((size // 2 - 8, size // 2 - 10), label, fill=(255, 255, 255))
    process_bytes(name, _pil_to_jpeg_bytes(img))


def _pil_to_jpeg_bytes(img):
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ok, fail = 0, 0

    for name, pid in PEXELS_SOURCES.items():
        try:
            fetch_pexels(name, pid)
            ok += 1
        except Exception as e:
            print(f'  FAIL {name}: {e}')
            fail += 1

    for name, url in NASA_SOURCES.items():
        try:
            fetch_url(name, url)
            ok += 1
        except Exception as e:
            print(f'  SKIP NASA {name}: {e}')

    try:
        make_avatar('avatar_admin', (30, 80, 160), (20, 50, 120), 'A')
        make_avatar('avatar_user', (90, 100, 110), (60, 65, 75), 'U')
        ok += 2
    except Exception as e:
        print(f'  FAIL avatars: {e}')
        fail += 2

    print(f'\n完成: 成功 {ok}, 失败 {fail}, 目录 {OUT_DIR}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
