#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>

enum class MissionState {
  INIT,
  TAKEOFF,
  PATROL,
  RETURN_TO_HOME
};

class MissionExecutiveNode : public rclcpp::Node
{
public:
  MissionExecutiveNode() : Node("mission_executive_node"), state_(MissionState::INIT)
  {
    goal_pub_ = this->create_publisher<geometry_msgs::msg::PoseStamped>("/autonomy/goal_pose", 10);
    
    // Timer to simulate mission progression every 5 seconds
    timer_ = this->create_wall_timer(
      std::chrono::seconds(5), std::bind(&MissionExecutiveNode::mission_loop, this));
      
    RCLCPP_INFO(this->get_logger(), "Mission Executive Active. State: INIT");
  }

private:
  void mission_loop()
  {
    switch (state_) {
      case MissionState::INIT:
        RCLCPP_INFO(this->get_logger(), "System initialized. Requesting TAKEOFF.");
        state_ = MissionState::TAKEOFF;
        break;
      case MissionState::TAKEOFF:
        RCLCPP_INFO(this->get_logger(), "Takeoff complete. Commencing PATROL to Waypoint Alpha.");
        publish_goal(15.0, 10.0); 
        state_ = MissionState::PATROL;
        break;
      case MissionState::PATROL:
        RCLCPP_INFO(this->get_logger(), "Patrol waypoint reached. Initiating RETURN TO HOME.");
        publish_goal(0.0, 0.0); 
        state_ = MissionState::RETURN_TO_HOME;
        break;
      case MissionState::RETURN_TO_HOME:
        RCLCPP_INFO(this->get_logger(), "Vehicle returned to home base. Mission complete.");
        break;
    }
  }

  void publish_goal(double x, double y)
  {
    geometry_msgs::msg::PoseStamped goal;
    goal.header.stamp = this->now();
    goal.header.frame_id = "map"; // Goals are published in the global map frame
    goal.pose.position.x = x;
    goal.pose.position.y = y;
    goal.pose.position.z = 2.5;   // 2.5m flight altitude
    goal.pose.orientation.w = 1.0;
    goal_pub_->publish(goal);
  }

  MissionState state_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr goal_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<MissionExecutiveNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
