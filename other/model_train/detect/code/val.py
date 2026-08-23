from ultralytics import YOLO

# 加载训练好的模型
model = YOLO("output/train/weights/best.pt")

# 使用数据集评估模型指标
metrics = model.val(data="dataset/small_dataset/data.yaml", project="output", name="val", split="test")
print(metrics.box.map)  # map50-95
print(metrics.box.map50)  # map50
print(metrics.box.map75)  # map75
print(metrics.box.maps)  # a list contains map50-95 of each category