cmake_minimum_required(VERSION 3.8)
project(airmouse_autonomy)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(geometry_msgs REQUIRED)

# Build Autonomy Core Node
add_executable(autonomy_core_node src/autonomy_core.cpp)
ament_target_dependencies(autonomy_core_node rclcpp std_msgs)

# Build Static Transforms Node
add_executable(static_transforms_node src/static_transforms_node.cpp)
ament_target_dependencies(static_transforms_node rclcpp tf2 tf2_ros geometry_msgs)

# Install both binaries so ROS can find them
install(TARGETS
  autonomy_core_node
  static_transforms_node
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

# Build Offboard Bridge Node
add_executable(offboard_bridge_node src/offboard_bridge_node.cpp)
ament_target_dependencies(offboard_bridge_node rclcpp geometry_msgs)

install(TARGETS
  offboard_bridge_node
  DESTINATION lib/${PROJECT_NAME}
)

# Find Point Cloud Libraries
find_package(sensor_msgs REQUIRED)
find_package(pcl_conversions REQUIRED)

# Build Perception Filter Node
add_executable(perception_filter_node src/perception_filter_node.cpp)
ament_target_dependencies(perception_filter_node rclcpp sensor_msgs pcl_conversions)

install(TARGETS
  perception_filter_node
  DESTINATION lib/${PROJECT_NAME}
)
