#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist_stamped.hpp>

class OffboardBridgeNode : public rclcpp::Node
{
public:
  OffboardBridgeNode() : Node("offboard_bridge_node")
  {
    // Subscribe to the Autonomy Planner's velocity command
    cmd_sub_ = this->create_subscription<geometry_msgs::msg::TwistStamped>(
      "/cmd_vel_nav", 10, std::bind(&OffboardBridgeNode::cmd_callback, this, std::placeholders::_1));

    // Publish to the Flight Controller Interface (Rohit's stack)
    fcu_pub_ = this->create_publisher<geometry_msgs::msg::TwistStamped>(
      "/flight_control/setpoint", 10);

    // Watchdog timer (Safety failsafe: 10 Hz check)
    watchdog_timer_ = this->create_wall_timer(
      std::chrono::milliseconds(100), std::bind(&OffboardBridgeNode::watchdog_callback, this));
    
    last_cmd_time_ = this->now();
    RCLCPP_INFO(this->get_logger(), "Offboard Bridge Active. Enforcing 0.5s safety watchdog.");
  }

private:
  void cmd_callback(const geometry_msgs::msg::TwistStamped::SharedPtr msg)
  {
    last_cmd_time_ = this->now();
    // Pass valid planner commands straight through to the FCU
    fcu_pub_->publish(*msg);
  }

  void watchdog_callback()
  {
    auto current_time = this->now();
    // If we haven't received a command in 0.5 seconds, send a zero-velocity hover command
    if ((current_time - last_cmd_time_).seconds() > 0.5)
    {
      geometry_msgs::msg::TwistStamped hover_cmd;
      hover_cmd.header.stamp = current_time;
      hover_cmd.header.frame_id = "base_link";
      hover_cmd.twist.linear.x = 0.0;
      hover_cmd.twist.linear.y = 0.0;
      hover_cmd.twist.linear.z = 0.0;
      hover_cmd.twist.angular.x = 0.0;
      hover_cmd.twist.angular.y = 0.0;
      hover_cmd.twist.angular.z = 0.0;
      
      fcu_pub_->publish(hover_cmd);
      RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000, 
        "Planner timeout! Emitting zero-velocity failsafe hover command.");
    }
  }

  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr cmd_sub_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr fcu_pub_;
  rclcpp::TimerBase::SharedPtr watchdog_timer_;
  rclcpp::Time last_cmd_time_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<OffboardBridgeNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
