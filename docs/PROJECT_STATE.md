# AirMouse V1 — Project State

Last updated: 28 September 2026

## Team

- Rohit — Flight Control & System Integration Lead
- Arif Sir — Simulation, Environment & Virtual Sensor Lead
- Doshi — ROS 2, Autonomy, Localisation & Navigation Lead

## Flight Control — Rohit

- Ubuntu 24.04.5 ARM64: VERIFIED
- ROS 2 Jazzy: VERIFIED
- AirMouse ROS workspace: VERIFIED
- `airmouse_core` package: VERIFIED
- `/airmouse_status_node`: VERIFIED
- `/airmouse/status` publishing at approximately 0.5 Hz: VERIFIED
- ArduPilot repository and prerequisites: VERIFIED
- ArduCopter SITL build: VERIFIED
- MAVProxy/MAVLink: VERIFIED
- STABILIZE → GUIDED: VERIFIED
- ARM: VERIFIED
- Takeoff to 5 m: VERIFIED
- Hover: VERIFIED
- LAND: VERIFIED
- Automatic disarm after landing: VERIFIED

## Simulation — Arif Sir

- Ubuntu development environment: PENDING VERIFICATION
- Gazebo installation: NOT STARTED
- UAV simulation model: NOT STARTED
- Indoor environment: NOT STARTED
- Virtual sensors: NOT STARTED
- ArduPilot ↔ Gazebo integration: NOT STARTED

## Autonomy — Doshi

- Ubuntu development environment: PENDING VERIFICATION
- ROS 2 Jazzy: NOT YET VERIFIED
- AirMouse workspace: NOT YET VERIFIED
- Localisation: NOT STARTED
- SLAM: NOT STARTED
- Navigation: NOT STARTED
- Mission logic: NOT STARTED
- Perception: NOT STARTED

## Integration

- Common private GitHub repository: CREATED
- Rohit's GitHub access: VERIFIED
- Rohit's SSH authentication: VERIFIED
- Rohit's local repository clone: VERIFIED
- Team member collaborator invitations: SENT
- Three-VM LAN connectivity: NOT STARTED
- ArduPilot ↔ Gazebo: NOT STARTED
- Gazebo ↔ ROS 2: NOT STARTED
- ROS 2 ↔ ArduPilot: NOT STARTED
- Full closed-loop simulation: NOT STARTED

## Current Parallel Objectives

### Rohit
Establish the common repository, documentation structure and integration baseline while preserving the verified ArduPilot SITL environment.

### Arif Sir
Establish and verify the Gazebo simulation environment.

### Doshi
Establish and verify the ROS 2 Jazzy autonomy-development environment.

## Next Integration Milestone

Connect all three Ubuntu VMs through the same local router and verify bidirectional network communication before attempting distributed simulation.
