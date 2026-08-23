# 遥感影像目标检测系统

面向 NWPU-VHR-10 数据集的遥感目标检测 Web 应用。系统提供图像上传、在线推理、结果可视化、用户管理与检测报告导出等功能，检测后端基于 YOLO 系列模型微调实现。

## 功能模块

- **目标检测**：本地上传遥感影像，返回标注结果与各类别统计
- **模型切换**：支持加载预训练权重或自定义训练权重（路径见 `config.py`）
- **用户管理**：注册、登录、个人信息、手机/邮箱绑定、管理员后台
- **模型数据**：展示训练曲线与验证集指标（`results.csv`、`测试集精度.txt`）
- **报告导出**：将检测结果导出为 PDF
- **智能问答**（可选）：配置 API 后可在检测页调用大语言模型；支持会员独立 Key 配置

检测类别（10 类）：飞机、船舶、储油罐、棒球场、网球场、篮球场、田径场、港口、桥梁、车辆。

## 技术架构

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+、Flask 3、SQLite |
| 检测推理 | PyTorch、Ultralytics、OpenCV |
| 前端 | HTML、CSS、JavaScript、ECharts |
| 模型训练 | Ultralytics YOLO12（`other/model_train/detect/code/`） |

## 目录结构

```
core-remote-sensing-detect-web/
├── web-flask/                 # Web 服务
│   ├── app.py                 # 应用入口与路由
│   ├── config.py              # 模型路径、类别映射、第三方服务配置
│   ├── service/               # 业务逻辑（检测、用户、邮件、短信、PDF、LLM）
│   ├── templates/             # 页面模板与静态资源
│   ├── data/                  # 运行时配置（参考 *.example.json）
│   └── scripts/               # 辅助脚本
└── other/model_train/detect/  # 模型训练
    ├── code/                  # train.py、val.py、predict.py
    ├── dataset/               # 数据集配置与标注（图像需自行准备）
    ├── weights/               # 预训练权重目录
    └── output/                # 训练输出（默认不纳入版本库）
```

## 运行环境

- 操作系统：Windows 10/11 或 Linux
- Python：3.10 及以上
- 硬件：推荐 NVIDIA GPU；CPU 可运行推理与训练，速度较慢

## 部署步骤

### 1. 安装依赖

```bash
cd web-flask
pip install -r requirements.txt
```

PyTorch 可按 [官方说明](https://pytorch.org/) 选择 CUDA 版本安装。

### 2. 初始化配置

在 `web-flask/data/` 下由模板复制配置文件：

```bash
copy email_config.example.json email_config.json
copy sms_config.example.json sms_config.json
copy member_llm_config.example.json member_llm_config.json
copy ..\users.example.json ..\users.json
```

邮件、短信、大模型均为可选模块。未配置短信时，开发模式下验证码输出至服务端控制台（`config.py` 中 `DEV_MODE = True`）。含密钥的配置文件不得提交至公开仓库。

### 3. 准备模型权重

默认权重路径：

`other/model_train/detect/output/已经训练好的模型和测试结果/train/weights/best.pt`

可通过以下方式获取：

- 执行 `other/model_train/detect/code/train.py` 完成训练
- 将已有 `best.pt` 放置至上述路径

预训练基础权重说明见 `other/model_train/detect/weights/README.md`。

### 4. 启动服务

Windows 可执行 `web-flask/start.bat`，或：

```bash
cd web-flask
python app.py
```

访问地址：<http://127.0.0.1:5011>

默认账号（`users.example.json`）：

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | 123456 | 管理员 |
| user | 123456 | 普通用户 |

部署前应修改默认密码。

## 数据集

训练数据来源于 [NWPU-VHR-10](https://www.kaggle.com/datasets/pavansriram3/nwpu-vhr)。项目内 `dataset/small_dataset/data.yaml` 为子集配置；图像与标注文件体积较大，需自行下载并按 YOLO 格式组织至 `train/`、`val/`、`test/` 目录。

## 模型训练与评估

```bash
cd other/model_train/detect/code
python train.py
python val.py
python predict.py
```

基于 YOLO12n 微调，测试集指标参考：mAP@0.5 = 91.8%，Precision = 95.9%，Recall = 85.0%（以本地 `测试集精度.txt` 为准）。

## 配置文件

| 文件 | 说明 |
|------|------|
| `data/email_config.json` | SMTP 邮件服务 |
| `data/sms_config.json` | 短信验证码服务 |
| `data/llm_config.json` | 检测页大语言模型（OpenAI 兼容接口） |
| `data/member_llm_config.json` | 会员账号专用模型配置 |

支持通过环境变量覆盖，变量名见 `config.py`。

## 常见问题

| 现象 | 处理 |
|------|------|
| 启动提示模型文件不存在 | 训练或放置 `best.pt`，并核对 `config.py` 中 `MODEL_CONFIGS` 路径 |
| 5011 端口占用 | 执行 `restart.bat`，或结束占用该端口的 Python 进程 |
| PDF 中文显示异常 | 保留 `data/fonts/simhei.ttf`，供 fpdf2 渲染使用 |

## 作者

孔杰 · 安徽理工大学 · 信息与计算科学

## 许可与声明

本项目代码以 MIT 协议开源。NWPU-VHR 数据集及 Ultralytics 模型权重须遵循各自原始许可协议。

## License

MIT
