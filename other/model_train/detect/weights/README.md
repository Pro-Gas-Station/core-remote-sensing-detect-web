# 预训练权重

YOLO 官方权重未纳入版本库。

训练前将 `yolo12n.pt` 置于本目录，或由 ultralytics 自动下载：

```bash
cd other/model_train/detect/code
python -c "from ultralytics import YOLO; YOLO('yolo12n.pt')"
```

Web 服务默认读取：

`output/已经训练好的模型和测试结果/train/weights/best.pt`
