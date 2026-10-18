cmake_minimum_required(VERSION 3.8)
project(airmouse_interfaces)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/FlightState.msg"
  "msg/AttitudeState.msg"
  "msg/GlobalPosition.msg"
  "msg/LocalPositionNED.msg"
  "msg/BatteryState.msg"
  "msg/SystemHealth.msg"
  "msg/FailSafeCause.msg"
  "msg/HealthStatus.msg"
  "msg/FailSafeStatus.msg"
  "msg/AdapterStatus.msg"
  "srv/Arm.srv"
  "srv/Disarm.srv"
  "srv/SetMode.srv"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
