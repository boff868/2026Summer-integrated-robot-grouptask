#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实桌面照片 → 自动标注脚本
============================================
给"真实桌上的物体"照片自动生成 YOLO 标注，可直接并入训练集做微调，
解决"COCO 图片与真实桌面场景差距大"导致的验收识别率不高问题。

用法：
    python3 auto_label_photos.py \
        --source /root/photos \
        --model /root/2026Summer-integrated-robot-grouptask/train/runs/detect/runs/desktop_train-3/weights/best.pt \
        --out-dir /root/real_photos

输出：
    <out-dir>/
    ├── images/   原图（加 real_ 前缀，用于训练）
    ├── labels/   对应 YOLO 标注（class_id cx cy w h）
    └── preview/  带框预览图（人工检查用）

之后：
    1) 检查 preview/ 里的带框图，删掉打错/漏打的图
    2) 并入训练集：
       cp -r <out-dir>/images/* /root/dataset_single/images/train/
       cp -r <out-dir>/labels/* /root/dataset_single/labels/train/
    3) 重新训练：
       python3 train.py --data /root/dataset_single/data.yaml
"""

import argparse
import os
import shutil
from pathlib import Path

from ultralytics import YOLO


def parse_args():
    p = argparse.ArgumentParser(description="用训练好的模型给真实照片自动打框")
    p.add_argument("--source", required=True, help="真实照片文件夹（jpg/png）")
    p.add_argument("--model", required=True, help="训练好的 best.pt 路径")
    p.add_argument("--out-dir", default="real_photos", help="输出目录")
    p.add_argument("--conf", type=float, default=0.35, help="置信度阈值（默认0.35，可调低到0.25多打框）")
    p.add_argument("--imgsz", type=int, default=640, help="推理尺寸")
    p.add_argument("--classes", default=None, help="只保留的类别编号，逗号分隔，如 '0,1'（默认全部）")
    return p.parse_args()


def main():
    args = parse_args()
    if not os.path.isdir(args.source):
        print(f"[错误] 源目录不存在: {args.source}")
        return
    if not os.path.exists(args.model):
        print(f"[错误] 模型不存在: {args.model}")
        return

    print(f"==> 加载模型: {args.model}")
    model = YOLO(args.model)
    print(f"==> 模型类别: {model.names}")

    classes = [int(c) for c in args.classes.split(",")] if args.classes else None

    # 推理：保存标注(txt) + 带框预览图
    pred = os.path.join(args.out_dir, "predict")
    model.predict(
        source=args.source,
        conf=args.conf,
        imgsz=args.imgsz,
        classes=classes,
        save=True,          # 带框预览图
        save_txt=True,      # YOLO 格式标注
        save_conf=True,
        project=pred,
        name="run",
        exist_ok=True,
    )

    # 整理输出：images=原图, labels=标注, preview=带框图
    img_out = os.path.join(args.out_dir, "images")
    lbl_out = os.path.join(args.out_dir, "labels")
    pre_out = os.path.join(args.out_dir, "preview")
    for d in (img_out, lbl_out, pre_out):
        os.makedirs(d, exist_ok=True)

    src_lbl = os.path.join(pred, "run", "labels")
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    count = 0
    for f in sorted(Path(args.source).iterdir()):
        if f.suffix.lower() not in exts or not f.is_file():
            continue
        lbl = os.path.join(src_lbl, f.stem + ".txt")
        if os.path.exists(lbl) and os.path.getsize(lbl) > 0:
            shutil.copyfile(f, os.path.join(img_out, "real_" + f.name))
            shutil.copyfile(lbl, os.path.join(lbl_out, "real_" + f.stem + ".txt"))
            count += 1

    # 带框预览图（人工检查）
    for f in sorted(Path(pred, "run").glob("*.jpg")):
        shutil.copyfile(f, os.path.join(pre_out, f.name))

    print(f"✅ 完成！成功标注 {count} 张真实照片 -> {os.path.abspath(args.out_dir)}")
    print("下一步：")
    print("  1) 检查 preview/ 带框图和 labels/，删掉打错/漏打的")
    print("  2) 并入训练集:")
    print(f"     cp -r {os.path.abspath(img_out)}/* /root/dataset_single/images/train/")
    print(f"     cp -r {os.path.abspath(lbl_out)}/* /root/dataset_single/labels/train/")
    print("  3) 重新训练: python3 train.py --data /root/dataset_single/data.yaml")


if __name__ == "__main__":
    main()
