#!/usr/bin/env python3
import math
import rospy
from geometry_msgs.msg import Quaternion, Transform, Twist, Vector3
from trajectory_msgs.msg import MultiDOFJointTrajectoryPoint

def main():
    rospy.init_node("static_pose_publisher")
    x = rospy.get_param("~x", 0.0)
    y = rospy.get_param("~y", -0.24)
    z = rospy.get_param("~z", 2.0)
    yaw = rospy.get_param("~yaw", -0.817)
    q = Quaternion(0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))
    point = MultiDOFJointTrajectoryPoint()
    point.transforms = [Transform(Vector3(x, y, z), q)]
    point.velocities = [Twist()]
    point.accelerations = [Twist()]
    pub = rospy.Publisher("desired_state", MultiDOFJointTrajectoryPoint, queue_size=1)
    rate = rospy.Rate(100)
    while not rospy.is_shutdown():
        pub.publish(point)
        rate.sleep()

if __name__ == "__main__":
    main()
