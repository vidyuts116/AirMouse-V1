#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2_ros/static_transform_broadcaster.h>
#include <tf2/LinearMath/Quaternion.h>
#include <memory>
#include <vector>

class StaticTransformsNode : public rclcpp::Node
{
public:
  StaticTransformsNode() : Node("static_transforms_node")
  {
    broadcaster_ = std::make_shared<tf2_ros::StaticTransformBroadcaster>(this);
    publish_static_transforms();
    RCLCPP_INFO(this->get_logger(), "AirMouse Static Transform Broadcaster Active.");
  }

private:
  void publish_static_transforms()
  {
    std::vector<geometry_msgs::msg::TransformStamped> static_transforms;

    // 1. base_link -> lidar_link (e.g., mounted 0.10 m forward, 0.08 m up)
    geometry_msgs::msg::TransformStamped tf_lidar;
    tf_lidar.header.stamp = this->now();
    tf_lidar.header.frame_id = "base_link";
    tf_lidar.child_frame_id = "lidar_link";
    tf_lidar.transform.translation.x = 0.10;
    tf_lidar.transform.translation.y = 0.0;
    tf_lidar.transform.translation.z = 0.08;
    tf2::Quaternion q_lidar;
    q_lidar.setRPY(0.0, 0.0, 0.0);
    tf_lidar.transform.rotation.x = q_lidar.x();
    tf_lidar.transform.rotation.y = q_lidar.y();
    tf_lidar.transform.rotation.z = q_lidar.z();
    tf_lidar.transform.rotation.w = q_lidar.w();
    static_transforms.push_back(tf_lidar);

    // 2. base_link -> imu_link (co-located near center of mass)
    geometry_msgs::msg::TransformStamped tf_imu;
    tf_imu.header.stamp = this->now();
    tf_imu.header.frame_id = "base_link";
    tf_imu.child_frame_id = "imu_link";
    tf_imu.transform.translation.x = 0.0;
    tf_imu.transform.translation.y = 0.0;
    tf_imu.transform.translation.z = 0.02;
    tf2::Quaternion q_imu;
    q_imu.setRPY(0.0, 0.0, 0.0);
    tf_imu.transform.rotation.x = q_imu.x();
    tf_imu.transform.rotation.y = q_imu.y();
    tf_imu.transform.rotation.z = q_imu.z();
    tf_imu.transform.rotation.w = q_imu.w();
    static_transforms.push_back(tf_imu);

    // 3. base_link -> camera_link (mounted forward-facing)
    geometry_msgs::msg::TransformStamped tf_cam;
    tf_cam.header.stamp = this->now();
    tf_cam.header.frame_id = "base_link";
    tf_cam.child_frame_id = "camera_link";
    tf_cam.transform.translation.x = 0.12;
    tf_cam.transform.translation.y = 0.0;
    tf_cam.transform.translation.z = 0.04;
    tf2::Quaternion q_cam;
    q_cam.setRPY(0.0, 0.0, 0.0);
    tf_cam.transform.rotation.x = q_cam.x();
    tf_cam.transform.rotation.y = q_cam.y();
    tf_cam.transform.rotation.z = q_cam.z();
    tf_cam.transform.rotation.w = q_cam.w();
    static_transforms.push_back(tf_cam);

    broadcaster_->sendTransform(static_transforms);
  }

  std::shared_ptr<tf2_ros::StaticTransformBroadcaster> broadcaster_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<StaticTransformsNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
