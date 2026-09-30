#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>

class SlamMappingNode : public rclcpp::Node
{
public:
  SlamMappingNode() : Node("slam_mapping_node")
  {
    sub_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
      "/perception/filtered_points", 10, std::bind(&SlamMappingNode::cloud_callback, this, std::placeholders::_1));
    
    pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>(
      "/mapping/local_costmap", 10);
      
    RCLCPP_INFO(this->get_logger(), "SLAM Mapping Layer Active. Generating 2D Occupancy Grid.");
  }

private:
  void cloud_callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg)
  {
    nav_msgs::msg::OccupancyGrid grid;
    grid.header = msg->header;
    grid.header.frame_id = "odom"; // Map is built in fixed odometry frame
    
    // Create a 10m x 10m local grid at 10cm resolution
    grid.info.resolution = 0.1;
    grid.info.width = 100;
    grid.info.height = 100;
    grid.info.origin.position.x = -5.0;
    grid.info.origin.position.y = -5.0;
    grid.info.origin.position.z = 0.0;
    grid.info.origin.orientation.w = 1.0;
    
    grid.data.assign(grid.info.width * grid.info.height, -1); // Initialize as Unknown (-1)

    // Iterate through 3D points and project to 2D
    sensor_msgs::PointCloud2ConstIterator<float> iter_x(*msg, "x");
    sensor_msgs::PointCloud2ConstIterator<float> iter_y(*msg, "y");
    sensor_msgs::PointCloud2ConstIterator<float> iter_z(*msg, "z");

    for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z)
    {
      // Crop out points representing the floor or ceiling above the drone
      if (*iter_z < -0.5 || *iter_z > 2.0) continue; 

      int grid_x = (*iter_x - grid.info.origin.position.x) / grid.info.resolution;
      int grid_y = (*iter_y - grid.info.origin.position.y) / grid.info.resolution;

      if (grid_x >= 0 && grid_x < (int)grid.info.width && grid_y >= 0 && grid_y < (int)grid.info.height)
      {
        int index = grid_y * grid.info.width + grid_x;
        grid.data[index] = 100; // Mark as Lethal Obstacle (100)
      }
    }
    
    pub_->publish(grid);
  }

  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_;
  rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<SlamMappingNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
