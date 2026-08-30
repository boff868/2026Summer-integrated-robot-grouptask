# 2026Summer-integrated-robot-grouptask

**实验一：目标检测与识别** —— 基于 YOLOv8 的桌面物体目标检测。
识别 **键盘（keyboard）、农夫山泉（nongfu_spring）、手机（phone）** 三类桌面物体，支持后续 Jetson 实时部署与 ROS2 结果发布。

## 仓库结构

```
.
├── README.md                  # 本说明
├── results.md                 # 模型评估结果（理论结果）
├── dataset_self/              # 自拍数据集（keyboard/nongfu_spring/phone）
│   ├── README.md / data.yaml
│   └── train/  valid/  test/  # 各含 images/ + labels/
└── train/
    ├── train.py / train.sh    # 基础训练脚本（自动检测 GPU/CPU）
    ├── train_simple.sh        # 当前使用的训练脚本（YOLOv8m + 强增强）
    ├── eval_predict.py        # 预测结果 vs 真值评估脚本（IoU>=0.5）
    ├── fix_labels.py          # 标签规范化工具（多边形转方框）
    └── downscale_dataset.py   # 图片压缩工具（GitHub 上传前用）
```

## 数据集

自拍数据集 `dataset_self/`：

- 真实场景实拍，3 类：**keyboard / nongfu_spring / phone**
- train / valid / test 划分，YOLO 格式标注（归一化方框）
- 图片压缩至最长边 800px，便于仓库分发（训练输入 640 足够）

## 训练

```bash
bash train/train_simple.sh
```

训练配置摘要：

- 模型：YOLOv8m，输入 640×640
- 600 epochs 上限 + 早停（patience=100）
- 数据增强：mixup / mosaic / 随机擦除 / 旋转平移缩放 / HSV 扰动 / 翻转

## 评估结果

- 验证集：mAP50 = **0.944**（Precision 0.938 / Recall 0.914）
- 测试集：conf=0.5 时整体正确识别率 **0.925**（≥ 80% 验收线）

详见 [results.md](results.md)。

## 后续工作

- Jetson 部署：ONNX → TensorRT → 摄像头实时识别（目标 ≥5 FPS）
- ROS2 发布识别结果（类别、检测框、置信度）
- 实机验收：20 个物体正确识别率 ≥ 80%，保存测试结果与错误案例
