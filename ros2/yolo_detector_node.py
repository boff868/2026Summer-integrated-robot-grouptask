#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目标检测 ROS2 发布节点
=====================
本地摄像头实时采集画面 → YOLOv8 推理 → 检测结果以 JSON 发布到 ROS2 话题，
同时弹出窗口显示标注画面（检测框 / 类别 / 置信度 / FPS）。

发布话题
--------
    /detections/json   std_msgs/String

    JSON 结构:
    {
        "fps": 12.5,
        "object_count": 2,
        "objects": [
            {
                "class_id": 0,
                "class_name": "keyboard",
                "confidence": 0.91,
                "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 300}
            },
            ...
        ]
    }

运行参数（--ros-args -p 键:=值）
--------------------------------
    model_path   权重文件路径（默认 /home/nvidia/best_gjs_1.pt）
    camera_id    摄像头设备号（默认 2，对应 /dev/video2）
    conf         置信度阈值（默认 0.7）
    imgsz        推理分辨率（默认 640）

使用方法
--------
    python3 yolo_detector_node.py --ros-args \
        -p model_path:=/home/nvidia/best_gjs_1.pt \
        -p camera_id:=2 -p conf:=0.7

    # 另开终端查看发布内容
    ros2 topic echo /detections/json

说明
----
- 推理使用 FP16 半精度（device=0，Jetson GPU 环境）
- 检测画面窗口内按 q 退出
"""

import json
import time

import cv2
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from ultralytics import YOLO


class ObjectDetectorNode(Node):
    """摄像头目标检测与发布节点"""

    def __init__(self):
        super().__init__("object_detector")

        # ---------- 参数 ----------
        self.declare_parameter("model_path", "/home/nvidia/best_gjs_1.pt")
        self.declare_parameter("camera_id", 2)
        self.declare_parameter("conf", 0.7)
        self.declare_parameter("imgsz", 640)

        model_path = self.get_parameter("model_path").value
        camera_id = self.get_parameter("camera_id").value
        self.conf_thr = self.get_parameter("conf").value
        self.infer_size = self.get_parameter("imgsz").value

        # ---------- 加载模型 ----------
        self.get_logger().info(f"加载模型: {model_path}")
        self.model = YOLO(model_path)
        self.get_logger().info(
            f"模型就绪，类别: {list(self.model.names.values())}")

        # ---------- 打开摄像头 ----------
        self.cam = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
        if not self.cam.isOpened():
            self.get_logger().error(f"无法打开摄像头 /dev/video{camera_id}")
            raise RuntimeError(f"camera /dev/video{camera_id} open failed")
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.get_logger().info(f"摄像头 /dev/video{camera_id} 已就绪 (640x480)")

        # ---------- 发布器 ----------
        self.pub = self.create_publisher(String, "/detections/json", 10)

        # ---------- FPS 统计 ----------
        self._prev_ts = time.perf_counter()
        self._fps_ema = 0.0

    # ------------------------------------------------------------------
    def _infer(self, frame):
        """单帧 YOLO 推理"""
        results = self.model.predict(
            source=frame,
            imgsz=self.infer_size,
            conf=self.conf_thr,
            device=0,
            half=True,
            verbose=False,
        )
        return results[0]

    # ------------------------------------------------------------------
    @staticmethod
    def _collect(result):
        """把推理结果整理为可序列化的检测列表"""
        objects = []
        for box in result.boxes:
            cls_id = int(box.cls[0].item())
            score = float(box.conf[0].item())
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].cpu().tolist()]
            objects.append({
                "class_id": cls_id,
                "class_name": result.names[cls_id],
                "confidence": round(score, 3),
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            })
        return objects

    # ------------------------------------------------------------------
    def _refresh_fps(self):
        """计算并平滑当前帧率"""
        now = time.perf_counter()
        dt = now - self._prev_ts
        self._prev_ts = now
        if dt > 1e-6:
            instant = 1.0 / dt
            self._fps_ema = self._fps_ema * 0.9 + instant * 0.1
        return round(self._fps_ema, 1)

    # ------------------------------------------------------------------
    def _publish(self, objects, fps):
        """JSON 编码并发布检测结果"""
        payload = {
            "fps": fps,
            "object_count": len(objects),
            "objects": objects,
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.pub.publish(msg)
        self.get_logger().info(f"发布 {len(objects)} 个目标 | FPS={fps}")

    # ------------------------------------------------------------------
    @staticmethod
    def _display(annotated, objects, fps):
        """本地窗口显示标注画面"""
        cv2.putText(annotated, f"FPS: {fps:.1f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(annotated, f"ROS2: {len(objects)} objects", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow("Object Detection", annotated)

    # ------------------------------------------------------------------
    def run(self):
        """主循环：采集 → 推理 → 发布 → 显示"""
        self.get_logger().info("节点启动，画面窗口内按 q 退出")
        try:
            while rclpy.ok():
                ok, frame = self.cam.read()
                if not ok or frame is None:
                    self.get_logger().warn("采集帧失败，跳过本帧")
                    continue

                result = self._infer(frame)
                objects = self._collect(result)
                fps = self._refresh_fps()
                self._publish(objects, fps)

                annotated = result.plot()
                self._display(annotated, objects, fps)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.get_logger().info("收到退出指令，正在关闭")
                    break
        except KeyboardInterrupt:
            self.get_logger().info("手动中断")
        finally:
            self.cam.release()
            cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args)
    node = ObjectDetectorNode()
    try:
        node.run()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
