#include <rclcpp/rclcpp.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <geometry_msgs/msg/twist_stamped.hpp>

class LocalPlannerNode : public rclcpp::Node
{
public:
  LocalPlannerNode() : Node("local_trajectory_node")
  {
    // Listen to the 2D map we just built
    costmap_sub_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
      "/mapping/local_costmap", 10, std::bind(&LocalPlannerNode::costmap_callback, this, std::placeholders::_1));

    // Send velocity commands to the Priority 2 Safety Bridge
    cmd_pub_ = this->create_publisher<geometry_msgs::msg::TwistStamped>(
      "/cmd_vel_nav", 10);

    RCLCPP_INFO(this->get_logger(), "Local Trajectory Planner Active. Computing dynamic velocity vectors.");
  }

private:
  void costmap_callback(const nav_msgs::msg::OccupancyGrid::SharedPtr msg)
  {
    geometry_msgs::msg::TwistStamped cmd;
    cmd.header.stamp = this->now();
    cmd.header.frame_id = "base_link";

    // Default safe cruising velocity (e.g., 0.5 m/s forward)
    cmd.twist.linear.x = 0.5;
    cmd.twist.linear.y = 0.0;
    cmd.twist.linear.z = 0.0;
    cmd.twist.angular.z = 0.0;

    // Basic obstacle check: If map data exists and the center region is lethal (>50)
    if (!msg->data.empty()) {
      int center_index = (msg->info.height / 2) * msg->info.width + (msg->info.width / 2);
      if (msg->data[center_index] > 50) {
        cmd.twist.linear.x = 0.0; // Emergency brake
        RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "Obstacle imminent! Halting velocity.");
      }
    }

    cmd_pub_->publish(cmd);
  }

  rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr costmap_sub_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr cmd_pub_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<LocalPlannerNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
