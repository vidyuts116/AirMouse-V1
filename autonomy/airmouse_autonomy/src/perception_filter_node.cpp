#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <pcl_conversions/pcl_conversions.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl/filters/voxel_grid.h>

class PerceptionFilterNode : public rclcpp::Node
{
public:
  PerceptionFilterNode() : Node("perception_filter_node")
  {
    // Subscribe to raw sensor data
    sub_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
      "/sensors/lidar/points_raw", 10, std::bind(&PerceptionFilterNode::cloud_callback, this, std::placeholders::_1));
    
    // Publish filtered data for SLAM and Planners
    pub_ = this->create_publisher<sensor_msgs::msg::PointCloud2>(
      "/perception/filtered_points", 10);
      
    RCLCPP_INFO(this->get_logger(), "Perception Filter Active. Voxelizing 3D point clouds at 10cm resolution.");
  }

private:
  void cloud_callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg)
  {
    // 1. Convert standard ROS msg to PCL cloud format
    pcl::PCLPointCloud2::Ptr pcl_pc2(new pcl::PCLPointCloud2());
    pcl_conversions::toPCL(*msg, *pcl_pc2);

    // 2. Apply Voxel Grid filter (compress points into 10cm cubes)
    pcl::PCLPointCloud2::Ptr cloud_filtered(new pcl::PCLPointCloud2());
    pcl::VoxelGrid<pcl::PCLPointCloud2> sor;
    sor.setInputCloud(pcl_pc2);
    sor.setLeafSize(0.1f, 0.1f, 0.1f);
    sor.filter(*cloud_filtered);

    // 3. Convert clean PCL cloud back to ROS msg for other nodes
    sensor_msgs::msg::PointCloud2 output;
    pcl_conversions::moveFromPCL(*cloud_filtered, output);
    output.header = msg->header; 

    pub_->publish(output);
  }

  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pub_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<PerceptionFilterNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
