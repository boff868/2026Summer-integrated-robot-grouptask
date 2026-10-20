#!/usr/bin/env python3
"""Replay measured VNAV Lab 3 circle telemetry as RViz2 markers."""

import bisect
import csv
import time

import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import Point
from std_msgs.msg import ColorRGBA
from visualization_msgs.msg import Marker, MarkerArray
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster
from geometry_msgs.msg import TransformStamped


CSV_PATH = "/root/lab3_rviz/circle_moderate2.csv"
FRAME = "map"
TOPIC = "/visualization_marker_array"
PUBLISH_HZ = 20.0
PREROLL_S = 2.0
TAIL_S = 3.0


def color(r, g, b, a=1.0):
    return ColorRGBA(r=float(r), g=float(g), b=float(b), a=float(a))


class CircleReplay(Node):
    def __init__(self):
        super().__init__("lab3_circle_rviz_replay")
        with open(CSV_PATH, newline="") as source:
            self.rows = list(csv.DictReader(source))
        if len(self.rows) < 2:
            raise RuntimeError(f"Need at least two trajectory rows in {CSV_PATH}")

        self.t0 = float(self.rows[0]["t_s"])
        self.times = [float(row["t_s"]) - self.t0 for row in self.rows]
        self.duration = self.times[-1]
        self.publisher = self.create_publisher(MarkerArray, TOPIC, 10)
        self.static_tf = StaticTransformBroadcaster(self)
        frame = TransformStamped()
        frame.header.stamp = self.get_clock().now().to_msg()
        frame.header.frame_id = "world"
        frame.child_frame_id = FRAME
        frame.transform.rotation.w = 1.0
        self.static_tf.sendTransform(frame)
        self.started = time.monotonic() + PREROLL_S
        self.done_at = None
        self.timer = self.create_timer(1.0 / PUBLISH_HZ, self.step)
        self.get_logger().info(
            f"Loaded {len(self.rows)} measured samples ({self.duration:.2f} s); "
            f"publishing RViz markers on {TOPIC}"
        )

    def make_marker(self, ns, marker_id, marker_type, scale, rgba, *, frame=FRAME):
        marker = Marker()
        marker.header.frame_id = frame
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = ns
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.scale.x, marker.scale.y, marker.scale.z = scale
        marker.color = rgba
        marker.lifetime.sec = 0
        marker.lifetime.nanosec = 0
        return marker

    @staticmethod
    def point(row, actual):
        keys = ("x_m", "y_m", "z_m") if actual else ("xd_m", "yd_m", "zd_m")
        return Point(
            x=float(row[keys[0]]),
            y=float(row[keys[1]]),
            z=float(row[keys[2]]),
        )

    def line(self, ns, marker_id, points, rgba, width):
        marker = self.make_marker(
            ns, marker_id, Marker.LINE_STRIP, (width, 0.0, 0.0), rgba
        )
        marker.points = points
        return marker

    def step(self):
        now = time.monotonic()
        if now < self.started:
            elapsed = 0.0
        else:
            elapsed = min(now - self.started, self.duration)
            if elapsed >= self.duration:
                if self.done_at is None:
                    self.done_at = now
                elif now - self.done_at >= TAIL_S:
                    rclpy.shutdown()
                    return

        idx = min(max(bisect.bisect_right(self.times, elapsed) - 1, 0), len(self.rows) - 1)
        row = self.rows[idx]
        desired = [self.point(sample, False) for sample in self.rows]
        actual = [self.point(sample, True) for sample in self.rows[: idx + 1]]
        actual_now = actual[-1]
        desired_now = self.point(row, False)

        items = MarkerArray()

        # The full desired loop and the measured path accumulated to the current pose.
        items.markers.append(
            self.line("reference", 0, desired, color(0.20, 0.95, 0.50), 0.055)
        )
        items.markers.append(
            self.line("measured_trail", 0, actual, color(0.15, 0.62, 1.0), 0.075)
        )

        # A small quadrotor glyph: body, arms, and four rotor caps.
        body = self.make_marker(
            "quadrotor", 1, Marker.CUBE, (0.32, 0.32, 0.14), color(1.0, 0.45, 0.08)
        )
        body.pose.position = actual_now
        items.markers.append(body)

        arm = self.make_marker(
            "quadrotor", 2, Marker.LINE_LIST, (0.055, 0.0, 0.0), color(0.12, 0.16, 0.22)
        )
        arm.pose.position = actual_now
        for dx, dy in ((-0.30, -0.30), (0.30, 0.30), (-0.30, 0.30), (0.30, -0.30)):
            arm.points.extend(
                [
                    Point(x=-dx, y=-dy, z=0.0),
                    Point(x=dx, y=dy, z=0.0),
                ]
            )
        items.markers.append(arm)

        rotors = self.make_marker(
            "quadrotor", 3, Marker.SPHERE_LIST, (0.15, 0.15, 0.035), color(0.18, 0.22, 0.28)
        )
        rotors.pose.position = actual_now
        for dx, dy in ((-0.30, -0.30), (0.30, 0.30), (-0.30, 0.30), (0.30, -0.30)):
            rotors.points.append(Point(x=dx, y=dy, z=0.03))
        items.markers.append(rotors)

        # Show the instantaneous position error as a thin yellow segment.
        error = self.make_marker(
            "tracking_error", 0, Marker.LINE_LIST, (0.035, 0.0, 0.0), color(1.0, 0.86, 0.12)
        )
        error.points = [actual_now, desired_now]
        items.markers.append(error)

        self.publisher.publish(items)


def main():
    rclpy.init()
    node = CircleReplay()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
