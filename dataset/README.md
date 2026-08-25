# 实验一：目标检测与识别 —— 桌面物品数据集

基于 COCO2017 **train2017** 构建的"桌面物品"目标检测数据集（v2 易训练版），共 **6 类物体、约 2300 张图片**，
已转换为 YOLO 格式并按 **8:1:1** 划分为 train / val / test。

## 类别与数量（每类最多取 400 张）

| 类别 | YOLO编号 | 数量 | 说明 |
|---|---|---|---|
| bottle 水瓶 | 0 | 400 | ✅ 达到上限 |
| cup 杯子 | 1 | 400 | ✅ 达到上限 |
| book 书 | 2 | 400 | ✅ 达到上限 |
| clock 时钟 | 3 | 395 | ⚠️ 候选不足400 |
| cell phone 手机 | 4 | 336 | ⚠️ 候选不足400 |
| laptop 笔记本 | 5 | 400 | ✅ 达到上限 |

- 图片总数：约 **2331 张**（train / val / test = 8:1:1）
- 数据筛选策略（"易训练"过滤）：
  - **单物体过滤**：每张图只保留"图中只有一个目标物体"的图片 → 背景干净，模型容易学，acc 高
  - **大物体过滤**：物体面积占画面 ≥ 10% → 特征清晰
  - 不强制要求桌子（否则手机、时钟类图片会严重不足）
- 实验验收要求 ≥ 2 类，本数据集 6 类，满足要求

## 生成流程

1. 下载 COCO2017 train2017 的标注文件（`annotations_trainval2017.zip`）
2. 用 `download_train2017_subset.py` **按需下载**"单物体 + 大物体"的目标图片（约 1~2GB，跳过 18GB 整包下载）
3. **类别筛选**：候选图片数 < 100 的类别自动丢弃
4. 每类最多取 400 张，转换为 YOLO 格式标注（`class_id cx cy w h`，归一化）
5. 全局随机划分 **8:1:1**，并保证每个类别在 train / val / test 中都有样本

## 复现步骤

```bash
# 1. 下载标注文件
#    标注: http://images.cocodataset.org/annotations/annotations_trainval2017.zip  (~250MB)
#    解压后得到 instances_train2017.json

# 2. 只下载需要的图片（约1~2GB，替代18GB整包）
python3 tools/download_train2017_subset.py \
    --annotations instances_train2017.json \
    --out-dir train2017_easy \
    --no-require-table --single-object --min-area-ratio 0.1 \
    --workers 16

# 3. 提取数据集（自动过滤 + 类别筛选 + 数据划分）
python3 tools/extract_coco_desktop.py \
    --annotations instances_train2017.json \
    --images-dir  train2017_easy \
    --out-dir     dataset \
    --per-class 400 --min-per-class 100 \
    --no-require-table --single-object --min-area-ratio 0.1
```

## 训练命令

训练代码在仓库的 `train/` 目录，从这里运行：

```bash
cd ../train
python3 train.py --data ../dataset/data.yaml

# 或直接命令行（yolov8s 时注意 batch 调小防显存溢出）
yolo detect train data=../dataset/data.yaml model=yolov8s.pt epochs=300 imgsz=640 batch=8 patience=60 mixup=0.1
```

> ⚠️ **路径说明**：`data.yaml` 的 `path: ../dataset` 是相对路径，从 `train/` 或 `dataset/` 目录运行均正确；若把 `dataset/` 单独拷贝到其他位置（如虚拟机的 `/root/dataset`），请把 `path` 改为绝对路径。

## 目录结构

```
2026Summer-integrated-robot-grouptask/
├── dataset/                        # 本目录
│   ├── README.md                   # 数据集说明
│   ├── tools/
│   │   ├── extract_coco_desktop.py          # 数据提取脚本（过滤/筛选/划分）
│   │   └── download_train2017_subset.py     # 按需下载脚本（只下需要的图片）
│   ├── data.yaml                   # 训练配置（相对路径）
│   ├── images/{train,val,test}/    # 图片
│   └── labels/{train,val,test}/    # YOLO 标注（与图片同名 .txt）
└── train/                          # 训练代码
    ├── train.py                    # 训练脚本（自动检测GPU/CPU，训练完自动评估）
    └── train.sh                    # 一键训练
```
