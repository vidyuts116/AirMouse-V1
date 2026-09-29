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

### command_interface.py

Purpose:
- Provide a reusable MAVLink command layer for AirMouse V1.
- Establish and verify MAVLink communication before issuing commands.
- Send generic MAVLink `COMMAND_LONG` requests.
- Match commands with their corresponding `COMMAND_ACK`.
- Apply bounded timeouts to connection, acknowledgement, and state verification.
- Provide verified ARM and DISARM operations.

The command interface currently provides:

- `connect()`
- `send_command_long()`
- `wait_for_armed_state()`
- `arm()`
- `disarm()`

## Command Acknowledgement and State Verification

AirMouse does not treat a successful `COMMAND_ACK` as proof that the vehicle has reached the requested state.

For state-changing operations such as ARM and DISARM, two separate conditions are verified:

1. ArduPilot accepts the command through `COMMAND_ACK`.
2. Subsequent `HEARTBEAT` telemetry confirms the requested armed state.

This provides the following control sequence:

    Command request
        |
        v
    COMMAND_ACK
        |
        v
    State telemetry
        |
        v
    State confirmation

For ARM/DISARM, the interface uses:

- `MAV_CMD_COMPONENT_ARM_DISARM`
- `MAV_MODE_FLAG_SAFETY_ARMED`

## Timeout Handling

The command interface uses bounded timeouts rather than waiting indefinitely.

Verified timeout behaviour includes:

- Missing MAVLink heartbeat during connection
- Missing `COMMAND_ACK`
- Requested armed state not being reached

Timeout measurement uses `time.monotonic()` so timeout behaviour is independent of changes to the system wall clock.

## ARM/DISARM SITL Verification

ARM and DISARM control has been verified using ArduPilot SITL.

The integration test confirmed the complete sequence:

    Initial state: DISARMED
        |
        v
    ARM command
        |
        v
    MAV_RESULT_ACCEPTED
        |
        v
    HEARTBEAT confirms ARMED
        |
        v
    DISARM command
        |
        v
    MAV_RESULT_ACCEPTED
        |
        v
    HEARTBEAT confirms DISARMED

The repository includes:

- `test_command_interface.py`
- `test_arm_disarm.py`

These provide reproducible command-interface and ARM/DISARM verification against SITL.

## Command-Layer Architecture Note

The current implementation directly receives MAVLink messages using `recv_match()`.

This is appropriate for the present single-consumer development stage.

Before AirMouse introduces multiple concurrent MAVLink consumers, ROS 2 integration, or multiple higher-level modules sharing one MAVLink connection, this architecture must be refactored to use a centralized MAVLink message-routing/dispatch layer.

The future routing layer should ensure that telemetry and command acknowledgements are distributed to the correct consumers without multiple modules independently competing for messages from the same MAVLink connection.

## Physical Aircraft Safety and Portability

The command-processing logic is intended to remain reusable when transitioning from SITL to the physical AirMouse V1 aircraft.

The current SITL endpoint remains:

    udpin:127.0.0.1:14550

The transport must be made configurable for physical hardware.

Physical-aircraft ARM/DISARM testing must not simply repeat the SITL procedure. It will require a dedicated bench-validation and safety procedure appropriate to the installed flight controller, propulsion system, communication transport, and aircraft configuration.

## Flight Mode Control

The MAVLink command interface supports verified flight-mode changes.

The interface currently provides:

- `wait_for_mode()`
- `set_mode()`

`wait_for_mode()` observes MAVLink `HEARTBEAT` telemetry and verifies that the vehicle's `custom_mode` matches the requested flight mode.

`set_mode()`:

1. validates the requested mode against the vehicle's available mode mapping,
2. sends a MAVLink `SET_MODE` request,
3. waits for subsequent `HEARTBEAT` telemetry,
4. confirms that the requested mode was actually reached.

A transmitted mode request is therefore not treated by itself as proof of a successful state transition.

### Flight Mode SITL Verification

Flight-mode control has been verified using ArduPilot SITL.

The verified integration sequence was:

    STABILIZE
        |
        v
    Request GUIDED
        |
        v
    HEARTBEAT confirms GUIDED
        |
        v
    Request STABILIZE
        |
        v
    HEARTBEAT confirms STABILIZE

Testing also confirmed:

- detection of the current `STABILIZE` mode,
- timeout when waiting for a mode that was not entered,
- successful `STABILIZE` to `GUIDED` transition,
- successful `GUIDED` to `STABILIZE` transition,
- rejection of an unsupported flight-mode name.

The repository includes:

    test_mode_control.py

This test performs the verified SITL mode-control integration cycle.

Mode-changing tests against a future physical aircraft will require a separate hardware safety and validation procedure and must not be treated as equivalent to SITL testing.

## MAVLink Connection Manager

The `MAVLinkConnectionManager` provides the transport and connection-lifecycle boundary for the AirMouse V1 MAVLink architecture.

Its responsibilities currently include:

- opening a MAVLink connection,
- accepting a configurable MAVLink connection string,
- passing transport-specific options to `pymavlink`,
- verifying communication through MAVLink heartbeat reception,
- storing the detected system and component IDs,
- providing controlled access to the verified connection,
- preventing accidental duplicate connection attempts,
- closing the connection cleanly,
- clearing connection state after disconnect,
- cleaning up correctly when heartbeat verification fails.

### Architecture

The Connection Manager separates MAVLink transport establishment from the higher-level AirMouse flight-control logic.

Conceptually:

    SITL / Physical Flight Controller
                |
                v
         MAVLink Transport
                |
                v
      MAVLinkConnectionManager
                |
                v
       Verified MAVLink Connection
                |
                v
        Future Message Router
                |
        +-------+-------+
        |       |       |
      State   Command  Health

Higher-level modules should therefore not need to know whether the underlying MAVLink transport is UDP, serial/UART, USB, telemetry radio, or another supported transport.

### SITL Verification

The Connection Manager has been verified against ArduPilot SITL using:

    udpin:127.0.0.1:14550

Verified behaviour includes:

- successful heartbeat-based connection establishment,
- system and component ID detection,
- verified connection-object access,
- rejection of access before connection,
- rejection of duplicate connection attempts,
- clean disconnect and state reset,
- timeout when no heartbeat is received,
- clean internal state after a failed connection attempt.

The repository includes:

- `test_connection_manager.py`
- `test_connection_timeout.py`

### Physical-Drone Portability

The Connection Manager itself does not hard-code the SITL UDP endpoint.

The connection string and optional transport parameters are supplied externally when the manager is created.

This allows the same connection-management logic to later support physical hardware through an appropriate connection such as USB, serial/UART, telemetry radio, or network transport without rewriting the Connection Manager.

The exact physical Pixhawk device, baud rate, and transport settings will be selected during hardware integration and should eventually be supplied by the AirMouse configuration layer.

The current SITL-specific connection strings in the integration tests are test configuration and are not part of the reusable Connection Manager core.

Automatic reconnection and more advanced connection supervision are intentionally deferred until their requirements are defined by the higher-level health-monitoring and message-routing architecture.
