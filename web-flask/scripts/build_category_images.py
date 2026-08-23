# -*- coding: utf-8 -*-
"""
按 NWPU 标注为 10 类地物各选一张最清晰样例，生成展示图（图文严格对应）。
文案见 detect.html CLASS_DEF：飞机/船舶/储油罐/棒球场/网球场/篮球场/田径场/港口/桥梁/车辆
"""
import os
import shutil
import sys

try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    print('pip install pillow')
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(
    ROOT, '..', 'other', 'model_train', 'detect', 'dataset', 'all_dataset'
)
OUT_CATEGORIES = os.path.join(ROOT, 'templates', 'images', 'categories')
OUT_WEB = os.path.join(ROOT, 'templates', 'images', 'web')

CLASS_KEYS = [
    'airplane', 'ship', 'storage_tank', 'baseball_diamond', 'tennis_court',
    'basketball_court', 'ground_track_field', 'harbor', 'bridge', 'vehicle',
]

THUMB_SIZE = 220
FULL_MAX = 1200


def scan_best_images():
    """按类别找标注框最多、面积最大的正样本图。"""
    best = {i: {'score': 0, 'path': None, 'count': 0} for i in range(10)}
    splits = ['train', 'val', 'test']
    for split in splits:
        label_dir = os.path.join(DATASET, split, 'labels')
        img_dir = os.path.join(DATASET, split, 'images')
        if not os.path.isdir(label_dir):
            continue
        for name in os.listdir(label_dir):
            if not name.endswith('.txt'):
                continue
            stem = name[:-4]
            img_path = os.path.join(img_dir, stem + '.jpg')
            if not os.path.isfile(img_path):
                continue
            with open(os.path.join(label_dir, name), 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if not lines:
                continue
            per_class = {}
            for ln in lines:
                parts = ln.split()
                if len(parts) < 5:
                    continue
                cid = int(parts[0])
                if cid < 0 or cid > 9:
                    continue
                w, h = float(parts[3]), float(parts[4])
                area = w * h
                if cid not in per_class:
                    per_class[cid] = {'count': 0, 'area': 0}
                per_class[cid]['count'] += 1
                per_class[cid]['area'] += area
            for cid, stat in per_class.items():
                score = stat['count'] * 100 + stat['area']
                if score > best[cid]['score']:
                    best[cid] = {
                        'score': score,
                        'path': img_path,
                        'count': stat['count'],
                    }
    return best


def enhance(img):
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Sharpness(img).enhance(1.15)
    return img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=2))


def resize_full(img):
    w, h = img.size
    if max(w, h) <= FULL_MAX:
        return img
    r = FULL_MAX / max(w, h)
    return img.resize((int(w * r), int(h * r)), Image.Resampling.LANCZOS)


def save_pair(key, src_path):
    img = enhance(Image.open(src_path))
    img = resize_full(img)
    thumb = img.copy()
    thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)

    for out_dir in (OUT_CATEGORIES, OUT_WEB):
        os.makedirs(out_dir, exist_ok=True)
        full_out = os.path.join(out_dir, key + '.jpg')
        thumb_out = os.path.join(out_dir, key + '_thumb.jpg')
        img.save(full_out, 'JPEG', quality=92, optimize=True)
        thumb.save(thumb_out, 'JPEG', quality=88, optimize=True)
    print(f'  {key}: {os.path.basename(src_path)} ({img.size[0]}x{img.size[1]})')


def build_banners():
    """横幅用通用遥感场景，不冒充具体类别。"""
    picks = [
        ('banner_1', OUT_WEB, 'harbor.jpg'),
        ('banner_2', OUT_WEB, 'airplane.jpg'),
        ('banner_3', OUT_WEB, 'ship.jpg'),
    ]
    for banner, out_dir, src_name in picks:
        src = os.path.join(out_dir, src_name)
        if not os.path.isfile(src):
            continue
        img = enhance(Image.open(src))
        img = resize_full(img)
        thumb = img.copy()
        thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
        img.save(os.path.join(out_dir, banner + '.jpg'), 'JPEG', quality=92, optimize=True)
        thumb.save(os.path.join(out_dir, banner + '_thumb.jpg'), 'JPEG', quality=88, optimize=True)


def build_samples():
    """精选样例：直接复用已匹配的类别图。"""
    sample_map = [
        ('sample_1', 'airplane'),
        ('sample_2', 'ship'),
        ('sample_3', 'harbor'),
        ('sample_4', 'bridge'),
    ]
    for sample, key in sample_map:
        src = os.path.join(OUT_WEB, key + '.jpg')
        if not os.path.isfile(src):
            continue
        dst = os.path.join(OUT_WEB, sample + '.jpg')
        dst_t = os.path.join(OUT_WEB, sample + '_thumb.jpg')
        shutil.copy2(src, dst)
        shutil.copy2(os.path.join(OUT_WEB, key + '_thumb.jpg'), dst_t)


def main():
    if not os.path.isdir(DATASET):
        print('数据集目录不存在:', DATASET)
        return 1
    best = scan_best_images()
    print('按标注为每类选取 NWPU 样例:')
    for i, key in enumerate(CLASS_KEYS):
        info = best[i]
        if not info['path']:
            print(f'  FAIL {key}: 未找到标注图')
            continue
        save_pair(key, info['path'])
    build_banners()
    build_samples()
    print('完成 -> categories/ 与 web/')
    return 0


if __name__ == '__main__':
    sys.exit(main())
