#include <ros/ros.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2/utils.h>
#include <mav_msgs/Actuators.h>
#include <nav_msgs/Odometry.h>
#include <trajectory_msgs/MultiDOFJointTrajectoryPoint.h>
#include <eigen3/Eigen/Dense>
#include <algorithm>
#include <cmath>

class ControllerNode {
 public:
  ControllerNode() : e3_(0.0,0.0,1.0), drag_coeff_(0.1,0.1,0.2),
      omega_d_world_(Eigen::Vector3d::Zero()),
      integral_error_(Eigen::Vector3d::Zero()),
      has_desired_(false), has_current_(false) {
    nh_.param("hz", hz_, 100.0);
    nh_.param("kx", kx_, 2.5);
    nh_.param("kv", kv_, 2.0);
    nh_.param("kr", kr_, 4.0);
    nh_.param("komega", komega_, 1.2);
    nh_.param("ki_z", ki_z_, 0.15);
    nh_.param("max_motor_speed", max_motor_speed_, 120.0);
    mass_=1.0; gravity_=9.81; arm_length_=0.3; cf_=1e-3; cd_=1e-5;
    inertia_.setIdentity();

    const double l=arm_length_/std::sqrt(2.0);
    allocation_ << cf_,cf_,cf_,cf_,
                   l*cf_,l*cf_,-l*cf_,-l*cf_,
                   -l*cf_,l*cf_,l*cf_,-l*cf_,
                   cd_,-cd_,cd_,-cd_;

    desired_sub_=nh_.subscribe("desired_state",1,&ControllerNode::onDesiredState,this);
    current_sub_=nh_.subscribe("current_state",1,&ControllerNode::onCurrentState,this);
    motor_pub_=nh_.advertise<mav_msgs::Actuators>("rotor_speed_cmds",1);
    if(hz_<=0.0) hz_=100.0;
    timer_=nh_.createTimer(ros::Duration(1.0/hz_),&ControllerNode::controlLoop,this);
    ROS_INFO("Geometric controller ready: kx=%.2f kv=%.2f kr=%.2f komega=%.2f ki_z=%.2f",
             kx_,kv_,kr_,komega_,ki_z_);
  }

 private:
  void onDesiredState(const trajectory_msgs::MultiDOFJointTrajectoryPoint& msg) {
    if(msg.transforms.empty()) return;
    const auto& tr=msg.transforms.front();
    xd_ << tr.translation.x,tr.translation.y,tr.translation.z;
    vd_.setZero(); ad_.setZero(); omega_d_world_.setZero();
    if(!msg.velocities.empty()) {
      const auto& tw=msg.velocities.front();
      vd_ << tw.linear.x,tw.linear.y,tw.linear.z;
      omega_d_world_.setZero();
    }
    if(!msg.accelerations.empty()) {
      const auto& ac=msg.accelerations.front();
      ad_ << ac.linear.x,ac.linear.y,ac.linear.z;
    }
    tf2::Quaternion q;
    tf2::fromMsg(tr.rotation,q);
    yaw_d_=tf2::getYaw(q);
    has_desired_=true;
  }

  void onCurrentState(const nav_msgs::Odometry& msg) {
    x_ << msg.pose.pose.position.x,msg.pose.pose.position.y,msg.pose.pose.position.z;
    v_ << msg.twist.twist.linear.x,msg.twist.twist.linear.y,msg.twist.twist.linear.z;
    Eigen::Quaterniond q(msg.pose.pose.orientation.w,msg.pose.pose.orientation.x,
                         msg.pose.pose.orientation.y,msg.pose.pose.orientation.z);
    if(q.norm()<1e-8) return;
    q.normalize(); R_=q.toRotationMatrix();
    const Eigen::Vector3d omega_world(msg.twist.twist.angular.x,
                                      msg.twist.twist.angular.y,
                                      msg.twist.twist.angular.z);
    omega_=R_.transpose()*omega_world;
    has_current_=true;
  }

