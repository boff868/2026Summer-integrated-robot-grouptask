# 实验一：目标检测与识别 —— 桌面物品数据集

基于 COCO2017 **val2017** 构建的"桌面物品"目标检测数据集，共 **280 张图片、4 类物体**，
已转换为 YOLO 格式并按 **8:1:1** 划分为 train / val / test。

## 类别与数量

| 类别 | YOLO编号 | train | val | test | 合计 |
|---|---|---|---|---|---|
| bottle 水瓶 | 0 | 94 | 11 | 15 | 120 |
| cup 杯子 | 1 | 151 | 16 | 20 | 187 |
| book 书 | 2 | 38 | 6 | 3 | 47 |
| cell phone 手机 | 3 | 24 | 5 | 2 | 31 |

- 图片总数：280 张（train 224 / val 28 / test 28）
- 标注实例总数：1135 个
- 所有图片均为"目标物体出现在餐桌上（dining table）"的场景，符合"识别桌上物品"的实验要求

## 生成流程

1. 下载 COCO2017 val2017（图片 + 标注）
2. **桌子过滤**：只保留同时含有 `dining table` 标注的图片，确保物体都在桌面上
3. **类别筛选**：候选图片数 < 30 的类别自动丢弃（最终保留 4 类）
4. 每类最多取 183 张，转换为 YOLO 格式标注（`class_id cx cy w h`，归一化）
5. 全局随机划分 **8:1:1**，并保证每个类别在 train / val / test 中都有样本

## 复现步骤

```bash
# 1. 下载 COCO val2017
#    图片: http://images.cocodataset.org/zips/val2017.zip     (~1GB)
#    标注: http://images.cocodataset.org/annotations/annotations_trainval2017.zip  (~250MB)

# 2. 运行提取脚本（在解压目录的同级执行）
python3 tools/extract_coco_desktop.py \
    --annotations instances_val2017.json \
    --images-dir  val2017 \
    --out-dir     desktop6 \
    --per-class   183 \
    --min-per-class 30
```

## 训练命令

训练代码在仓库的 `train/` 目录，从这里运行：

```bash
# 一键训练（自动检测 GPU/CPU，用 COCO 预训练权重）
python3 ../train/train.py --data data.yaml

# 或者直接命令行
yolo detect train data=data.yaml model=yolov8n.pt epochs=150 imgsz=640
```

训练结果在 `runs/desktop_train/weights/best.pt`（相对运行目录），训练脚本会自动在测试集上评估并输出 mAP50。

## 目录结构

```
2026Summer-integrated-robot-grouptask/
├── dataset/                        # 本目录
│   ├── README.md                   # 数据集说明
│   ├── tools/
│   │   └── extract_coco_desktop.py # 数据提取脚本（COCO → YOLO，含桌子过滤/类别筛选/数据划分）
│   ├── data.yaml                   # 训练配置（相对路径，可直接使用）
│   ├── images/{train,val,test}/    # 图片
│   └── labels/{train,val,test}/    # YOLO 标注（与图片同名 .txt）
└── train/                          # 训练代码
    ├── train.py                    # 训练脚本（自动检测GPU/CPU，训练+测试集评估）
    └── train.sh                    # 一键训练（自动装依赖）
```
