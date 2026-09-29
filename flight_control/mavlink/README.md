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
