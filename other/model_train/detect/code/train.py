from ultralytics import YOLO
from ultralytics.utils import DEFAULT_CFG
DEFAULT_CFG.save_dir= f"output/train"

# 加载基础yolo模型
model = YOLO("weights/yolo12n.pt")

# 使用数据集训练模型
results = model.train(data="dataset/small_dataset/data.yaml", epochs=50, imgsz=640)