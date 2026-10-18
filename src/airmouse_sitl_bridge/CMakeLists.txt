cmake_minimum_required(VERSION 3.16)
project(airmouse_sitl_bridge CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(gz-cmake3 REQUIRED)
gz_find_package(gz-sim8 REQUIRED)
gz_find_package(gz-plugin2 REQUIRED COMPONENTS register)
gz_find_package(gz-transport13 REQUIRED)
gz_find_package(gz-msgs10 REQUIRED)
add_library(AirMouseActuatorsBridge SHARED ActuatorsBridge.cc)
target_link_libraries(AirMouseActuatorsBridge PRIVATE
  gz-sim8::gz-sim8 gz-plugin2::register gz-transport13::gz-transport13 gz-msgs10::gz-msgs10)

add_library(AirMouseLidarDropout SHARED LidarDropout.cc)
target_link_libraries(AirMouseLidarDropout PRIVATE
  gz-sim8::gz-sim8 gz-plugin2::register gz-transport13::gz-transport13 gz-msgs10::gz-msgs10)

# ArduPilotPlugin built from the unmodified ardupilot_gazebo sources (pinned clone in ../ardupilot_gazebo).
# Only this target is needed; upstream's CMake also requires OpenCV + GStreamer for its camera plugin.
set(APG ${CMAKE_CURRENT_SOURCE_DIR}/../ardupilot_gazebo)
find_package(RapidJSON REQUIRED)
add_library(ArduPilotPlugin SHARED ${APG}/src/ArduPilotPlugin.cc ${APG}/src/SocketUDP.cc ${APG}/src/Util.cc)
target_include_directories(ArduPilotPlugin PRIVATE ${APG}/include ${RAPIDJSON_INCLUDE_DIRS} ${RapidJSON_INCLUDE_DIRS})
target_link_libraries(ArduPilotPlugin PRIVATE gz-sim8::gz-sim8)
