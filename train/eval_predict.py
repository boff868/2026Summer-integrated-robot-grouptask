#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评估 YOLO 预测结果 vs 真值 (IoU>=0.5 命中)
用法: python3 train/eval_predict.py [预测labels目录] [真值labels目录] [最低置信度]
      （在仓库根目录运行，默认评估 dataset_self 的 test 集）
"""
import os, glob, sys

PRED_DIR = sys.argv[1] if len(sys.argv) > 1 else "runs/predict/labels"
GT_DIR   = sys.argv[2] if len(sys.argv) > 2 else "dataset_self/test/labels"
MIN_CONF = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
IOU_THR  = 0.5
CLASSES  = {0: "keyboard", 1: "nongfu_spring", 2: "phone"}

def parse(path, has_conf, min_conf=0.0):
    boxes = []
    if not os.path.exists(path):
        return boxes
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) < 5:
                continue
            cls = int(p[0])
            cx, cy, w, h = map(float, p[1:5])
            conf = float(p[5]) if has_conf and len(p) > 5 else 1.0
            if conf < min_conf:
                continue
            boxes.append([cls, cx, cy, w, h, conf])
    return boxes

def iou(a, b):
    ax1, ay1 = a[1]-a[3]/2, a[2]-a[4]/2
    ax2, ay2 = a[1]+a[3]/2, a[2]+a[4]/2
    bx1, by1 = b[1]-b[3]/2, b[2]-b[4]/2
    bx2, by2 = b[1]+b[3]/2, b[2]+b[4]/2
    ix1, iy1 = max(ax1,bx1), max(ay1,by1)
    ix2, iy2 = min(ax2,bx2), min(ay2,by2)
    inter = max(0, ix2-ix1) * max(0, iy2-iy1)
    union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter/union if union > 0 else 0

tp, fp, fn = {c:0 for c in CLASSES}, {c:0 for c in CLASSES}, {c:0 for c in CLASSES}
fp_cases, fn_cases, low_conf = [], [], []

for gt_path in sorted(glob.glob(os.path.join(GT_DIR, "*.txt"))):
    name = os.path.basename(gt_path)[:-4]
    gts   = parse(gt_path, has_conf=False)
    preds = parse(os.path.join(PRED_DIR, name + ".txt"), has_conf=True, min_conf=MIN_CONF)
    matched_gt, matched_pr = set(), set()
    for gi, g in enumerate(gts):
        best_i, best_iou = -1, 0.0
        for pi, p in enumerate(preds):
            if pi in matched_pr or p[0] != g[0]:
                continue
            v = iou(g, p)
            if v > best_iou:
                best_iou, best_i = v, pi
        if best_i >= 0 and best_iou >= IOU_THR:
            matched_gt.add(gi); matched_pr.add(best_i)
            tp[g[0]] += 1
            if preds[best_i][5] < 0.4:
                low_conf.append((name, CLASSES[g[0]], round(preds[best_i][5], 2)))
    for gi, g in enumerate(gts):
        if gi not in matched_gt:
            fn[g[0]] += 1
            fn_cases.append((name, CLASSES[g[0]]))
    for pi, p in enumerate(preds):
        if pi not in matched_pr:
            fp[p[0]] += 1
            fp_cases.append((name, CLASSES[p[0]], round(p[5], 2)))

print(f"\n[阈值 conf>={MIN_CONF}]")
print("=" * 62)
print(f"{'类别':<14}{'TP':>6}{'FP':>6}{'FN':>6}{'Precision':>11}{'Recall':>10}{'正确识别率':>11}")
print("=" * 62)
tot_gt = tot_fp = 0
for c in CLASSES:
    gt_n = tp[c] + fn[c]
    prec = tp[c]/(tp[c]+fp[c]) if tp[c]+fp[c] else 0
    rec  = tp[c]/gt_n if gt_n else 0
    tot_gt += gt_n; tot_fp += fp[c]
    print(f"{CLASSES[c]:<14}{tp[c]:>6}{fp[c]:>6}{fn[c]:>6}{prec:>11.3f}{rec:>10.3f}{rec:>11.3f}")
print("=" * 62)
overall = sum(tp.values())/tot_gt if tot_gt else 0
n_img = len(glob.glob(os.path.join(GT_DIR, "*.txt")))
print(f"整体正确识别率: {overall:.3f} ({sum(tp.values())}/{tot_gt})   误检总数: {sum(fp.values())} (平均每图 {tot_fp/max(n_img,1):.2f})")
print("=" * 62)

if low_conf:
    print(f"\n[提示] {len(low_conf)} 个命中但置信度<0.4 的边界情况:")
    for name, cls, conf in low_conf[:10]:
        print(f"  {name}: {cls} conf={conf}")
print(f"\n[误检案例] {len(fp_cases)} 个:")
for name, cls, conf in fp_cases[:20]:
    print(f"  {name}: 检出 {cls} conf={conf}")
if len(fp_cases) > 20: print(f"  ... 其余 {len(fp_cases)-20} 个略")
print(f"\n[漏检案例] {len(fn_cases)} 个:")
for name, cls in fn_cases[:20]:
    print(f"  {name}: 漏检 {cls}")
if len(fn_cases) > 20: print(f"  ... 其余 {len(fn_cases)-20} 个略")
print("\n达标判断:", "通过(≥80%)" if overall >= 0.8 else "未达 80%,需改进")
