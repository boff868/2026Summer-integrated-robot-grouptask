#include <tf2/LinearMath/Quaternion.h>
#include <tf2_ros/transform_broadcaster.h>

#include <geometry_msgs/msg/transform_stamped.hpp>
#include <chrono>
#include <cmath>
#include <iostream>
#include <memory>
#include <rclcpp/create_timer.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp/timer.hpp>

class FramesPublisherNode : public rclcpp::Node {
  rclcpp::Time startup_time;

  rclcpp::TimerBase::SharedPtr heartbeat;

  // TODO: Declare a std::unique_ptr<tf2_ros::TransformBroadcaster>
  std::unique_ptr<tf2_ros::TransformBroadcaster> br_;

 public:
  FramesPublisherNode() : Node("frames_publisher_node") {
    // NOTE: This method is run once, when the node is launched.

    // TODO: Instantiate the Transform Broadcaster
    br_ = std::make_unique<tf2_ros::TransformBroadcaster>(this);

    startup_time = now();
    heartbeat = create_timer(std::chrono::milliseconds(20),
                             std::bind(&FramesPublisherNode::onPublish, this));
    heartbeat->reset();
  }

  void onPublish() {
    // NOTE: This method is called at 50Hz, due to the timer created on line 25.

    // 1. Compute time elapsed in seconds since the node has been started
    double time = (this->now() - startup_time).seconds();

    // Here we declare two geometry_msgs::msg::TransformStamped objects, which
    // need to be populated
    geometry_msgs::msg::TransformStamped world_T_av1;
    geometry_msgs::msg::TransformStamped world_T_av2;

    // 2. Populate the two transforms for the AVs, using the variable "time".
    //
    // AV1: origin [cos(time), sin(time), 0.0], yaw = time (roll = pitch = 0).
    //      This keeps the body y axis tangent to the circular trajectory and
    //      the body z axis parallel to the world z axis.
    world_T_av1.header.stamp = this->now();
    world_T_av1.header.frame_id = "world";
    world_T_av1.child_frame_id = "av1";
    world_T_av1.transform.translation.x = std::cos(time);
    world_T_av1.transform.translation.y = std::sin(time);
    world_T_av1.transform.translation.z = 0.0;
    tf2::Quaternion q_av1;
    q_av1.setRPY(0.0, 0.0, time);  // roll = 0, pitch = 0, yaw = time
    world_T_av1.transform.rotation.x = q_av1.x();
    world_T_av1.transform.rotation.y = q_av1.y();
    world_T_av1.transform.rotation.z = q_av1.z();
    world_T_av1.transform.rotation.w = q_av1.w();

    // AV2: origin [sin(time), 0.0, cos(2*time)], rotation is irrelevant.
    world_T_av2.header.stamp = this->now();
    world_T_av2.header.frame_id = "world";
    world_T_av2.child_frame_id = "av2";
    world_T_av2.transform.translation.x = std::sin(time);
    world_T_av2.transform.translation.y = 0.0;
    world_T_av2.transform.translation.z = std::cos(2.0 * time);
    world_T_av2.transform.rotation.w = 1.0;  // identity rotation

    // 3. Publish the transforms.
    br_->sendTransform(world_T_av1);
    br_->sendTransform(world_T_av2);
  }
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<FramesPublisherNode>());
  rclcpp::shutdown();
  return 0;
}
