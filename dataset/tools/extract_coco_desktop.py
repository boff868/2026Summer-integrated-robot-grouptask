#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COCO 桌面物品子集提取脚本（仅保留"桌上物品"图片）
========================================================
从 COCO2017 数据集中提取桌面物品的图片和标注，自动转换为 YOLO 格式，
并按 8:1:1 划分 train / val / test。

与普通提取的区别：
1. 【桌子过滤】只保留同时含有 "dining table"(桌子) 标注的图片 —— 这样图片里的
   目标物体基本都出现在桌面上，符合"识别桌子上的物品"的实验要求。
2. 【类别自动筛选】图片数量不足 --min-per-class 的类别会被自动丢弃
   （数据太少的类别训练不出好效果，宁可不要）。
3. 全局随机划分 + 每类保底，保证每个类别在 train/val/test 中都有样本。

用法示例：
    python extract_coco_desktop.py \
        --annotations instances_val2017.json \
        --images-dir  val2017 \
        --out-dir     desktop6 \
        --per-class   183 \
        --min-per-class 30

参数说明：
    --annotations     COCO 标注文件路径 (instances_*.json)
    --images-dir      COCO 图片目录 (解压后的 val2017/ 或 train2017/)
    --out-dir         输出目录，生成 images/ + labels/ + data.yaml
    --per-class       每类最多取多少张图片 (默认 183)
    --min-per-class   类别最少图片数，低于此数自动丢弃 (默认 30)
    --min-classes     至少保留多少个类别 (默认 4)
    --split           划分比例 train,val,test (默认 0.8,0.1,0.1)
    --seed            随机种子 (默认 42，保证结果可复现)

数据下载：
    val2017 图片:   http://images.cocodataset.org/zips/val2017.zip     (~1GB)
    train2017 图片: http://images.cocodataset.org/zips/train2017.zip   (~18GB)
    标注文件:       http://images.cocodataset.org/annotations/annotations_trainval2017.zip  (~250MB)

输出结构：
    <out-dir>/
    ├── data.yaml        # ultralytics 训练配置文件
    ├── images/train|val|test/
    └── labels/train|val|test/   # YOLO格式: class_id cx cy w h (归一化)

