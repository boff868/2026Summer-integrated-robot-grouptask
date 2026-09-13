"""Task3 真机视觉分拣主节点。

一个物体一遍的流程：

    YOLO 像素框中心  --单应矩阵-->  桌面 XY  --atan2-->  J1  --IK-->  J2/J3/J5
    张开夹爪 -> 抬到上方 -> 下降 -> 夹到最紧 -> 抬起
    -> 固定其他关节、只把 J1 转到落料方位 -> 到落料位上方 -> 下降 -> 松开 -> 退回

真机安全策略：一个目标只要出现 IK 不可达、关节超限、发送失败或未到位，就停止
这个目标的后续动作并尝试回到高位；绝不在位置未知时继续下降或闭合夹爪。

运行：
    ros2 run task3_vision vision_sort                               # 默认只算不动
    ros2 run task3_vision vision_sort --ros-args -p dry_run:=false  # 明确确认后真跑
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from pathlib import Path

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from . import homography as homography_module
from . import ik
from .arm import RealArm
from .detector import DetectionListener

# 检测到的物体离某个落料区中心多近就算"已经分拣过了"
DEFAULT_EXCLUDE_RADIUS_M = 0.09
# 同一个位置重复当成新目标的判定半径（抓失败时物体还在原地）
SAME_TARGET_RADIUS_M = 0.02


# =====================================================================
# 配置
# =====================================================================
def _load_yaml(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _expand(path):
    return Path(os.path.expanduser(os.path.expandvars(str(path))))


class VisionSortNode(Node):
    def __init__(self):
        super().__init__("task3_vision_sort")

        self.declare_parameter("config", "")
        self.declare_parameter("calibration_file", "~/.ros/task3_table_calibration.yaml")
        self.declare_parameter("max_objects", 0)
        self.declare_parameter("passes", 0)
        # 默认只做解算。真机运动必须在命令行明确写 dry_run:=false。
        self.declare_parameter("dry_run", True)
        self.declare_parameter("arm_speed_percent", 0)

        config_path = self.get_parameter("config").value
        if not config_path:
            config_path = (Path(get_package_share_directory("task3_vision"))
                           / "config" / "vision_config.yaml")
        self.config = _load_yaml(config_path)
        self.get_logger().info(f"配置: {config_path}")

        self.robot_conf = self.config.get("robot", {}) or {}
        self.camera_conf = self.config.get("camera", {}) or {}
        self.geometry = self.config.get("geometry", {}) or {}
        self.limits = self.config.get("limits", {}) or {}
        self.safety = self.config.get("safety", {}) or {}
        self.classes = self.config.get("classes", {}) or {}
        self.regions = self.config.get("regions", {}) or {}
        self.run_conf = self.config.get("run", {}) or {}

        # 命令行覆盖
        speed = int(self.get_parameter("arm_speed_percent").value or 0)
        if speed > 0:
            self.robot_conf["arm_speed_percent"] = speed
        self.max_objects = int(self.get_parameter("max_objects").value or 0) \
            or int(self.run_conf.get("max_objects", 6))
        self.passes = int(self.get_parameter("passes").value or 0) \
            or int(self.run_conf.get("passes", 1))
        self.dry_run = bool(self.get_parameter("dry_run").value)

        # 几何参数
        self.base_z = float(self.geometry.get("base_z_m", 0.0))
        self.j4 = float(self.geometry.get("fixed_j4_deg", 0.0))
        self.grip_rad = float(self.geometry.get("ik_grip_rad", 0.14))
        self.pick_pad_z = float(self.geometry.get("pick_pad_z_m", 0.026))
        self.place_pad_z = float(self.geometry.get("place_pad_z_m", 0.030))
        self.above_offset = float(self.geometry.get("above_offset_m", 0.100))
        self.pre_pick_offset = float(self.geometry.get("pre_pick_offset_m", 0.030))
        self.transfer_offset = float(self.geometry.get("transfer_offset_m", 0.170))
        pick_offset = self.geometry.get("pick_xy_offset", [0.0, 0.0]) or [0.0, 0.0]
        self.pick_offset = (float(pick_offset[0]), float(pick_offset[1]))
        self.ik_seed = [float(v) for v in
                        (self.geometry.get("ik_seed_q") or [54.76, -14.71, 51.36])]
        safe = self.geometry.get("rotation_safe_joints_deg") \
            or [0.0, 49.8690, -73.3070, 0.0, 113.4385, 0.0]
        if len(safe) != 6:
            raise ValueError("geometry.rotation_safe_joints_deg 必须正好有 6 个关节角")
        self.rotation_safe = [float(v) for v in safe]

        lower = self.limits.get("lower") or [-160.0, -75.0, -175.0, -155.0, -115.0, -180.0]
        upper = self.limits.get("upper") or [160.0, 120.0, 65.0, 155.0, 115.0, 180.0]
        self.lower = [float(v) for v in lower]
        self.upper = [float(v) for v in upper]

        self.image_size = tuple(self.camera_conf.get("image_size", [640, 480]))
        self.max_age_s = float(self.camera_conf.get("max_age_s", 2.0))
        self.confirm_frames = int(self.camera_conf.get("confirm_frames", 2))
        self.stable_pixel_tolerance = float(
            self.camera_conf.get("stable_pixel_tolerance_px", 8.0))
        self.min_confidence = float(self.camera_conf.get("min_confidence", 0.0))
        pixel_offset = self.camera_conf.get("pixel_offset", [0.0, 0.0]) or [0.0, 0.0]
        self.pixel_offset = (float(pixel_offset[0]), float(pixel_offset[1]))
        self.max_ik_residual = float(self.safety.get("max_ik_residual_m", 0.005))
        radius_limits = self.safety.get("workspace_radius_m", [0.095, 0.255])
        self.min_radius = float(radius_limits[0])
        self.max_radius = float(radius_limits[1])

        # 标定
        self.calibration_file = _expand(self.get_parameter("calibration_file").value)
        self.homography = None
        self._load_calibration()

        # 落料槽位占用情况（只在本次运行内有效）
        self.slot_used = {name: set() for name in self.regions}
        self.attempted = []
        self._unmapped_warned = set()

        self.log_path = _expand(self.run_conf.get("log_path", "~/.ros/task3_vision_sort.jsonl"))
        self.arm = RealArm(self.config, self.get_logger())
        self.detector = DetectionListener(self.config)
        self._finished = False

        self.get_logger().info(
            f"高度参数（相对机械臂底面/桌面）: 抓取 {self.pick_pad_z*1000:.1f}mm, "
            f"放料 {self.place_pad_z*1000:.1f}mm, above +{self.above_offset*1000:.0f}mm, "
            f"转运 +{self.transfer_offset*1000:.0f}mm"
        )
        if self.dry_run:
            self.get_logger().warn("DRY RUN：只解算和打印，不会让机械臂动")

    # ------------------------------------------------------------------
    def _load_calibration(self):
        """桌面标定优先取标定文件；没有就用配置里的 homography。"""
        matrix = None
        if self.calibration_file.exists():
            try:
                data = _load_yaml(self.calibration_file)
                matrix = data.get("homography")
                if matrix:
                    self.get_logger().info(f"已载入标定: {self.calibration_file}")
            except Exception as error:            # noqa: BLE001
                self.get_logger().warn(f"读标定文件失败（继续）: {error}")
        if not matrix:
            matrix = (self.config.get("table_calibration", {}) or {}).get("homography")
        if matrix and len(matrix) == 3 and all(len(row) == 3 for row in matrix):
            self.homography = [[float(v) for v in row] for row in matrix]
        else:
            self.homography = None

    def _wait_for_calibration(self):
        """没有标定就原地等，直到标定文件出现（不是中止，等着就行）。"""
        warned = False
        while rclpy.ok() and self.homography is None:
            if not warned:
                self.get_logger().error(
                    "还没有桌面标定，暂时不动。先跑："
                    "ros2 run task3_vision calibrate_table"
                )
                warned = True
            time.sleep(3.0)
            self._load_calibration()
        if self.homography is not None:
            self.get_logger().info("标定就绪，开始分拣")

    # ------------------------------------------------------------------
    def _log(self, event, **fields):
        record = {"t": round(time.time(), 3), "event": event}
        record.update(fields)
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:                        # noqa: BLE001
            pass
        if event in ("plan", "pick", "place", "result"):
            self.get_logger().info(json.dumps(record, ensure_ascii=False))

    # ------------------------------------------------------------------
    def _region_for(self, item):
        """按类别名找落料区；名字对不上再按 class_id 兜底。"""
        entry = self.classes.get(item["class_name"])
        if isinstance(entry, dict) and entry.get("region") in self.regions:
            return str(entry["region"])
        by_id = self.classes.get("by_id") or {}
        if str(item["class_id"]) in by_id:
            fallback = str(by_id[str(item["class_id"])])
            if fallback in self.regions:
                return fallback
        return None

    def _inside_any_region(self, x, y):
        for name, region in self.regions.items():
            centre = (region or {}).get("centre")
            if centre and len(centre) == 2:
                radius = float(region.get("exclude_radius_m", DEFAULT_EXCLUDE_RADIUS_M))
                if math.hypot(x - float(centre[0]), y - float(centre[1])) <= radius:
                    return True
            # 没配 centre 就用槽位的包围盒兜底
            slots = (region or {}).get("slots") or []
            xs = [float(s[0]) for s in slots]
            ys = [float(s[1]) for s in slots]
            if xs and min(xs) - 0.03 <= x <= max(xs) + 0.03 \
                    and min(ys) - 0.03 <= y <= max(ys) + 0.03:
                return True
        return False

    def _next_slot(self, region_name):
        """按顺序拿一个还没用过的落料槽位。全用满了就循环复用最后一个。"""
        slots = (self.regions.get(region_name) or {}).get("slots") or []
        if not slots:
            centre = (self.regions.get(region_name) or {}).get("centre")
            return (float(centre[0]), float(centre[1])) if centre else None
        used = self.slot_used.setdefault(region_name, set())
        for index, slot in enumerate(slots):
            if index not in used:
                used.add(index)
                return float(slot[0]), float(slot[1])
        fallback = slots[-1]
        self.get_logger().warn(f"落料区 {region_name} 的槽位已用完，复用最后一个")
        return float(fallback[0]), float(fallback[1])

    # ------------------------------------------------------------------
    def _candidates(self):
        """把当前画面里的目标转成桌面坐标并按距离底座的远近排序。"""
        _frames, _stamp, objects = self.detector.snapshot(self.max_age_s)
        if objects is None:
            return None
        found = []
        for item in objects:
            if item["confidence"] < self.min_confidence:
                continue
            pixel = (item["u"] + self.pixel_offset[0],
                     item["v"] + self.pixel_offset[1])
            point = homography_module.project(self.homography, pixel[0], pixel[1])
            if point is None:
                continue
            region = self._region_for(item)
            if region is None:
                # 类别名没配就跳过，但要明确告诉用户实际见到的名字是什么，
                # 否则他没法知道该往 vision_config.yaml 里填什么。
                name = item["class_name"]
                if name not in self._unmapped_warned:
                    self._unmapped_warned.add(name)
                    self.get_logger().error(
                        f"类别 '{name}'（class_id={item['class_id']}）没有配置落料区，"
                        f"跳过。请在 vision_config.yaml 的 classes: 里加上它。"
                        f"目前配的名字 = {sorted(k for k in self.classes if k != 'by_id')}；"
                        f"相机到目前为止报过的名字 = {self.detector.seen_names()}"
                    )
                continue

            class_conf = self.classes.get(item["class_name"])
            class_conf = class_conf if isinstance(class_conf, dict) else {}
            class_offset = class_conf.get("pick_xy_offset", [0.0, 0.0]) or [0.0, 0.0]
            x = point[0] + self.pick_offset[0] + float(class_offset[0])
            y = point[1] + self.pick_offset[1] + float(class_offset[1])
            radius = math.hypot(x, y)
            if not self.min_radius <= radius <= self.max_radius:
                self.get_logger().warn(
                    f"跳过 {item['class_name']}: 半径 {radius:.3f}m 超出工作范围 "
                    f"[{self.min_radius:.3f}, {self.max_radius:.3f}]m")
                continue
            if self._inside_any_region(x, y):
                continue                                    # 已经放进落料区了
            if any(math.hypot(x - ax, y - ay) < SAME_TARGET_RADIUS_M
                   for ax, ay in self.attempted):
                continue                                    # 刚抓过，别重复抓
            pick_z = float(class_conf.get("pick_pad_z_m", self.pick_pad_z))
            found.append({
                "item": item, "x": x, "y": y, "region": region,
                "radius": radius, "pick_z": pick_z,
                "pixel": pixel,
            })
        found.sort(key=lambda candidate: candidate["radius"])
        return found

    def _same_scene(self, previous, current):
        """类别相同且对应框中心移动不超过阈值，才算同一个稳定画面。"""
        if previous is None or len(previous) != len(current):
            return False
        key = lambda item: (item["class_id"], item["u"], item["v"])
        left = sorted(previous, key=key)
        right = sorted(current, key=key)
        for old, new in zip(left, right):
            if old["class_id"] != new["class_id"]:
                return False
            if math.hypot(old["u"] - new["u"], old["v"] - new["v"]) \
                    > self.stable_pixel_tolerance:
                return False
        return True

    def _wait_for_scene(self, timeout_s=10.0):
        """等连续多帧类别和位置都稳定，避免检测框抖动时下手。"""
        previous = None
        stable = 0
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            _frames, _stamp, objects = self.detector.snapshot(self.max_age_s)
            if objects is not None:
                if self._same_scene(previous, objects):
                    stable += 1
                    if stable >= self.confirm_frames:
                        return True
                else:
                    stable = 0
                previous = objects
            time.sleep(0.15)
        return False

    # ------------------------------------------------------------------
    def _build_plan(self, target, slot):
        """构造一个物体的完整动作序列。

        每一步的 ``action``（张开/夹紧）都在**移动到位之后**执行，否则夹爪会在
        半空中先合上，然后带着闭合的爪子压下去。张开夹爪单独作为第一步。
        角度都是"度"。
        """
        ox, oy = target["x"], target["y"]
        bx, by = slot

        object_j1 = math.degrees(math.atan2(oy, ox))
        bin_j1 = math.degrees(math.atan2(by, bx))

        pick_z = float(target.get("pick_z", self.pick_pad_z))
        place_z = self.place_pad_z
        above_z = pick_z + self.above_offset
        pre_z = pick_z + self.pre_pick_offset
        transfer_z = pick_z + self.transfer_offset

        def step(stage, x, y, z, solve_j1, command_j1=None, action=None,
                 move=True, rotate_only=False):
            return {"stage": stage, "x": x, "y": y, "z": z,
                    "solve_j1": solve_j1,
                    "command_j1": solve_j1 if command_j1 is None else command_j1,
                    "action": action, "move": move, "rotate_only": rotate_only}

        return [
            # 先在原地把夹爪张开，然后飞到目标上方（高处走，不贴着桌面横穿）
            step("OPEN_GRIPPER", ox, oy, transfer_z, object_j1,
                 action="open", move=False),
            step("OPEN_AT_TRANSFER", ox, oy, transfer_z, object_j1),
            step("ABOVE_OBJECT", ox, oy, above_z, object_j1),
            step("PRE_PICK", ox, oy, pre_z, object_j1),
            # 到位之后再夹：往死里夹最紧
            step("PICK", ox, oy, pick_z, object_j1, action="close"),
            step("LIFT", ox, oy, above_z, object_j1),
            step("TRANSFER_IN", ox, oy, transfer_z, object_j1),
            # 你说的那一步：其他关节不动，只把 J1 转到落料方位
            step("ROTATE_J1", ox, oy, transfer_z, object_j1,
                 command_j1=bin_j1, rotate_only=True),
            step("BIN_ABOVE", bx, by, place_z + self.above_offset, bin_j1),
            step("BIN_PLACE", bx, by, place_z, bin_j1, action="open"),
            step("BIN_RETREAT", bx, by, place_z + self.above_offset, bin_j1),
        ]

    def _validate_joints(self, arm_deg, stage):
        """超限必须拒绝动作；截断角度会改变末端位置，真机上不可接受。"""
        for index, value in enumerate(arm_deg):
            low, high = self.lower[index], self.upper[index]
            if value < low or value > high:
                self.get_logger().error(
                    f"J{index + 1}={value:.2f} 超出限位 [{low:.0f}, {high:.0f}]，"
                    f"拒绝执行 {stage}"
                )
                return False
        return True

    def _safe_pose(self, heading_deg=0.0):
        pose = list(self.rotation_safe)
        pose[0] = float(heading_deg)
        pose[5] = float(heading_deg)
        return pose

    def _prepare_pick(self, target, label):
        """先收拢抬高，再只转 J1/J6；避免 HOME 直接插值到目标时末端下坠。"""
        heading = math.degrees(math.atan2(target["y"], target["x"]))
        neutral = self._safe_pose(0.0)
        aligned = self._safe_pose(heading)
        if not self._validate_joints(neutral, "SAFE_NEUTRAL") \
                or not self._validate_joints(aligned, "SAFE_ROTATE_TO_OBJECT"):
            return False
        if self.dry_run:
            self._log("step", label=label, stage="SAFE_RAISE_CURRENT_HEADING",
                      joint_deg=neutral, dry_run=True)
            self._log("step", label=label, stage="SAFE_NEUTRAL",
                      joint_deg=neutral, dry_run=True)
            self._log("step", label=label, stage="SAFE_ROTATE_TO_OBJECT",
                      joint_deg=aligned, dry_run=True)
            return True

        measured = self.arm.measured_deg()
        if measured is None:
            self.get_logger().error(f"{label}: 进入抓取前读不到关节角，停止")
            return False
        # 第一步保持当前 J1 方位不变，只收拢/抬高；确认到位后才允许底座旋转。
        raised = self._safe_pose(measured[0])
        if not self._validate_joints(raised, "SAFE_RAISE_CURRENT_HEADING"):
            return False
        if not self.arm.move(raised, f"{label}/SAFE_RAISE_CURRENT_HEADING"):
            return False
        # raised、neutral、aligned 之间只有 J1/J6 不同，旋转时高度不会下降。
        if not self.arm.move(neutral, f"{label}/SAFE_NEUTRAL"):
            return False
        return self.arm.move(aligned, f"{label}/SAFE_ROTATE_TO_OBJECT")

    def _recover_high(self, label):
        """当前物体失败后，保持当前底座方向先抬高收拢，再回中位。"""
        if self.dry_run:
            return
        measured = self.arm.measured_deg()
        if measured is None:
            self.get_logger().error(f"{label}: 无关节反馈，禁止自动恢复")
            return
        raised = self._safe_pose(measured[0])
        if self.arm.move(raised, f"{label}/RECOVER_RAISE"):
            self.arm.move(self._safe_pose(0.0), f"{label}/RECOVER_NEUTRAL")

    def _execute(self, plan, label):
        """执行单个物体；任一步失败就停止该物体，绝不继续下降或夹取。"""
        seed = list(self.ik_seed)
        last_arm_deg = None
        for index, step in enumerate(plan):
            arm_deg = None
            if step["move"]:
                if step.get("rotate_only"):
                    if last_arm_deg is None:
                        self.get_logger().error(f"{label}: 没有上一姿态，无法安全旋转")
                        return False
                    arm_deg = list(last_arm_deg)
                    arm_deg[0] = float(step["command_j1"])
                    arm_deg[5] = float(step["command_j1"])
                    residual = 0.0
                else:
                    q, residual = ik.solve(
                        (step["x"], step["y"], step["z"]), seed, step["solve_j1"],
                        j4_deg=self.j4, grip_rad=self.grip_rad, base_z=self.base_z,
                    )
                    seed = list(q)
                    arm_deg = [
                        step["command_j1"], q[0], q[1], self.j4,
                        q[2], step["command_j1"],
                    ]
                self._log(
                    "step", label=label, stage=step["stage"], index=index + 1,
                    target_xyz=[round(step["x"], 4), round(step["y"], 4),
                                round(step["z"], 4)],
                    j1=round(step["solve_j1"], 3),
                    joint_deg=[round(value, 2) for value in arm_deg],
                    ik_residual_mm=round(residual * 1000, 3),
                    action=step["action"], dry_run=self.dry_run,
                )
                if residual > self.max_ik_residual:
                    self.get_logger().error(
                        f"{label} {step['stage']}: IK 残差 {residual * 1000:.2f}mm "
                        f"超过 {self.max_ik_residual * 1000:.1f}mm，停止当前物体")
                    return False
                if not self._validate_joints(arm_deg, step["stage"]):
                    return False
                if not self.dry_run \
                        and not self.arm.move(arm_deg, f"{label}/{step['stage']}"):
                    return False
                last_arm_deg = list(arm_deg)
            else:
                self._log("step", label=label, stage=step["stage"],
                          index=index + 1, action=step["action"],
                          dry_run=self.dry_run)

            # 夹爪动作一定在移动到位之后
            if step["action"] == "open" and not self.dry_run:
                if not self.arm.open_gripper():
                    return False
            elif step["action"] == "close" and not self.dry_run:
                if not self.arm.close_gripper():
                    return False

            time.sleep(float(self.run_conf.get("step_pause_s", 0.2)))
        return True

    # ------------------------------------------------------------------
    def _connect_with_retry(self):
        """连机械臂。连不上就每 5 秒重试一次——不是中止，是一直等着。"""
        warned = False
        while rclpy.ok():
            try:
                self.arm.connect()
                return True
            except Exception as error:            # noqa: BLE001
                if not warned:
                    self.get_logger().error(
                        f"连接机械臂失败，5 秒后自动重试（不会退出）: {error}")
                    warned = True
                time.sleep(5.0)
        return False

    def run(self):
        """主流程：等标定 -> 连接机械臂 -> 一个物体一个物体地分拣。"""
        self._wait_for_calibration()
        if not self.dry_run and not self._connect_with_retry():
            return

        startup_home = self.run_conf.get("startup_home", True)
        home = self.run_conf.get("home")
        if startup_home and home and len(home) == 6 and not self.dry_run:
            if not self.arm.open_gripper():
                self.get_logger().error("夹爪初始化失败，停止分拣")
                return
            if not self.arm.move([float(v) for v in home], "STARTUP_HOME"):
                self.get_logger().error("HOME 未到位，停止分拣")
                return

        for pass_index in range(1, max(1, self.passes) + 1):
            self.get_logger().info(f"===== 第 {pass_index}/{self.passes} 轮 =====")
            completed = 0
            while completed < self.max_objects:
                self._wait_for_scene()
                candidates = self._candidates()
                if candidates is None:
                    self.get_logger().warn("还没收到检测结果，等相机")
                    time.sleep(1.0)
                    continue
                if not candidates:
                    self.get_logger().info("视野里没有需要分拣的目标了")
                    break

                target = candidates[0]
                slot = self._next_slot(target["region"])
                if slot is None:
                    self.get_logger().warn(
                        f"落料区 {target['region']} 没有配置槽位，跳过这个目标")
                    self.attempted.append((target["x"], target["y"]))
                    continue

                label = f"{target['item']['class_name']}#{completed + 1}"
                self._log(
                    "pick", label=label,
                    class_name=target["item"]["class_name"],
                    confidence=round(target["item"]["confidence"], 3),
                    pixel=[round(v, 1) for v in target["pixel"]],
                    table_xy=[round(target["x"], 4), round(target["y"], 4)],
                    region=target["region"],
                    slot=[round(slot[0], 4), round(slot[1], 4)],
                )
                plan = self._build_plan(target, slot)
                self._log(
                    "plan", label=label,
                    stages=[item["stage"] for item in plan],
                )
                success = False
                try:
                    if self._prepare_pick(target, label):
                        success = self._execute(plan, label)
                except Exception as error:            # noqa: BLE001
                    self.get_logger().error(f"{label} 执行过程出错: {error}")

                self.attempted.append((target["x"], target["y"]))
                if success:
                    self._log("place", label=label, region=target["region"],
                              slot=[round(slot[0], 4), round(slot[1], 4)])
                    completed += 1
                    self.get_logger().info(
                        f"已处理 {completed}/{self.max_objects}: {label}")
                else:
                    self._log("failure", label=label, reason="motion_or_gripper_failed")
                    self.get_logger().error(f"{label} 未完成，停止该物体并尝试回高位")
                    self._recover_high(label)

            self._log("result", pass_index=pass_index, handled=completed,
                      attempted=len(self.attempted))

        self.get_logger().info("全部分拣动作结束")
        self._log("finish", attempted=len(self.attempted))

    def finish(self):
        """收尾。

        默认**不给舵机松力**：松力之后手臂会直接掉下来。只有在配置里显式写
        ``run.release_servos_at_end: true`` 才会松（那是手动搬运前的准备动作）。
        """
        if self._finished:
            return
        self._finished = True
        if not self.dry_run and bool(self.run_conf.get("release_servos_at_end", False)):
            try:
                self.arm.release()
            except Exception:                     # noqa: BLE001
                pass
        self.get_logger().info("节点退出，舵机保持在当前姿态")


# =====================================================================
def main(args=None):
    rclpy.init(args=args)
    node = VisionSortNode()
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    executor.add_node(node.detector)

    worker = threading.Thread(target=_guarded_run, args=(node,), daemon=True)
    worker.start()

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.finish()
        executor.shutdown()
        node.detector.destroy_node()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def _guarded_run(node):
    try:
        node.run()
    except Exception as error:                    # noqa: BLE001
        node.get_logger().error(f"主流程异常: {error}")
        import traceback
        node.get_logger().error(traceback.format_exc())
    finally:
        node.get_logger().info("分拣流程线程结束（节点仍在运行，Ctrl+C 退出）")


if __name__ == "__main__":
    sys.exit(main())
