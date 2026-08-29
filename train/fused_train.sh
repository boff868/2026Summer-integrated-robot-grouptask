#!/bin/bash
# 两数据集融合训练（在仓库根目录运行）
# 前置：已用 fuse_datasets.py 生成 dataset_fused/

cd "$(dirname "$0")/.."
if [ ! -d dataset_fused ]; then
    echo "未找到 dataset_fused/，请先运行:"
    echo "  python3 train/fuse_datasets.py --src-a dataset --src-b dataset_self --out dataset_fused"
    exit 1
fi

cd dataset_fused

yolo detect train \
  data=data.yaml \
  model=yolov8s.pt \
  epochs=400 imgsz=640 batch=4 patience=80 \
  mixup=0.2 mosaic=1.0 close_mosaic=20 \
  degrees=10 translate=0.15 scale=0.5 shear=5 \
  hsv_h=0.02 hsv_s=0.8 hsv_v=0.5 fliplr=0.5 \
  project=runs name=fused_train