依赖：仅 Python 标准库。
"""

import argparse
import json
import os
import random
import shutil
from collections import Counter, defaultdict

# 全部候选桌面物品类别（脚本会自动丢弃图片不足的类别）
TARGET_CLASSES = [
    "bottle",        # 0 水瓶
    "cup",           # 1 杯子
    "book",          # 2 书
    "clock",         # 3 时钟
    "cell phone",    # 4 手机
    "laptop",        # 5 笔记本
]
TABLE_CLASS_NAME = "dining table"   # 用"桌子"做过滤依据


def parse_args():
    p = argparse.ArgumentParser(description="从COCO提取桌面物品子集(仅桌上物品)并转YOLO格式")
    p.add_argument("--annotations", required=True, help="COCO标注文件 instances_*.json")
    p.add_argument("--images-dir", required=True, help="COCO图片目录（解压后的val2017/或train2017/）")
    p.add_argument("--out-dir", default="desktop6", help="输出目录")
    p.add_argument("--per-class", type=int, default=183, help="每类最多取多少张图片")
    p.add_argument("--min-per-class", type=int, default=30, help="类别最少图片数，不足自动丢弃")
    p.add_argument("--min-classes", type=int, default=4, help="至少保留的类别数")
    p.add_argument("--classes", default=None,
                   help="只保留的类别，逗号分隔，如 'laptop,cell phone,clock'（默认全部6类）")
    p.add_argument("--single-object", action="store_true",
                   help="只保留\"单物体\"图片（图中只有一个目标物体实例，场景更干净，acc 通常更高）")
    p.add_argument("--min-area-ratio", type=float, default=None,
                   help="只保留物体面积占比≥该值的标注（如 0.1=物体占图10%以上，画面更干净更好学）")
    p.add_argument("--no-require-table", dest="require_table", action="store_false",
                   default=True, help="关闭桌子过滤（默认开启）")
    p.add_argument("--split", default="0.8,0.1,0.1", help="train,val,test 划分比例")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    return p.parse_args()


def load_coco(ann_path):
    """读取COCO标注，返回 (图片元信息, 每图目标框, 含桌子的图片id集合)。"""
    with open(ann_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cat_id_to_name = {c["id"]: c["name"] for c in data["categories"]}
    name_to_idx = {name: i for i, name in enumerate(TARGET_CLASSES)}
    cat_id_to_idx = {
        cid: name_to_idx[name]
        for cid, name in cat_id_to_name.items()
        if name in name_to_idx
    }
    table_cat_ids = {c["id"] for c in data["categories"] if c["name"] == TABLE_CLASS_NAME}

    img_meta = {img["id"]: img for img in data["images"]}
    img_boxes = defaultdict(list)      # image_id -> [(class_idx, bbox)]
    img_has_table = set()              # 含桌子的图片id
    for ann in data["annotations"]:
        cid = ann["category_id"]
        if cid in table_cat_ids:
            img_has_table.add(ann["image_id"])
            continue
        if cid not in cat_id_to_idx:
            continue
        bbox = ann["bbox"]  # COCO: [x, y, w, h]
        if bbox[2] <= 0 or bbox[3] <= 0:
            continue
        img_boxes[ann["image_id"]].append((cat_id_to_idx[cid], bbox))

    return img_meta, img_boxes, img_has_table


def main():
    args = parse_args()
    random.seed(args.seed)

    # 可选：限定类别子集（在读取标注前生效，保持 TARGET_CLASSES 顺序）
    if args.classes:
        wanted = [c.strip() for c in args.classes.split(",")]
        unknown = [c for c in wanted if c not in TARGET_CLASSES]
        if unknown:
            print(f"错误: 未知类别 {unknown}，可选: {TARGET_CLASSES}")
            exit(1)
        TARGET_CLASSES[:] = [c for c in TARGET_CLASSES if c in wanted]
        print(f"==> 限定类别 ({len(TARGET_CLASSES)} 类): {TARGET_CLASSES}")
    tr, va, te = [float(x) for x in args.split.split(",")]
    if abs(tr + va + te - 1.0) > 1e-6:
        print("错误：划分比例之和必须等于 1")
        exit(1)

    # 清空旧的输出目录，避免重复运行产生残留文件
    if os.path.exists(args.out_dir):
        shutil.rmtree(args.out_dir)
        print(f"已清空旧的输出目录: {args.out_dir}")

    print(f"[1/4] 读取 COCO 标注: {args.annotations}")
    img_meta, img_boxes, img_has_table = load_coco(args.annotations)
    print(f"      图片总数: {len(img_meta)}，含目标类别标注的图片: {len(img_boxes)}")

    # ---- 桌子过滤 ----
    if args.require_table:
        before = len(img_boxes)
        img_boxes = {iid: boxes for iid, boxes in img_boxes.items() if iid in img_has_table}
        print(f"      [桌子过滤] 含桌子的图片 {len(img_has_table)} 张；"
              f"目标物体在桌边场景的图片: {before} -> {len(img_boxes)}")

    # ---- 大物体过滤：只保留物体面积占比达标的标注（画面干净，更好学）----
    if args.min_area_ratio:
        before = sum(len(v) for v in img_boxes.values())
        img_wh = {iid: (meta["width"], meta["height"]) for iid, meta in img_meta.items()}
        new_boxes = {}
        for iid, boxes in img_boxes.items():
            w, h = img_wh[iid]
            keep = [b for b in boxes if (b[1][2] * b[1][3]) / (w * h) >= args.min_area_ratio]
            if keep:
                new_boxes[iid] = keep
        img_boxes = new_boxes
        after = sum(len(v) for v in img_boxes.values())
        print(f"      [大物体过滤] 面积占比≥{args.min_area_ratio:.0%}: 标注 {before} -> {after}")

    # ---- 单物体过滤：每张图只保留一个目标物体实例 ----
    if args.single_object:
        before = len(img_boxes)
        img_boxes = {iid: boxes for iid, boxes in img_boxes.items() if len(boxes) == 1}
        print(f"      [单物体过滤] 只保留\"图中只有一个目标物体\"的图片: {before} -> {len(img_boxes)}")

    # ---- 类别筛选：自动丢弃图片不足的类别 ----
    cand_counts = Counter()
    for iid, boxes in img_boxes.items():
        for ci in {ci for ci, _ in boxes}:
            cand_counts[ci] += 1
    keep_idx = [ci for ci in range(len(TARGET_CLASSES)) if cand_counts[ci] >= args.min_per_class]
    if len(keep_idx) < args.min_classes:
        print(f"      ⚠️ 警告: 图片数≥{args.min_per_class} 的类别只有 {len(keep_idx)} 个"
              f"（要求至少 {args.min_classes} 个），请考虑调低 --min-per-class")
    remap = {old: new for new, old in enumerate(keep_idx)}
    kept_names = [TARGET_CLASSES[ci] for ci in keep_idx]
    dropped = [TARGET_CLASSES[ci] for ci in range(len(TARGET_CLASSES)) if ci not in remap]
    print(f"      ✅ 保留类别 ({len(kept_names)} 类): {', '.join(kept_names)}")
    if dropped:
        print(f"      ❌ 丢弃类别 (图片<{args.min_per_class}张): {', '.join(dropped)}")
    # 重映射类别编号，只保留保留类
    img_boxes = {iid: [(remap[ci], box) for ci, box in boxes if ci in remap]
                 for iid, boxes in img_boxes.items() if any(ci in remap for ci, _ in boxes)}

    # ---- 每类候选池（cap 到 per_class）----
    class_pool = defaultdict(list)
    for iid, boxes in img_boxes.items():
        for ci in {ci for ci, _ in boxes}:
            class_pool[ci].append(iid)

    print(f"[2/4] 各类别候选图片数（每类最多取 {args.per_class} 张）:")
    for ci, name in enumerate(kept_names):
        pool = class_pool[ci]
        random.shuffle(pool)
        n = min(len(pool), args.per_class)
        flag = "" if len(pool) >= args.per_class else f"  ⚠️ 不足 {args.per_class} 张！"
        print(f"      {name:12s}(class {ci}): 候选 {len(pool):4d} 张，取 {n} 张{flag}")
        class_pool[ci] = pool[:n]

    # ---- 全局随机划分 + 每类保底 ----
    print(f"[3/4] 按 {tr:.0%}/{va:.0%}/{te:.0%} 划分数据")
    img_classes = {iid: {ci for ci, _ in boxes} for iid, boxes in img_boxes.items()}
    all_images = sorted({iid for pool in class_pool.values() for iid in pool})
    random.shuffle(all_images)
    n_total = len(all_images)
    n_train = round(n_total * tr)
    n_val = round(n_total * va)
    n_test = n_total - n_train - n_val
    splits = {
        "train": all_images[:n_train],
        "val": all_images[n_train:n_train + n_val],
        "test": all_images[n_train + n_val:],
    }

    def ensure_presence(split_name):
        """保证每个类别在指定集合中至少有一张图（从 train 挪）"""
        for ci in range(len(kept_names)):
            if any(ci in img_classes[iid] for iid in splits[split_name]):
                continue
            cand = [iid for iid in splits["train"] if ci in img_classes[iid]]
            if cand:
                moved = cand[0]
                splits["train"].remove(moved)
                splits[split_name].append(moved)
                print(f"      保底: {kept_names[ci]} 在 {split_name} 无样本，已从 train 挪入 1 张")

    ensure_presence("val")
    ensure_presence("test")

    for s in ("train", "val", "test"):
        print(f"      → {s:6s}: {len(splits[s])} 张图片")
    print("      各类别在各集合的图片数:")
    for ci, name in enumerate(kept_names):
        counts = [sum(1 for iid in splits[s] if ci in img_classes[iid]) for s in ("train", "val", "test")]
        print(f"      {name:12s}: train {counts[0]:4d} | val {counts[1]:3d} | test {counts[2]:3d}")

    # ---- 生成 YOLO 格式数据集 ----
    print(f"[4/4] 生成 YOLO 数据集 -> {args.out_dir}")
    missing_total = 0
    for split_name in splits:
        img_out = os.path.join(args.out_dir, "images", split_name)
        lbl_out = os.path.join(args.out_dir, "labels", split_name)
        os.makedirs(img_out, exist_ok=True)
        os.makedirs(lbl_out, exist_ok=True)

        for iid in splits[split_name]:
            meta = img_meta[iid]
            src = os.path.join(args.images_dir, meta["file_name"])
            dst = os.path.join(img_out, meta["file_name"])
            if not os.path.exists(src):
                missing_total += 1
                if missing_total <= 10:
                    print(f"      ⚠️ 图片缺失，跳过: {src}")
                continue
            shutil.copyfile(src, dst)

            # 写 YOLO 标注: class_id cx cy w h (归一化)
            w_img, h_img = float(meta["width"]), float(meta["height"])
            lines = []
            for ci, (x, y, w, h) in img_boxes[iid]:
                xc = max(0.0, min(1.0, (x + w / 2.0) / w_img))
                yc = max(0.0, min(1.0, (y + h / 2.0) / h_img))
                wn = max(0.0, min(1.0, w / w_img))
                hn = max(0.0, min(1.0, h / h_img))
                lines.append(f"{ci} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}")
            lbl_path = os.path.join(lbl_out, os.path.splitext(meta["file_name"])[0] + ".txt")
            with open(lbl_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")  # 末尾换行，避免 cat 拼接时合并成一行

    if missing_total:
        print(f"⚠️ 共 {missing_total} 张图片缺失！请先运行 download_train2017_subset.py 补下载后重新提取")
    else:
        print("✅ 图片全部找到，无缺失")

    # ---- data.yaml ----
    yaml_path = os.path.join(args.out_dir, "data.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {os.path.abspath(args.out_dir)}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("test: images/test\n\n")
        f.write(f"nc: {len(kept_names)}\n")
        f.write("names:\n")
        for i, name in enumerate(kept_names):
            f.write(f"  {i}: {name}\n")

    print(f"✅ 完成！数据集在: {os.path.abspath(args.out_dir)}")
    print(f"   训练命令: yolo detect train data={os.path.abspath(yaml_path)} model=yolov8n.pt epochs=150 imgsz=640")


if __name__ == "__main__":
    main()
