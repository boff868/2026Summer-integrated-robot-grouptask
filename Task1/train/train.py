#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验一：目标检测与识别 —— 模型训练脚本（最终版）
=================================================
- 模型：YOLOv8m（中量级，25.9M 参数，精度与速度均衡；
        部署到 Jetson 时换用更小的 YOLOv8n/s 或导出 TensorRT 引擎）
- 数据：默认 ../dataset_self/data.yaml（自采数据集，keyboard / nongfu_spring / phone 三类）
- 训练：强数据增强（Mosaic / MixUp / Random Erasing / 几何与颜色增强）
        + 余弦退火学习率 + 早停（patience=100）
- 设备：自动检测 CUDA / MPS / CPU
- 结果：runs/desktop_train/weights/best.pt

用法：
    python3 train.py                              # 用默认参数训练
    python3 train.py --data /path/to/data.yaml    # 指定数据集
    python3 train.py --epochs 300 --imgsz 640 --batch 4   # 自定义关键参数

依赖：
    pip install ultralytics
"""

import argparse
import os
import shutil

import torch
from ultralytics import YOLO


def parse_args():
    p = argparse.ArgumentParser(description="YOLOv8 桌面物品检测训练")
    p.add_argument("--data", default=None, help="data.yaml 路径（默认自动找 ../dataset_self/data.yaml）")
    p.add_argument("--model", default="yolov8m.pt", help="预训练模型（yolov8n/s/m/l/x.pt）")
    p.add_argument("--epochs", type=int, default=None, help="训练轮数（默认 GPU 600）")
    p.add_argument("--imgsz", type=int, default=None, help="输入图片尺寸（默认 640）")
    p.add_argument("--batch", type=int, default=None, help="batch size（默认按显存自动调整）")
    p.add_argument("--workers", type=int, default=None, help="数据加载进程数（Docker 容器建议 <=2）")
    p.add_argument("--device", default=None, help="cuda / cpu / 0 / 1 ...（默认自动检测）")
    p.add_argument("--patience", type=int, default=100, help="早停轮数")
    return p.parse_args()


def main():
    args = parse_args()

    # ---- 数据集路径 ----
    data = args.data or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "dataset_self", "data.yaml"
    )
    data = os.path.abspath(data)
    if not os.path.exists(data):
        print(f"[错误] 找不到 data.yaml: {data}")
        print("请用 --data 指定正确路径，例如: python3 train.py --data /root/dataset_self/data.yaml")
        return

    # ---- 设备 ----
    device = args.device
    if device is None:
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"  # Apple Silicon (M系列芯片) 加速
        else:
            device = "cpu"

    # MPS 尚未实现 torchvision::nms 等算子，开启官方推荐的 CPU 回退
    if device == "mps":
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        print("==> 已开启 PYTORCH_ENABLE_MPS_FALLBACK=1（MPS 不支持的算子自动回退 CPU）")

    print(f"==> 训练设备: {device}")

    # ---- 默认参数（按设备自动调整）----
    if args.epochs is None:
        args.epochs = 600 if device == "cuda" else (200 if device == "mps" else 100)
    if args.imgsz is None:
        args.imgsz = 640 if device in ("cuda", "mps") else 416
    if args.batch is None:
        # 8GB 显存跑 yolov8m 实测 batch=2 稳定；更大显存可自行调大
        args.batch = 2 if device == "cuda" else (4 if device == "mps" else 8)

    # ---- 数据加载进程数 ----
    if args.workers is None:
        # Docker 容器默认 /dev/shm 只有 64MB，多进程数据加载会撑爆共享内存（Bus error）
        try:
            shm_total = shutil.disk_usage("/dev/shm").total
            args.workers = 2 if shm_total < 2 * 1024**3 else 8
            print(f"==> DataLoader workers: {args.workers}（/dev/shm 大小: {shm_total / 1024**3:.1f}GB）")
        except OSError:
            args.workers = 8
            print("==> DataLoader workers: 8（未检测到 /dev/shm 限制）")

    print(f"==> 数据集: {data}")
    print(f"==> 模型: {args.model}")
    print(f"==> 参数: epochs={args.epochs}, imgsz={args.imgsz}, batch={args.batch}, "
          f"workers={args.workers}, patience={args.patience}")

    # ---- 加载 COCO 预训练权重（数据量小，必须从预训练开始做迁移学习）----
    model = YOLO(args.model)

    # ---- 训练（最终版参数：强增强 + 余弦退火 + 早停）----
    model.train(
        data=data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=device,
        patience=args.patience,   # 验证集连续 100 轮无提升自动停止
        pretrained=True,
        cos_lr=True,              # 余弦退火学习率
        warmup_epochs=5,
        mosaic=1.0,               # Mosaic 数据增强
        close_mosaic=10,          # 最后 10 轮关闭 Mosaic
        mixup=0.5,                # MixUp 增强
        erasing=0.4,              # 随机擦除
        degrees=15,               # 旋转 ±15°
        translate=0.2,            # 平移 20%
        scale=0.5,                # 缩放 ±50%
        shear=10,                 # 剪切 10°
        hsv_h=0.02, hsv_s=0.8, hsv_v=0.5,   # HSV 颜色抖动
        fliplr=0.5,               # 水平翻转 50%
        project="runs",
        name="desktop_train",
    )

    # ---- 在测试集上评估（输出 mAP50 / mAP50-95，写报告要用）----
    print("==> 训练完成，用 best.pt 在测试集上评估...")
    metrics = model.val(
        data=data,
        split="test",
        imgsz=args.imgsz,
        device=device,
    )
    print(f"==> mAP50: {metrics.box.map50:.4f} | mAP50-95: {metrics.box.map:.4f}")

    # ---- 部署提示 ----
    print("\n训练权重: runs/desktop_train/weights/best.pt")
    print("部署到 Jetson 前可导出 ONNX / TensorRT:")
    print("    yolo export model=runs/desktop_train/weights/best.pt format=onnx imgsz=640")
    print("    yolo export model=runs/desktop_train/weights/best.pt format=engine device=0 imgsz=640")


if __name__ == "__main__":
    main()
