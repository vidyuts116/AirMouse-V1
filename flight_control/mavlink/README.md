# AirMouse V1 — MAVLink Interface

This directory contains AirMouse V1 components used to communicate with and monitor the ArduPilot flight controller through MAVLink.

## Current Components

### heartbeat_monitor.py

Purpose:
- Establish MAVLink communication with the flight controller.
- Wait for and verify MAVLink heartbeat messages.
- Confirm that the autopilot is reachable.

### attitude_monitor.py

Purpose:
- Monitor vehicle attitude telemetry.
- Observe roll, pitch, and yaw information received through MAVLink.

### position_monitor.py

Purpose:
- Monitor global and local vehicle position.
- Monitor translational velocity.
- Convert MAVLink telemetry into human-readable SI units.

MAVLink messages currently used:

- `GLOBAL_POSITION_INT`
- `LOCAL_POSITION_NED`

The monitor displays:

- Latitude and longitude
- Absolute altitude
- Relative altitude
- Local NED X, Y, Z position
- Global NED velocity
- Local NED velocity

## Coordinate Convention

Local position follows the NED coordinate system:

- X = North
- Y = East
- Z = Down

Therefore, while the aircraft is above its local origin, Z is normally negative.

Example:

    Z = -5 m

means the aircraft is approximately 5 metres above the local origin.

## Verification

The position monitor has been verified using ArduPilot SITL.

Testing confirmed:

- MAVLink heartbeat reception
- `GLOBAL_POSITION_INT` reception
- `LOCAL_POSITION_NED` reception
- Position changes during simulated vehicle movement
- Velocity changes during simulated vehicle movement
- Stable altitude during horizontal movement
- Velocity returning approximately to zero after stopping

## Physical Drone Portability

The telemetry-processing logic is intended to remain reusable when moving from SITL to the physical AirMouse V1 aircraft.

Current simulation-specific connection:

    udpin:127.0.0.1:14550

This connection endpoint must be made configurable before physical-drone integration.

When physical hardware is introduced, the MAVLink transport may change to USB, serial/UART, telemetry radio, network transport, or another appropriate interface without requiring the telemetry interpretation logic to be rewritten.

### system_health_monitor.py

Purpose:
- Monitor MAVLink system-health and battery telemetry.
- Convert raw battery measurements into human-readable units.
- Observe communication error information.
- Expose onboard sensor status bitmasks for later health decoding.

MAVLink messages currently used:

- `SYS_STATUS`
- `BATTERY_STATUS`

The monitor displays:

- Battery voltage
- Battery current
- Remaining battery percentage
- MAVLink communication drop rate
- MAVLink communication error count
- Onboard sensor present, enabled, and health bitmasks
- Battery ID
- Consumed battery capacity
- Consumed battery energy
- Battery fault bitmask

## System Health Verification

The system health monitor has been verified using ArduPilot SITL.

Testing confirmed:

- `SYS_STATUS` reception
- `BATTERY_STATUS` reception
- Battery voltage conversion from millivolts to volts
- Battery current conversion from MAVLink 10 mA units to amperes
- Battery remaining percentage reception
- Communication status reception
- Sensor-status bitmask reception
- Battery fault-bitmask reception

During the verification run, SITL reported approximately:

    Voltage: 12.60 V
    Current: 0.00 A
    Remaining: 100%
    Communication errors: 0
    Battery fault mask: 0

These values validate the telemetry-processing path in simulation. They do not represent validation of a physical battery monitor or current sensor.

The sensor present, enabled, and health values are currently retained as raw MAVLink bitmasks. Human-readable per-sensor decoding can be added in a later health-management layer.
