#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 COCO train2017 只下载需要的图片（含目标类别 + 桌子），
避免下载整个 18GB 的 train2017.zip。

用法：
    python3 download_train2017_subset.py \
        --annotations /root/coco/annotations/instances_train2017.json \
        --out-dir /root/coco/train2017_subset \
        --workers 16

参数：
    --annotations  COCO 标注文件 instances_*.json
    --out-dir      图片保存目录（下载后可直接给 extract_coco_desktop.py 用）
    --workers      并发下载线程数（默认 16）
    --base-url     默认 http://images.cocodataset.org/train2017/
    --dry-run      只统计需要下载的图片，不实际下载（用于先看数量）
"""

import argparse
import json
import os
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# 与提取脚本共用同一份类别列表，避免两边不一致导致图片缺失
from extract_coco_desktop import TARGET_CLASSES

BASE_URL = "http://images.cocodataset.org/train2017/"
TARGETS = set(TARGET_CLASSES)
TABLE_NAME = "dining table"


def parse_args():
    p = argparse.ArgumentParser(description="只下载COCO train2017中含桌子的目标物体图片")
    p.add_argument("--annotations", required=True, help="COCO标注文件")
    p.add_argument("--out-dir", default="train2017_subset", help="图片保存目录")
    p.add_argument("--workers", type=int, default=16, help="并发下载线程数")
    p.add_argument("--base-url", default=BASE_URL, help="图片基础URL")
    p.add_argument("--dry-run", action="store_true", help="只统计不下载")
    return p.parse_args()


def main():
    args = parse_args()

    print(f"[1/3] 读取标注: {args.annotations}")
    with open(args.annotations, encoding="utf-8") as f:
        data = json.load(f)

    cat_name_to_id = {c["name"]: c["id"] for c in data["categories"]}
    target_ids = {cat_name_to_id[n] for n in TARGETS if n in cat_name_to_id}
    table_id = cat_name_to_id[TABLE_NAME]

    img_file = {img["id"]: img["file_name"] for img in data["images"]}
    img_target = {}      # image_id -> {category_id,...}
    img_has_table = set()

    for ann in data["annotations"]:
        cid = ann["category_id"]
        iid = ann["image_id"]
        if cid == table_id:
            img_has_table.add(iid)
        elif cid in target_ids:
            img_target.setdefault(iid, set()).add(cid)

    # 需要下载的图片 = 同时含目标类别 和 桌子
    need = {iid for iid in img_target if iid in img_has_table}

    name_by_id = {c["id"]: c["name"] for c in data["categories"]}
    per_class = Counter()
    for iid in need:
        for cid in img_target[iid]:
            per_class[cid] += 1

    print(f"      需要下载的图片: {len(need)} 张")
    for cid in sorted(target_ids):
        print(f"      {name_by_id[cid]:12s}: {per_class[cid]} 张")

    if args.dry_run:
        print("      [dry-run] 结束，未下载任何文件")
        return

    print(f"[2/3] 开始下载到 {args.out_dir} (workers={args.workers}) ...")
    os.makedirs(args.out_dir, exist_ok=True)
    failed = []

    def download_one(iid):
        fname = img_file[iid]
        dst = os.path.join(args.out_dir, fname)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return None  # 已存在，跳过
        url = args.base_url + fname
        for attempt in range(3):
            try:
                urllib.request.urlretrieve(url, dst)
                return None
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    return (fname, str(e))

    futs = {iid: None for iid in need}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fmap = {ex.submit(download_one, iid): iid for iid in need}
        for i, fut in enumerate(as_completed(fmap), 1):
            r = fut.result()
            if r:
                failed.append(r)
            if i % 500 == 0 or i == len(fmap):
                print(f"      {i}/{len(fmap)} 完成...")

    print(f"[3/3] 完成！成功 {len(fmap) - len(failed)} 张，失败 {len(failed)} 张")
    for fname, err in failed[:10]:
        print(f"      失败: {fname} ({err})")
    if not failed:
        print("✅ 全部下载成功，接下来可以运行提取脚本 extract_coco_desktop.py")


if __name__ == "__main__":
    main()
