# Rohit — Flight Control & System Integration Progress

## Role

Flight Control & System Integration Lead

## Development Environment

- Host: MacBook
- Ubuntu: 24.04.5 LTS
- Architecture: ARM64 / aarch64
- Ubuntu VM RAM: approximately 3.8 GiB
- Swap: approximately 3.8 GiB
- vCPU: 2
- ROS distribution: ROS 2 Jazzy

## ROS 2 Baseline

Status: VERIFIED

Completed:

- ROS 2 Jazzy installed and operational.
- Workspace created at `~/airmouse_ws`.
- `airmouse_core` package created.
- Workspace successfully built using `colcon`.
- `/airmouse_status_node` successfully executed.
- `/airmouse/status` topic verified.
- Message type: `std_msgs/msg/String`.
- Message `AirMouse system online` successfully received.
- Publishing frequency verified at approximately 0.5 Hz.

## ArduPilot Baseline

Status: VERIFIED

Completed:

- ArduPilot repository available at `~/ardupilot`.
- Required submodules available.
- ArduPilot prerequisites installed.
- Python virtual environment available at `~/venv-ardupilot`.
- `sim_vehicle.py` verified.
- MAVProxy verified.
- ArduCopter SITL successfully built.
- ArduCopter SITL successfully launched.

## Virtual Flight Test

Status: VERIFIED

Successfully demonstrated:

1. ArduCopter SITL launch.
2. MAVProxy connection.
3. STABILIZE mode.
4. GUIDED mode.
5. Arming.
6. Takeoff to approximately 5 m.
7. Hover.
8. LAND command.
9. Landing.
10. Automatic disarming after landing.

## Git/GitHub Baseline

Status: IN PROGRESS

Completed:

- Common private `AirMouse-V1` repository created.
- Rohit's personal GitHub account added as collaborator.
- Git 2.43.0 verified.
- Local Git identity configured.
- Ed25519 SSH key generated.
- SSH public key registered with Rohit's GitHub account.
- GitHub SSH authentication successfully verified.
- Private AirMouse repository successfully cloned.
- `flight-control/project-baseline` branch created.
- Initial project documentation structure created.

## Current Responsibility

Rohit owns:

- ArduPilot / ArduCopter
- SITL
- MAVProxy / MAVLink
- Flight-control configuration
- Flight modes
- Failsafes
- GPS-denied flight-controller configuration
- Autonomy ↔ flight-controller interface
- Cross-system integration
- End-to-end testing

## Immediate Next Objectives

1. Establish common Git/documentation baseline.
2. Preserve the currently working ArduPilot SITL configuration.
3. Define integration interfaces with Gazebo and ROS 2.
4. Prepare for three-machine LAN integration.
5. Integrate with Arif Sir's Gazebo environment when verified.
6. Integrate with Doshi's ROS/autonomy stack when verified.

## Important Rule

Previously verified components must not be marked incomplete or reinstalled without evidence of a problem.

Future progress must be recorded only after actual testing and verification.

## MAVLink Communication Baseline

Status: VERIFIED

Date: 28 September 2026

### Test Configuration

- ArduCopter SITL running locally
- MAVProxy connected to ArduCopter SITL
- MAVProxy forwarding MAVLink telemetry to UDP 127.0.0.1:14550
- Python environment: ~/venv-ardupilot
- pymavlink version: 2.4.50
- Test program: flight_control/mavlink/heartbeat_monitor.py

### Verified Result

The AirMouse Python MAVLink client successfully received a HEARTBEAT
message from the ArduCopter SITL MAVLink stream.

Observed values:

- System ID: 1
- Component ID: 0
- Vehicle type: 2
- Autopilot type: 3
- Base mode: 81
- Custom mode: 0
- System status: 3

Verified communication path:

ArduCopter SITL
→ MAVLink
→ MAVProxy
→ UDP 127.0.0.1:14550
→ AirMouse heartbeat_monitor.py

This verifies the first programmatic MAVLink communication baseline
between AirMouse software and the simulated ArduPilot flight controller.
