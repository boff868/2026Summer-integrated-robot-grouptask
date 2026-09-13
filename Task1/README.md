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
├── models/
│   └── best_gjs_1.pt          # 最终训练权重（供 Jetson 部署 / ROS2 节点使用）
├── train/
│   ├── train.py / train.sh    # 基础训练脚本（自动检测 GPU/CPU）
│   ├── train_simple.sh        # 当前使用的训练脚本（YOLOv8m + 强增强）
│   ├── eval_predict.py        # 预测结果 vs 真值评估脚本（IoU>=0.5）
│   ├── fix_labels.py          # 标签规范化工具（多边形转方框）
│   └── downscale_dataset.py   # 图片压缩工具（GitHub 上传前用）
└── ros2/
    └── yolo_detector_node.py  # ROS2 检测结果发布节点
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
- 最终模型权重：[models/best_gjs_1.pt](models/best_gjs_1.pt)（可直接用于 Jetson 部署与 ROS2 节点）

详见 [results.md](results.md)。

## ROS2 发布

`ros2/yolo_detector_node.py`：摄像头实时采集 → YOLOv8 推理 → 检测结果以 JSON 发布到 ROS2 话题，同时弹窗显示标注画面（框 / 类别 / 置信度 / FPS）。

- 发布话题：`/detections/json`（std_msgs/String）
- JSON 结构：`{"fps": 12.5, "object_count": 2, "objects": [{"class_id": 0, "class_name": "keyboard", "confidence": 0.91, "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 300}}, ...]}`
- 运行：
  ```bash
  python3 ros2/yolo_detector_node.py --ros-args \
      -p model_path:=/home/nvidia/best_gjs_1.pt -p camera_id:=2 -p conf:=0.7
  ```
- 说明：类别名自动从模型读取；FP16 半精度推理（Jetson 友好）；画面窗口内按 q 退出

## 后续工作

- Jetson 部署：ONNX → TensorRT → 摄像头实时识别（目标 ≥5 FPS）
- 实机验收：20 个物体正确识别率 ≥ 80%，保存测试结果与错误案例
