# 目标检测推理服务
import os
import base64
import io
import tempfile
import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO
from config import MODEL_CONFIGS, AVAILABLE_MODELS, CLASS_NAME_MAPPING

_model_cache = {}

BOX_COLORS = [
    (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0),
    (0, 128, 255), (128, 255, 0),
]


def load_model(model_name):
    if model_name in _model_cache:
        return _model_cache[model_name]

    cfg = MODEL_CONFIGS.get(model_name)
    if not cfg:
        raise ValueError('不支持的模型: ' + model_name)

    model_path = cfg['model_path']
    if not os.path.isfile(model_path):
        raise FileNotFoundError(
            '模型权重不存在: ' + model_path + '，请先运行 train.py 完成训练'
        )

    print('加载模型', model_name, model_path)
    _model_cache[model_name] = YOLO(model_path)
    return _model_cache[model_name]


def get_models():
    return {'code': 200, 'data': AVAILABLE_MODELS}


def decode_base64_image(image_data):
    if image_data.startswith('data:image'):
        image_data = image_data.split(',', 1)[1]

    raw = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(raw))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return img


def draw_detection_boxes(image, detections):
    arr = np.array(image)
    canvas = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    for det in detections:
        box = det['bbox']
        x1, y1, x2, y2 = int(box['x1']), int(box['y1']), int(box['x2']), int(box['y2'])
        cid = det['class_id']
        color = BOX_COLORS[cid % len(BOX_COLORS)]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

        label = det['class_name'] + ' ' + format(det['confidence'], '.2f')
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(label, font, 0.6, 2)
        cv2.rectangle(canvas, (x1, y1 - th - 8), (x1 + tw, y1), color, -1)
        cv2.putText(canvas, label, (x1, y1 - 4), font, 0.6, (255, 255, 255), 2)

    out = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    out.save(buf, format='JPEG', quality=90)
    encoded = base64.b64encode(buf.getvalue()).decode('utf-8')
    return 'data:image/jpeg;base64,' + encoded


def _empty_result(model_name, width, height, msg='未检测到任何目标'):
    return {
        'code': 200,
        'data': {
            'model': model_name,
            'image_size': {'width': width, 'height': height},
            'detections': [],
            'total_detections': 0,
            'detection_image': None,
            'message': msg,
        }
    }


def detect_objects(model_name, image_data):
    if model_name not in MODEL_CONFIGS:
        return {'code': 400, 'message': '不支持的模型: ' + model_name}

    try:
        model = load_model(model_name)
        image = decode_base64_image(image_data)
    except FileNotFoundError as e:
        return {'code': 404, 'message': str(e)}
    except ValueError as e:
        return {'code': 400, 'message': str(e)}

    img_w, img_h = image.size
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG')
            temp_path = tmp.name

        results = model(temp_path, verbose=False, imgsz=640)
        if not results:
            return {'code': 500, 'message': '模型推理未返回结果'}

        result = results[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return _empty_result(model_name, img_w, img_h)

        detections = []
        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            x1, y1, x2, y2 = xyxy
            conf = float(boxes.conf[i].cpu().numpy())
            class_id = int(boxes.cls[i].cpu().numpy())
            name_en = result.names[class_id]
            name_zh = CLASS_NAME_MAPPING.get(name_en, name_en)

            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            w, h = x2 - x1, y2 - y1

            detections.append({
                'detection_id': i + 1,
                'class_name': name_en,
                'class_name_zh': name_zh,
                'class_id': class_id,
                'confidence': conf,
                'percentage': format(conf * 100, '.2f') + '%',
                'bbox': {
                    'x1': float(x1), 'y1': float(y1),
                    'x2': float(x2), 'y2': float(y2),
                    'center_x': float(cx), 'center_y': float(cy),
                    'width': float(w), 'height': float(h),
                },
                'bbox_normalized': {
                    'center_x': float(cx / img_w),
                    'center_y': float(cy / img_h),
                    'width': float(w / img_w),
                    'height': float(h / img_h),
                },
            })

        detections.sort(key=lambda x: x['confidence'], reverse=True)

        det_image = None
        try:
            det_image = draw_detection_boxes(image, detections)
        except Exception as draw_err:
            print('绘制检测框失败:', draw_err)

        return {
            'code': 200,
            'data': {
                'model': model_name,
                'image_size': {'width': img_w, 'height': img_h},
                'detections': detections,
                'total_detections': len(detections),
                'highest_confidence': detections[0],
                'detection_image': det_image,
            }
        }
    except Exception as e:
        return {'code': 500, 'message': '检测过程出错: ' + str(e)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
