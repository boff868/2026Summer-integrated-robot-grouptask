#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验一：目标检测与识别 —— 模型训练脚本
========================================
- 模型：YOLOv8n（nano 轻量版，便于后续部署到 Jetson 并满足 >=5 FPS）
- 数据：默认 ../dataset/data.yaml，可用 --data 指定（如 /root/desktop6/data.yaml）
- 设备：自动检测 GPU / CPU
    * GPU:  imgsz=640, epochs=150, batch=16
    * CPU:  imgsz=416, epochs=80,  batch=8   （虚拟机无 GPU 时自动变小，避免跑太久）
- 训练结果：runs/desktop_train/weights/best.pt

用法：
    python3 train.py --data /root/desktop6/data.yaml        # 用默认参数
    python3 train.py --data /root/desktop6/data.yaml --epochs 200 --imgsz 640 --batch 16

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
    p.add_argument("--data", default=None, help="data.yaml 路径（默认自动找 ../dataset/data.yaml）")
    p.add_argument("--epochs", type=int, default=None, help="训练轮数")
    p.add_argument("--imgsz", type=int, default=None, help="输入图片尺寸")
    p.add_argument("--batch", type=int, default=None, help="batch size")
    p.add_argument("--workers", type=int, default=None, help="数据加载进程数（Docker 容器建议 <=2）")
    p.add_argument("--device", default=None, help="cuda / cpu / 0 / 1 ...（默认自动检测）")
    return p.parse_args()


def main():
    args = parse_args()

    # ---- 数据集路径 ----
    data = args.data or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "dataset", "data.yaml"
    )
    data = os.path.abspath(data)
    if not os.path.exists(data):
        print(f"[错误] 找不到 data.yaml: {data}")
        print("请用 --data 指定正确路径，例如: python3 train.py --data /root/desktop6/data.yaml")
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
    print(f"==> 训练设备: {device}")

    # ---- 默认参数（按设备自动调整）----
    if args.epochs is None:
        args.epochs = 150 if device.startswith("cuda") else (100 if device == "mps" else 80)
    if args.imgsz is None:
        args.imgsz = 640 if device in ("cuda", "mps") else 416
    if args.batch is None:
        args.batch = 16 if device in ("cuda", "mps") else 8

    # ---- 数据加载进程数 ----
    if args.workers is None:
        # Docker 容器默认 /dev/shm 只有 64MB，多进程数据加载会撑爆共享内存（Bus error）
        # 检测到共享内存 < 2GB 时自动降为 2 个进程
        try:
            shm_total = shutil.disk_usage("/dev/shm").total
            args.workers = 2 if shm_total < 2 * 1024**3 else 8
            print(f"==> DataLoader workers: {args.workers}（/dev/shm 大小: {shm_total / 1024**3:.1f}GB）")
        except OSError:
            args.workers = 8
            print("==> DataLoader workers: 8（未检测到 /dev/shm 限制）")

    print(f"==> 数据集: {data}")
    print(f"==> 参数: epochs={args.epochs}, imgsz={args.imgsz}, batch={args.batch}, workers={args.workers}")

    # ---- 加载 COCO 预训练权重（数据量小，必须从预训练开始）----
    model = YOLO("yolov8n.pt")

    # ---- 训练 ----
    model.train(
        data=data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=device,
        patience=30,        # 验证集连续30轮无提升自动停止
        pretrained=True,
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
    print("部署到 Jetson 前可导出 ONNX:")
    print("    yolo export model=runs/desktop_train/weights/best.pt format=onnx imgsz=640")


if __name__ == "__main__":
    main()
