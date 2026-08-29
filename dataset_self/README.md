# 自拍数据集（dataset_self）

- 3 类：**keyboard（键盘）/ nongfu_spring（农夫山泉）/ phone（手机）**
- 共 **596 张**：train 428 / valid 73 / test 95（8:1:1）
- 来源：Roboflow 导出（项目 `2026summer_nongfu_checked`），DJI 实拍画面
- 标注：YOLO 格式 `class cx cy w h`（归一化），多边形已转换为最小外接框
- 图片已压缩至最长边 800px（原图约 1.5GB → 43MB），训练输入 640 足够
- `data.yaml` 使用相对路径，训练时在本目录下运行：

```bash
cd dataset_self
yolo detect train data=data.yaml model=yolov8s.pt epochs=400 imgsz=640 batch=4
```
