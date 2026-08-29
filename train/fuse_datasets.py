#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据融合脚本：将两个 YOLO 数据集按类名对齐后合并，用于融合训练。

用法:
  python3 fuse_datasets.py --src-a dataset --src-b dataset_self \
      --out dataset_fused --classes keyboard nongfu_spring phone

说明:
  - 支持两种数据集布局:
      1) <dir>/<split>/images + labels        (Roboflow 导出风格)
      2) <dir>/images/<split> + labels/<split> (本仓库 dataset/ 风格)
      3) 扁平布局 <dir>/images + labels       (自动视为 train)
  - 按类名映射（自动忽略不在目标类列表中的类别），重写 label 类别编号
  - 图片与标签统一加 a_/b_ 前缀，避免同名冲突
"""
import argparse
import os
import shutil
import yaml

IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


def load_names(data_yaml):
    """读取 data.yaml 中的类名列表"""
    with open(data_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    names = cfg["names"]
    if isinstance(names, dict):
        names = [names[i] for i in sorted(names)]
    return list(names)


def detect_splits(ds_dir):
    """返回 {split: (images_dir, labels_dir)}；兼容两种布局"""
    splits = {}
    for sp in ("train", "valid", "test"):
        img_d = os.path.join(ds_dir, sp, "images")
        if os.path.isdir(img_d):
            splits[sp] = (img_d, os.path.join(ds_dir, sp, "labels"))
            continue
        img_d2 = os.path.join(ds_dir, "images", sp)
        if os.path.isdir(img_d2):
            splits[sp] = (img_d2, os.path.join(ds_dir, "labels", sp))
    if not splits:
        img_d = os.path.join(ds_dir, "images")
        if os.path.isdir(img_d):
            splits["train"] = (img_d, os.path.join(ds_dir, "labels"))
    return splits


def convert_label(lab_path, src_names, target_names):
    """返回转换后的标注行，只保留目标类别"""
    rows = []
    if not os.path.exists(lab_path):
        return rows
    name2idx = {name: i for i, name in enumerate(target_names)}
    with open(lab_path, encoding="utf-8") as f:
        for line in f:
            p = line.split()
            if len(p) < 5:
                continue
            cls = int(p[0])
            name = src_names[cls] if cls < len(src_names) else None
            if name in name2idx:
                coords = p[1:5]
                rows.append(f"{name2idx[name]} {' '.join(coords)}\n")
    return rows


def process_source(src_dir, prefix, target_names, out_dir):
    """处理单个数据集，把标注转换并拷贝到输出目录"""
    splits = detect_splits(src_dir)
    if not splits:
        print(f"[跳过] {src_dir}: 未找到 images 目录")
        return
    src_names = load_names(os.path.join(src_dir, "data.yaml"))
    kept = {c: 0 for c in target_names}
    for split, (img_d, lab_d) in splits.items():
        out_img_d = os.path.join(out_dir, split, "images")
        out_lab_d = os.path.join(out_dir, split, "labels")
        os.makedirs(out_img_d, exist_ok=True)
        os.makedirs(out_lab_d, exist_ok=True)
        n_imgs = 0
        for fn in sorted(os.listdir(img_d)):
            if not fn.lower().endswith(IMG_EXTS):
                continue
            stem = os.path.splitext(fn)[0]
            rows = convert_label(os.path.join(lab_d, stem + ".txt"), src_names, target_names)
            if not rows:
                continue  # 无目标类别标注的图片不保留
            ext = os.path.splitext(fn)[1].lower()
            new_stem = f"{prefix}_{stem}"
            shutil.copy(os.path.join(img_d, fn), os.path.join(out_img_d, new_stem + ext))
            with open(os.path.join(out_lab_d, new_stem + ".txt"), "w", encoding="utf-8") as f:
                f.writelines(rows)
            n_imgs += 1
            for r in rows:
                kept[target_names[int(r.split()[0])]] += 1
        print(f"  [{prefix}] {split}: {n_imgs} 张图")
    print(f"  [{prefix}] 目标类别标注数: " + ", ".join(f"{c}={kept[c]}" for c in target_names))


def main():
    ap = argparse.ArgumentParser(description="两个 YOLO 数据集按类名融合")
    ap.add_argument("--src-a", required=True, help="数据集 A 目录（含 data.yaml）")
    ap.add_argument("--src-b", required=True, help="数据集 B 目录（含 data.yaml）")
    ap.add_argument("--out", default="dataset_fused", help="输出融合数据集目录")
    ap.add_argument("--classes", nargs="+", default=["keyboard", "nongfu_spring", "phone"],
                    help="融合后的目标类别")
    args = ap.parse_args()

    print(f"数据集A类名: {load_names(os.path.join(args.src_a, 'data.yaml'))}")
    print(f"数据集B类名: {load_names(os.path.join(args.src_b, 'data.yaml'))}")
    print(f"融合目标类别: {args.classes}")

    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(args.out, exist_ok=True)

    process_source(args.src_a, "a", args.classes, args.out)
    process_source(args.src_b, "b", args.classes, args.out)

    data_yaml = {
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(args.classes),
        "names": list(args.classes),
    }
    with open(os.path.join(args.out, "data.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml, f, allow_unicode=True, sort_keys=False)

    print(f"\n完成: 融合数据集已生成到 {args.out}/")
    print("训练命令示例:")
    print(f"  cd {os.path.abspath(args.out)} && yolo detect train data=data.yaml model=yolov8s.pt epochs=400 imgsz=640 batch=4")


if __name__ == "__main__":
    main()