  static Eigen::Vector3d vee(const Eigen::Matrix3d& m) {
    return Eigen::Vector3d(m(2,1),m(0,2),m(1,0));
  }
  static double signedSqrt(double x) {
    return (x>=0.0?1.0:-1.0)*std::sqrt(std::abs(x));
  }

  void controlLoop(const ros::TimerEvent&) {
    if(!has_desired_ || !has_current_) return;
    const double dt=1.0/hz_;
    const Eigen::Vector3d ex=x_-xd_, ev=v_-vd_;
    integral_error_.z()=std::max(-2.0,std::min(2.0,integral_error_.z()+ex.z()*dt));

    const Eigen::Vector3d v_body=R_.transpose()*v_;
    const Eigen::Vector3d drag_body=
        -drag_coeff_.cwiseProduct(v_body.cwiseAbs()).cwiseProduct(v_body);
    Eigen::Vector3d force_des=-kx_*ex-kv_*ev-ki_z_*integral_error_.z()*e3_
        +mass_*gravity_*e3_+mass_*ad_-R_*drag_body;
    if(!force_des.allFinite() || force_des.norm()<1e-6) force_des=mass_*gravity_*e3_;

    const Eigen::Vector3d b3_des=force_des.normalized();
    const Eigen::Vector3d b1_course(std::cos(yaw_d_),std::sin(yaw_d_),0.0);
    Eigen::Vector3d b2_des=b3_des.cross(b1_course);
    if(b2_des.norm()<1e-6) b2_des=b3_des.cross(Eigen::Vector3d(0.0,1.0,0.0));
    b2_des.normalize();
    const Eigen::Vector3d b1_des=b2_des.cross(b3_des).normalized();
    Eigen::Matrix3d R_des;
    R_des.col(0)=b1_des; R_des.col(1)=b2_des; R_des.col(2)=b3_des;

    const Eigen::Matrix3d R_err=R_des.transpose()*R_-R_.transpose()*R_des;
    const Eigen::Vector3d e_R=0.5*vee(R_err);
    const Eigen::Vector3d Omega_d=R_des.transpose()*omega_d_world_;
    const Eigen::Vector3d e_Omega=omega_-R_.transpose()*R_des*Omega_d;

    const double thrust=force_des.dot(R_.col(2));
    const Eigen::Vector3d torque=-kr_*e_R-komega_*e_Omega+
                                  omega_.cross(inertia_*omega_);
    Eigen::Vector4d wrench;
    wrench << thrust,torque.x(),torque.y(),torque.z();
    const Eigen::Vector4d u=allocation_.fullPivLu().solve(wrench);

    mav_msgs::Actuators cmd;
    cmd.header.stamp=ros::Time::now();
    cmd.angular_velocities.resize(4);
    for(int i=0;i<4;++i) {
      const double speed=signedSqrt(u(i));
      cmd.angular_velocities[i]=std::max(-max_motor_speed_,
          std::min(max_motor_speed_,speed));
    }
    motor_pub_.publish(cmd);
  }

  ros::NodeHandle nh_;
  ros::Subscriber desired_sub_,current_sub_;
  ros::Publisher motor_pub_;
  ros::Timer timer_;
  double hz_,kx_,kv_,kr_,komega_,ki_z_,max_motor_speed_;
  double mass_,gravity_,arm_length_,cf_,cd_;
  Eigen::Vector3d e3_,drag_coeff_,x_,v_,omega_,xd_,vd_,ad_,omega_d_world_,integral_error_;
  Eigen::Matrix3d inertia_,R_;
  Eigen::Matrix4d allocation_;
  double yaw_d_=0.0;
  bool has_desired_,has_current_;
};

int main(int argc,char** argv) {
  ros::init(argc,argv,"controller_node");
  ControllerNode node;
  ros::spin();
  return 0;
}
