#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标签规范化：把多边形标注行转为方框，保证所有 label 都是 5 列格式
用法: python3 fix_labels.py /root/dataset_XBY
"""
import os
import sys


def fix_dir(labels_dir):
    n_files = n_lines = n_poly = 0
    if not os.path.isdir(labels_dir):
        return 0, 0, 0
    for fn in os.listdir(labels_dir):
        if not fn.endswith(".txt"):
            continue
        path = os.path.join(labels_dir, fn)
        with open(path) as f:
            lines = f.read().splitlines()
        out = []
        changed = False
        for line in lines:
            p = line.split()
            if len(p) < 5:
                continue
            coords = list(map(float, p[1:]))
            if len(coords) > 4:  # 多边形 -> 最小外接方框
                xs = coords[0::2]
                ys = coords[1::2]
                x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
                cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
                out.append(f"{p[0]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                changed = True
                n_poly += 1
            else:  # 已是方框
                out.append(f"{p[0]} {' '.join(f'{v:.6f}' for v in coords)}")
            n_lines += 1
        if changed:
            with open(path, "w") as f:
                f.write("\n".join(out) + "\n")
            n_files += 1
    return n_files, n_lines, n_poly


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "/root/dataset_XBY"
    total_files = total_poly = 0
    for sp in ("train", "valid", "test"):
        d = os.path.join(root, sp, "labels")
        nf, nl, np_ = fix_dir(d)
        total_files += nf
        total_poly += np_
        print(f"  {sp}: 修改 {nf} 个文件, {nl} 行标注, 转换 {np_} 条多边形")
    print(f"\n完成: 共修改 {total_files} 个文件, 转换 {total_poly} 条多边形为方框")


if __name__ == "__main__":
    main()
