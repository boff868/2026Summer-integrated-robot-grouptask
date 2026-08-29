# 2026Summer-integrated-robot-grouptask

**实验一：目标检测与识别** —— 基于 YOLOv8 的桌面物体目标检测。
识别 **键盘（keyboard）、农夫山泉（nongfu_spring）、手机（phone）** 三类桌面物体，支持后续 Jetson 实时部署与 ROS2 结果发布。

## 仓库结构

```
.
├── README.md                      # 本说明
├── results.md                     # 模型评估结果（理论结果）
├── dataset/                       # 数据集一：COCO 桌面物品过滤子集（脚本自动过滤，6 类）
│   ├── README.md / data.yaml
│   ├── images/  labels/
│   └── tools/                     # 数据获取 / 过滤 / 标注脚本
├── dataset_self/                  # 数据集二：自拍数据集（keyboard/nongfu_spring/phone）
│   ├── README.md / data.yaml
│   └── train/  valid/  test/      # 各含 images/ + labels/
└── train/
    ├── train.py / train.sh        # 基础训练脚本（自动检测 GPU/CPU）
    ├── fused_train.sh             # 两数据集融合训练命令
    ├── fuse_datasets.py           # 两数据集融合脚本（按类名对齐合并）
    ├── eval_predict.py            # 预测结果 vs 真值评估脚本（IoU>=0.5）
    └── downscale_dataset.py       # 图片压缩脚本（GitHub 上传前用）
```

## 数据集

### 1. dataset/ —— COCO 桌面物品过滤子集

- 来源：COCO 2017 train2017，脚本自动过滤（桌面 / 单物体 / 大物体面积 ≥ 10%）
- 6 类共 2331 张：bottle / cup / book / clock / cell phone / laptop
- 详细说明见 `dataset/README.md`

### 2. dataset_self/ —— 自拍数据集

- 真实场景实拍（DJI），3 类：**keyboard / nongfu_spring / phone**
- 共 **596 张**：train 428 / valid 73 / test 95（8:1:1）
- 原图约 1.5GB，为便于仓库分发已将图片压缩到最长边 800px（训练输入 640 足够）；标注为 YOLO 格式（多边形已转最小外接框）

## 数据融合训练

两个数据集按类名对齐后融合（`train/fuse_datasets.py`），统一为 3 类：

```bash
python3 train/fuse_datasets.py --src-a dataset --src-b dataset_self \
    --out dataset_fused --classes keyboard nongfu_spring phone
```

- 自动读取 data.yaml 类名映射，忽略不在目标类别中的标注（如 bottle / cup / laptop 等）
- COCO 子集中的 cell phone 与自拍数据的 phone 合并；keyboard / nongfu_spring 主要来自自拍数据

## 训练

融合训练（YOLOv8s，含增强参数）：

```bash
bash train/fused_train.sh
```

训练配置摘要：YOLOv8s、640×640、400 epochs（早停 patience=80）、mixup / mosaic / HSV 等增强。

## 评估结果

- 验证集：mAP50 = **0.944**（Precision 0.938 / Recall 0.914）
- 测试集：conf=0.5 时整体正确识别率 **0.925**（≥ 80% 验收线）

详见 [results.md](results.md)。

## 后续工作

- Jetson 部署：ONNX → TensorRT → 摄像头实时识别（目标 ≥5 FPS）
- ROS2 发布识别结果（类别、检测框、置信度）
- 实机验收：20 个物体正确识别率 ≥ 80%，保存测试结果与错误案例
