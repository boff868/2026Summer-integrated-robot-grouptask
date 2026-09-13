# Task3：充电头 / 订书钉外壳视觉分拣

这套代码连接本仓库 Task1 的 YOLO 节点与 MechArm 270 Pi：

`摄像头 -> YOLO /detections/json -> 桌面标定 -> 动态 XY -> IK -> 高位抓取/分类`

## 重要前提

- 摄像头必须固定在桌面上方，标定后不能移动；如果摄像头装在机械臂末端，不能直接使用本方案。
- 第一次运行必须保持急停可用、速度不超过 10%，并使用 `dry_run:=true`。
- `config/vision_config.yaml` 里的两个分类区域坐标和两类物体抓取高度必须按真机测量。
- 默认夹爪命令为 `0`，即夹到最紧。

## 1. Jetson 拉取并进入工作区

```bash
cd ~
git clone https://github.com/boff868/2026Summer-integrated-robot-grouptask.git
cd ~/2026Summer-integrated-robot-grouptask/Task3/ros2_ws
```

如果已经克隆过：

```bash
cd ~/2026Summer-integrated-robot-grouptask
git pull
cd Task3/ros2_ws
```

## 2. 安装依赖并编译

```bash
source /opt/ros/humble/setup.bash
python3 -m pip install --user pymycobot PyYAML
colcon build --symlink-install --packages-select task3_vision
source install/setup.bash
```

## 3. 启动 Task1 摄像头和 YOLO（终端一）

先检查摄像头编号：

```bash
v4l2-ctl --list-devices
```

启动检测：

```bash
cd ~/2026Summer-integrated-robot-grouptask/Task1
source /opt/ros/humble/setup.bash
python3 ros2/yolo_detector_node.py --ros-args \
  -p model_path:=models/best_gjs_1.pt \
  -p camera_id:=2 \
  -p conf:=0.70
```

日志里的模型类别必须包含充电头和订书钉外壳。它们的名字需要与
`Task3/ros2_ws/src/task3_vision/config/vision_config.yaml` 中 `classes` 的 key 完全一致。

## 4. 检查检测话题（终端二）

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /detections/json --once
```

输出中应包含 `class_id`、`class_name`、`confidence` 和 `bbox`。

## 5. 编写真机配置

编辑：

```bash
nano ~/2026Summer-integrated-robot-grouptask/Task3/ros2_ws/src/task3_vision/config/vision_config.yaml
```

至少确认：

- `robot.robot_ip` 是机械臂实际 IP。
- `classes.charger` 和 `classes.staple_shell` 与 YOLO 实际类别名一致。
- 每类的 `pick_pad_z_m` 是夹爪橡胶垫中心的抓取高度。
- `regions.A.slots` 是充电头放置点。
- `regions.B.slots` 是订书钉外壳放置点。
- `run.home` 和 `geometry.rotation_safe_joints_deg` 已在低速下验证不会碰桌面或分类箱。

改完后重新编译并加载：

```bash
cd ~/2026Summer-integrated-robot-grouptask/Task3/ros2_ws
colcon build --symlink-install --packages-select task3_vision
source install/setup.bash
```

## 6. 桌面标定（终端二）

在桌面抓取范围铺开设置至少 5 个标记点，用尺子测量每点相对机械臂底座的 X、Y，单位米：

```bash
ros2 run task3_vision calibrate_table
```

按提示逐点放置物体并输入 X、Y。标定结果写入：

```text
~/.ros/task3_table_calibration.yaml
```

最大重投影误差应不超过 5 mm；移动摄像头或机械臂底座后必须重新标定。

## 7. 只解算、不让机械臂运动（终端二）

```bash
ros2 launch task3_vision task3_vision.launch.py \
  dry_run:=true max_objects:=2
```

检查日志：

- 识别类别与目标区域是否正确。
- `table_xy` 是否和尺子测量位置接近。
- 每一步 `ik_residual_mm` 是否小于 5 mm。
- 所有关节是否处于配置限位内。
- 动作顺序是否包含 `SAFE_RAISE_CURRENT_HEADING`、`SAFE_NEUTRAL`、
  `SAFE_ROTATE_TO_OBJECT`、`TRANSFER_IN`、`ROTATE_J1`。

## 8. 第一次低速空载运动

先移走物体和分类箱，保持急停可用：

```bash
ros2 launch task3_vision task3_vision.launch.py \
  dry_run:=false arm_speed_percent:=5 max_objects:=1
```

确认机械臂从 HOME 先收拢抬高，再只转 J1/J6，没有下坠或扫过桌面。

## 9. 单物体抓取

放一个物体，分类箱保持在已经测量的区域：

```bash
ros2 launch task3_vision task3_vision.launch.py \
  dry_run:=false arm_speed_percent:=8 max_objects:=1
```

若抓取中心固定偏移，调整该类别的 `pick_xy_offset`；若夹爪过高或碰桌面，调整该类别的 `pick_pad_z_m`，每次只改 2 mm 左右。

## 10. 正式分拣六个物体

单物体两种类别都通过以后：

```bash
ros2 launch task3_vision task3_vision.launch.py \
  dry_run:=false arm_speed_percent:=10 max_objects:=6
```

运行日志保存在：

```text
~/.ros/task3_vision_sort.jsonl
```

## 安全行为

- IK 残差大于 5 mm：拒绝执行该目标。
- 任何关节超限：拒绝动作，不会截断后继续。
- 机械臂未到位或反馈丢失：停止当前物体，禁止继续下降或夹紧。
- 失败恢复时保持当前 J1 方向先抬高，再回中位。
- 结束时默认保持舵机受力，不会自动松力导致机械臂掉落。
