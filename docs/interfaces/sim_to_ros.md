# Interface: Gazebo simulation → ROS 2 (AirMouse V1, for Doshi)

**Status:** DRAFT, 2026-10-04. Owner of the simulation side: Arif. Consumer: Doshi (SLAM / odometry).

**Evidence labels:** topics, types, frame ids, rates and the clock were OBSERVED on the running simulation. **The ROS side is NOT VERIFIED:** no ROS 2 is installed on the simulation machine, so `config/ros_gz_bridge.yaml` has never been run. Treat the first `ros2 topic list` as the acceptance test (section 7).

## 1. Set-up

```sh
export GZ_IP=127.0.0.1                      # Gazebo Transport is loopback-only; ROS and gz must agree
scripts/launch_sim.sh nidar_maze --sitl     # or any world; add --profile nominal|degraded
ros2 run ros_gz_bridge parameter_bridge --ros-args \
  -p config_file:=config/ros_gz_bridge.yaml -p use_sim_time:=true
```

Versions: Gazebo Harmonic (`gz sim` 8.15.0). Use ROS 2 **Jazzy** (the pairing for Harmonic). The YAML uses `qos_profile` and `frame_id` keys from the Jazzy `ros_gz_bridge`; older bridges ignore or reject them (comments in the file say what to do).

## 2. Topics (Gazebo → ROS only)

| ROS topic | ROS type ← Gazebo type | Rate | Content | QoS (bridge) |
|---|---|---|---|---|
| `/clock` | `rosgraph_msgs/Clock` ← `gz.msgs.Clock` | sim step | simulated time | `CLOCK` |
| `/airmouse/imu` | `sensor_msgs/Imu` ← `gz.msgs.IMU` | 200 Hz | body **FLU**; at rest `linear_acceleration.z ≈ +9.81`; noise per profile | `SENSOR_DATA` |
| `/airmouse/lidar` | `sensor_msgs/LaserScan` ← `gz.msgs.LaserScan` | 10 Hz | 360 beams, ±π, 0.1–12 m, σ 0.01 m; no return = `+inf` | `SENSOR_DATA` |
| `/airmouse/camera` | `sensor_msgs/Image` ← `gz.msgs.Image` | 10 Hz | 640×480 `rgb8`, 60° HFOV | `SENSOR_DATA` |
| `/airmouse/camera_info` | `sensor_msgs/CameraInfo` ← `gz.msgs.CameraInfo` | 10 Hz | intrinsics from the SDF camera | `SENSOR_DATA` |
| `/airmouse/rangefinder` | `sensor_msgs/LaserScan` ← `gz.msgs.LaserScan` | 50 Hz | 1 beam down, 0.2–8 m, σ 0.02 m; no return below 0.2 m | `SENSOR_DATA` |

- **Not bridged on purpose:** `/airmouse/gazebo/command/motor_speed` (ArduPilot drives the motors through the SITL plugin), `/airmouse/lidar/points`, `/airmouse/rangefinder/points`.
- **Experimental:** `/airmouse/depth_lidar/points` (`PointCloud2`, 64×16), see `docs/interfaces/depth_fallback_proposal.md`. Commented out in the YAML.
- **Ground truth:** `/world/airmouse_physics/pose/info` (`gz.msgs.Pose_V`). For evaluating SLAM drift only; **never** feed it to the SLAM or to ArduPilot. Commented out in the YAML.
- **`/airmouse/imu` orientation is ground truth.** The Gazebo IMU fills `orientation` with the world-referenced true attitude (covariance 0). A real IMU gives no such thing. Do not use it; use `angular_velocity` and `linear_acceleration` only.
- **LiDAR dropout:** with `--profile nominal|degraded`, `/airmouse/lidar` has random `+inf` beams and occasional fully-`inf` scans (rate unchanged). The sensor itself publishes `/airmouse/lidar_raw` in that case.

## 3. Frames

Gazebo stamps messages with scoped frame names such as `airmouse::base_link::imu_sensor`. The bridge YAML rewrites them to the ROS names below. **Gazebo publishes no TF.** Publish these static transforms yourself (poses are the SDF mounts in `simulation/airmouse_quadrotor.sdf`, in `base_link` = FLU: x forward, y left, z up):

| ROS `frame_id` | Gazebo frame | Pose in `base_link` (x y z, rpy) |
|---|---|---|
| `imu_link` | `airmouse::base_link::imu_sensor` | 0 0 0, 0 0 0 |
| `lidar_link` | `airmouse::base_link::lidar_2d` | 0 0 0.06, 0 0 0 |
| `camera_link` | `airmouse::base_link::rgb_camera` | 0.12 0 0, 0 0 0 (optical axis +x) |
| `camera_optical_link` | (same camera) | child of `camera_link`: 0 0 0, rpy −π/2 0 −π/2 (ROS optical convention, z forward) |
| `rangefinder_link` | `airmouse::base_link::rangefinder_down` | 0 0 −0.035, 0 π/2 0 (beam along +x of this frame = down) |
| `depth_lidar_link` (experimental) | `airmouse::base_link::depth_lidar` | 0.12 0 0, 0 0 0 |

```sh
ros2 run tf2_ros static_transform_publisher --frame-id base_link --child-frame-id lidar_link --z 0.06
ros2 run tf2_ros static_transform_publisher --frame-id base_link --child-frame-id camera_link --x 0.12
ros2 run tf2_ros static_transform_publisher --frame-id camera_link --child-frame-id camera_optical_link --roll -1.5708 --yaw -1.5708
# imu_link: identity; rangefinder_link: --z -0.035 --pitch 1.5708
```

Image data: Gazebo's camera frame is x-forward; the bridge does not rotate the pixels, so the `camera_optical_link` rename is only correct if your TF carries the −π/2 optical rotation shown above.

## 4. Time

- All ROS nodes use `use_sim_time:=true`; the bridge publishes `/clock`. Header stamps are **simulation** time (starts at 0 when the world starts).
- Measured real-time factor in SITL flights: 0.994–1.000. With heavy GUI load it can drop; sim time then runs slower than wall time, which is why nodes must not use wall time.
- MAVLink `ODOMETRY.time_usec` (docs/interfaces/odometry_to_ardupilot.md) is on the companion's monotonic clock; keep that separate from ROS sim time.

## 5. QoS

| Topic class | Bridge publisher | Recommended subscriber |
|---|---|---|
| sensors | `SENSOR_DATA` (best-effort, volatile, small depth) | `rclcpp::SensorDataQoS()` (a reliable subscriber cannot connect to a best-effort publisher) |
| `/clock` | `CLOCK` | the default for `use_sim_time` |

## 6. Realism profiles

`scripts/launch_sim.sh <world> --sitl --profile ideal|nominal|degraded` changes IMU noise/bias, wind and LiDAR dropout (`docs/sim-realism-profiles.md`). Values are PROVISIONAL assumptions. Use `nominal` and `degraded` to test the SLAM against the noise it will meet, and `ideal` to separate algorithm errors from sensor noise.

## 7. Acceptance checks (to run on Doshi's side)

1. `ros2 topic hz /airmouse/imu` ≈ 200, `/airmouse/lidar` ≈ 10, `/airmouse/camera` ≈ 10, `/airmouse/rangefinder` ≈ 50 (sim time).
2. `ros2 topic echo /clock --once` advances; `ros2 topic echo /airmouse/imu --once` shows `frame_id: imu_link` and `linear_acceleration.z ≈ 9.8` on the ground.
3. `ros2 run tf2_tools view_frames` shows the static tree above; RViz shows the scan on the maze walls.
4. Report any key the bridge rejects, so the YAML can be corrected.
