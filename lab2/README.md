# Lab 2 — ROS, tf and homogeneous transformations

Two-drone scenario used to study rigid transformations with ROS `tf`:

- **AV1** moves on a circle `o1 = [cos t, sin t, 0]` with `yaw = t`, so its body *y* axis stays tangent to the trajectory and its *z* axis stays parallel to the world *z* axis.
- **AV2** moves on the parabola `o2 = [sin t, 0, cos 2t]` (i.e. `z = 1 - 2x²`) with pure translation.
- The motion of AV2 expressed in AV1's frame is an ellipse with semi-axes `1/2` and `√5/2`, lying in the plane `z = 1 + 2y`.

## Contents

| Path | Description |
| --- | --- |
| `two_drones_pkg/` | ROS 2 package: `frames_publisher_node` (broadcasts `world → av1`, `world → av2`), `plots_publisher_node` (looks up the relative transform and draws the three trajectories), launch file, rviz config, quadrotor mesh |
| `ROS1版本/` | ROS 1 (Noetic) implementations of the same two nodes |
| `report/` | Lab report (PDF) |

## Run (ROS 2)

```bash
cd two_drones_pkg
colcon build --packages-select two_drones_pkg
source install/setup.bash
ros2 launch two_drones_pkg two_drones.launch.yaml            # dynamic
ros2 launch two_drones_pkg two_drones.launch.yaml static:=true  # static
```

## Run (ROS 1)

```bash
# place ROS1版本/frames_publisher_node.cpp and plots_publisher_node.cpp
# into two_drones_pkg/src, then
catkin build two_drones_pkg
roslaunch two_drones_pkg two_drones.launch
```
