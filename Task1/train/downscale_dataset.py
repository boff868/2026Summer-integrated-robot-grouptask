#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压缩数据集图片（保持 labels 不变，归一化坐标不受缩放影响）

用法:
  python3 downscale_dataset.py --src dataset_self --out dataset_self_small --max-side 800
"""
import argparse
import os
import shutil
from PIL import Image


def main():
    ap = argparse.ArgumentParser(description="压缩 YOLO 数据集图片")
    ap.add_argument("--src", required=True, help="源数据集目录")
    ap.add_argument("--out", default="dataset_small", help="输出目录")
    ap.add_argument("--max-side", type=int, default=800, help="图片最大边长")
    ap.add_argument("--quality", type=int, default=90, help="JPEG 质量")
    args = ap.parse_args()

    for split in ("train", "valid", "test"):
        si = os.path.join(args.src, split, "images")
        if not os.path.isdir(si):
            continue
        oi = os.path.join(args.out, split, "images")
        ol = os.path.join(args.out, split, "labels")
        os.makedirs(oi, exist_ok=True)
        os.makedirs(ol, exist_ok=True)
        n = 0
        for fn in sorted(os.listdir(si)):
            if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            stem = os.path.splitext(fn)[0]
            im = Image.open(os.path.join(si, fn))
            im.thumbnail((args.max_side, args.max_side), Image.LANCZOS)
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.save(os.path.join(oi, stem + ".jpg"), quality=args.quality)
            lab = os.path.join(args.src, split, "labels", stem + ".txt")
            if os.path.exists(lab):
                shutil.copy(lab, os.path.join(ol, stem + ".txt"))
            n += 1
        print(f"{split}: {n} 张完成")
    shutil.copy(os.path.join(args.src, "data.yaml"), os.path.join(args.out, "data.yaml"))
    print(f"完成: {args.out}/")


if __name__ == "__main__":
    main()
