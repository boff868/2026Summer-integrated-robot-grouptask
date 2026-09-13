#!/bin/bash
# ============================================================
# 目标检测训练（稳妥版）
# 直接在数据集上训练，无中间步骤
# batch=2 + workers=4：8GB 显存跑 yolov8m 不会 OOM
# 用法: bash train_simple.sh
# ============================================================
set -e

cd /root/dataset_XBY

# ① 修正 data.yaml 路径（Roboflow 导出的 ../ 相对路径改成当前目录相对路径）
sed -i 's|^train: .*|train: train/images|; s|^val: .*|val: valid/images|; s|^test: .*|test: test/images|' data.yaml

# ② 训练（yolov8m + 余弦退火 + 强增强，batch 调小防显存溢出）
yolo detect train \
    data=data.yaml \
    model=yolov8m.pt \
    epochs=600 imgsz=640 batch=2 workers=4 patience=100 \
    cos_lr=True mixup=0.5 erasing=0.4 \
    degrees=15 translate=0.2 scale=0.5 shear=10 \
    hsv_h=0.02 hsv_s=0.8 hsv_v=0.5 fliplr=0.5 \
    project=/root/runs name=simple

echo "训练完成，权重: /root/runs/simple/weights/best.pt"
