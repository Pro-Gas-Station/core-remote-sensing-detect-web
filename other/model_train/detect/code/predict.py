from ultralytics import YOLO

# 加载训练好的模型
model = YOLO("output/train/weights/best.pt")

# 图片路径
image_path = "dataset/small_dataset/train/images/pos_056.jpg"
# 预测图片
results = model(image_path, save=True, project="output", name="predict", imgsz=640)

# 访问结果
for result in results:
    xywh = result.boxes.xywh  # center-x, center-y, width, height
    xywhn = result.boxes.xywhn  # normalized
    xyxy = result.boxes.xyxy  # top-left-x, top-left-y, bottom-right-x, bottom-right-y
    xyxyn = result.boxes.xyxyn  # normalized
    names = [result.names[cls.item()] for cls in result.boxes.cls.int()]  # class name of each box
    confs = result.boxes.conf  # confidence score of each box
    print("xywh: ", xywh)
    print("xywhn: ", xywhn)
    print("xyxy: ", xyxy)
    print("xyxyn: ", xyxyn)
    print("names: ", names)
    print("confs: ", confs)

""" 输出结果如下：
xywh:  tensor([[400.0136, 478.8882, 792.3619, 499.0480],
        [740.4135, 636.7728, 138.7925, 483.8793],
        [143.3527, 651.8801, 191.8959, 504.6299],
        [283.7633, 634.5622, 121.4086, 451.7471],
        [ 34.4536, 714.2138,  68.8637, 316.2908]])
xywhn:  tensor([[0.4938, 0.4434, 0.9782, 0.4621],
        [0.9141, 0.5896, 0.1713, 0.4480],
        [0.1770, 0.6036, 0.2369, 0.4672],
        [0.3503, 0.5876, 0.1499, 0.4183],
        [0.0425, 0.6613, 0.0850, 0.2929]])
xyxy:  tensor([[3.8327e+00, 2.2936e+02, 7.9619e+02, 7.2841e+02],
        [6.7102e+02, 3.9483e+02, 8.0981e+02, 8.7871e+02],
        [4.7405e+01, 3.9957e+02, 2.3930e+02, 9.0420e+02],
        [2.2306e+02, 4.0869e+02, 3.4447e+02, 8.6044e+02],
        [2.1726e-02, 5.5607e+02, 6.8885e+01, 8.7236e+02]])
xyxyn:  tensor([[4.7318e-03, 2.1237e-01, 9.8296e-01, 6.7446e-01],
        [8.2842e-01, 3.6559e-01, 9.9977e-01, 8.1362e-01],
        [5.8524e-02, 3.6997e-01, 2.9543e-01, 8.3722e-01],
        [2.7538e-01, 3.7842e-01, 4.2527e-01, 7.9670e-01],
        [2.6822e-05, 5.1488e-01, 8.5044e-02, 8.0774e-01]])
names:  ['bus', 'person', 'person', 'person', 'person']
confs:  tensor([0.9402, 0.8882, 0.8783, 0.8558, 0.6219])
"""
