#include <ros/ros.h>
#include <tf2_ros/transform_broadcaster.h>
#include <tf2/LinearMath/Quaternion.h>

#include <cmath>
#include <iostream>

class FramesPublisherNode {
 private:
  ros::NodeHandle nh;
  ros::Time startup_time;

  ros::Timer heartbeat;
  // *** FILL IN *** instantiate a transform broadcaster
  tf2_ros::TransformBroadcaster br;

 public:
  FramesPublisherNode() : br() {
    // NOTE: This method is run once, when the node is launched.
    startup_time = ros::Time::now();
    heartbeat =
        nh.createTimer(ros::Duration(0.02), &FramesPublisherNode::onPublish, this);
    heartbeat.start();
  }

  void onPublish(const ros::TimerEvent&) {
    // NOTE: This method is called at 50Hz, due to the timer created on line 16.

    // 1. Compute time elapsed in seconds since the node has been started
    double time = (ros::Time::now() - startup_time).toSec();  // *** FILL IN ***

    // Here we declare two geometry_msgs::TransformStamped objects, which need to be
    // populated
    geometry_msgs::TransformStamped AV1World;
    geometry_msgs::TransformStamped AV2World;
    // NOTE: fields in a ros message default to zero, so we set an identity transform by
    //       setting just the w component of the rotation
    AV1World.transform.rotation.w = 1.0;
    AV2World.transform.rotation.w = 1.0;

    // 2. Populate the two transforms for the AVs, using the variable "time"
    //    computed above.
    //
    // AV1: origin [cos(time), sin(time), 0.0], yaw = time (roll = pitch = 0).
    //      With yaw = time, the body y axis stays tangent to the circular
    //      trajectory and the body z axis stays parallel to the world z axis.
    AV1World.header.stamp = ros::Time::now();
    AV1World.header.frame_id = "world";
    AV1World.child_frame_id = "av1";
    AV1World.transform.translation.x = std::cos(time);
    AV1World.transform.translation.y = std::sin(time);
    AV1World.transform.translation.z = 0.0;
    tf2::Quaternion q_av1;
    q_av1.setRPY(0.0, 0.0, time);  // roll = 0, pitch = 0, yaw = time
    AV1World.transform.rotation.x = q_av1.x();
    AV1World.transform.rotation.y = q_av1.y();
    AV1World.transform.rotation.z = q_av1.z();
    AV1World.transform.rotation.w = q_av1.w();

    // AV2: origin [sin(time), 0.0, cos(2*time)], rotation is irrelevant
    //      (kept as identity).
    AV2World.header.stamp = ros::Time::now();
    AV2World.header.frame_id = "world";
    AV2World.child_frame_id = "av2";
    AV2World.transform.translation.x = std::sin(time);
    AV2World.transform.translation.y = 0.0;
    AV2World.transform.translation.z = std::cos(2.0 * time);

    // 3. Publish the transforms
    br.sendTransform(AV1World);  // *** FILL IN ***
    br.sendTransform(AV2World);  // *** FILL IN ***
  }
};

int main(int argc, char** argv) {
  ros::init(argc, argv, "frames_publisher_node");
  FramesPublisherNode node;
  ros::spin();
  return 0;
}
