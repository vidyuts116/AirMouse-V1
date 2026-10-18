# AirMouse V1 ROS 2 Interface Contract

## Purpose

The ROS 2 Interface Adapter exposes the existing AirMouse flight-control
core to ROS 2 consumers without duplicating MAVLink transport, routing,
state decoding, health evaluation, or command logic.

The adapter is a boundary layer between the existing MAVLink flight-control
core and higher-level ROS 2 modules.

## Architecture

    Flight Controller / ArduPilot SITL
                  |
                  v
          Connection Manager
                  |
                  v
           Message Router
                  |
          +-------+--------+
          |                |
          v                v
    Vehicle State     Command Manager
          |
          v
    Health / Fail-Safe Monitor
          |
          v
    ROS 2 Interface Adapter
          |
     +----+----+----------------+
     |         |                |
     v         v                v
    SLAM    Navigation      Mission / AI

## Architectural Boundaries

The ROS 2 Interface Adapter MUST NOT:

- create an independent MAVLink receive loop,
- call recv_match(),
- bypass the Message Router,
- duplicate Vehicle State decoding,
- duplicate Health Monitor policy,
- implement MAVLink command acknowledgement handling,
- directly own the MAVLink transport,
- contain SITL-specific connection details,
- fabricate unsupported flight-control capabilities.

The adapter MUST consume the existing public AirMouse core APIs.

## Time and Coordinate Semantics

Internal Vehicle State `updated_at` values are monotonic process-local
timestamps used for freshness evaluation.

They are not ROS wall-clock timestamps and MUST NOT be published directly
as ROS message header timestamps.

ROS messages requiring timestamps shall use the ROS node clock when
published.

Existing local position and velocity use MAVLink NED semantics:

- X = North
- Y = East
- Z = Down

Coordinate conversion required by ROS REP-103 / ENU consumers shall be
performed explicitly by the ROS adapter or a dedicated transform layer.
NED values MUST NOT be silently labelled as ENU.

Angles currently supplied by Vehicle State are in radians.

## Namespace

The default vehicle namespace is:

    /airmouse

Future multi-vehicle operation shall permit this namespace to be
configured/remapped rather than hard-coded throughout consuming modules.

## Topics Implemented From Existing Core

### /airmouse/state/flight

Purpose:

Expose high-level flight-controller state.

Fields:

- system_id
- component_id
- vehicle_type
- autopilot_type
- flight_mode
- armed
- system_status
- system_state
- stamp

Source:

    VehicleStateManager.state["flight"]

### /airmouse/state/attitude

Purpose:

Expose vehicle attitude and angular velocity.

Fields:

- roll_rad
- pitch_rad
- yaw_rad
- roll_rate_rad_s
- pitch_rate_rad_s
- yaw_rate_rad_s
- stamp

Source:

    VehicleStateManager.state["attitude"]

### /airmouse/state/global_position

Purpose:

Expose global geographic position and velocity.

Fields:

- latitude_deg
- longitude_deg
- altitude_m
- relative_altitude_m
- velocity_north_mps
- velocity_east_mps
- velocity_down_mps
- stamp

Source:

    VehicleStateManager.state["global_position"]

### /airmouse/state/local_position_ned

Purpose:

Expose flight-controller local NED position and velocity without hiding
the underlying coordinate convention.

Fields:

- north_m
- east_m
- down_m
- velocity_north_mps
- velocity_east_mps
- velocity_down_mps
- stamp

Source:

    VehicleStateManager.state["local_position"]

### /airmouse/state/battery

Purpose:

Expose available battery information.

Fields:

- battery_id
- current_consumed_mah
- energy_consumed_hj
- remaining_percent
- fault_bitmask
- voltage_v
- current_a
- stamp

Sources:

    VehicleStateManager.state["battery"]
    VehicleStateManager.state["system_health"]

Missing telemetry must remain representable as unavailable rather than
being converted into misleading valid measurements.

### /airmouse/state/system_health

Purpose:

Expose raw flight-controller system-health information required by
diagnostics and higher-level monitoring.

Fields:

- voltage_v
- current_a
- battery_remaining_percent
- drop_rate_comm
- errors_comm
- sensors_present
- sensors_enabled
- sensors_health
- stamp

Source:

    VehicleStateManager.state["system_health"]

### /airmouse/health/status

Purpose:

Expose the interpreted AirMouse health assessment.

Fields:

- overall_status
- heartbeat_status
- system_health_status
- battery_status
- sensor_status
- evaluated_at_age_or_equivalent
- stamp

Valid health states:

- HEALTHY
- WARNING
- CRITICAL
- UNKNOWN

Source:

    HealthFailSafeMonitor.evaluate()

### /airmouse/health/failsafe

Purpose:

Expose the current fail-safe policy decision and its causes.

Fields:

- health_status
- decision
- causes
- stamp

Valid decisions:

- CONTINUE
- CAUTION
- HOLD
- FAILSAFE

Each cause shall preserve:

- check
- status
- reason

Source:

    HealthFailSafeMonitor.determine_failsafe_decision()

## Services Implemented From Existing Core

### /airmouse/command/arm

Request:

- no vehicle-control parameters required

Response:

- success
- message
- resulting_armed_state
- resulting_mode

Backend:

    MAVLinkCommandManager.arm()

### /airmouse/command/disarm

Request:

- no vehicle-control parameters required

Response:

- success
- message
- resulting_armed_state
- resulting_mode

Backend:

    MAVLinkCommandManager.disarm()

### /airmouse/command/set_mode

Request:

- mode

Response:

- success
- message
- resulting_mode
- armed

Backend:

    MAVLinkCommandManager.set_mode()

## Diagnostics / Adapter State

### /airmouse/interface/status

Purpose:

Allow other ROS 2 modules to determine whether the AirMouse bridge itself
is operational.

Fields should represent:

- adapter_running
- vehicle_state_available
- health_available
- command_interface_available
- last_publish_time
- stamp

This represents adapter readiness, not flight safety.

## Future Required Interfaces

The following capabilities are expected by later AirMouse modules but
MUST NOT be implemented as fake flight-control functionality in this
module until a real backend exists.

### Pose / Odometry

Future navigation and SLAM integration will require standard ROS 2
representations such as:

- geometry_msgs/PoseStamped
- geometry_msgs/TwistStamped
- nav_msgs/Odometry
- tf2 transforms

Required frame relationships may include:

    map
      |
      v
    odom
      |
      v
    base_link

The existing MAVLink local state is NED and must be explicitly converted
where an ENU ROS frame is required.

### IMU

Future perception, estimation, and navigation modules may require:

    sensor_msgs/Imu

The current Vehicle State Manager exposes attitude and angular rates but
does not yet expose a complete raw IMU measurement set.

A fake IMU topic MUST NOT be produced from incomplete data.

### GNSS

A future standard ROS GNSS representation may use:

    sensor_msgs/NavSatFix

The current state contains latitude, longitude and altitude, but additional
GNSS metadata may be required before claiming a complete GNSS interface.

### Camera

Future reconnaissance and perception modules may require:

    sensor_msgs/Image
    sensor_msgs/CameraInfo

Camera ownership belongs to the future perception/sensor subsystem, not
the MAVLink state adapter.

### Range / Altitude Sensors

Future obstacle avoidance and low-altitude navigation may require:

    sensor_msgs/Range

These shall be introduced when real range-sensor data exists.

### Point Clouds

Future mapping modules may require:

    sensor_msgs/PointCloud2

Point-cloud generation belongs to perception / SLAM rather than this
flight-control adapter.

### Navigation Goals

Future autonomous navigation may require an action interface for
long-running goal execution.

Examples include:

- navigate to local pose,
- navigate to global waypoint,
- execute mission,
- takeoff,
- land,
- return-to-launch.

These MUST only be exposed once corresponding real command and feedback
paths exist.

## Service Versus Action Boundary

Short request/response operations such as ARM, DISARM and SET_MODE are
ROS 2 services.

Long-running operations requiring progress, feedback or cancellation
shall use ROS 2 actions when implemented.

## Data Ownership

The authoritative owners remain:

Vehicle state:
    VehicleStateManager

Health interpretation:
    HealthFailSafeMonitor

MAVLink command transactions:
    MAVLinkCommandManager

MAVLink receive ownership:
    MAVLinkMessageRouter

Transport lifecycle:
    MAVLinkConnectionManager

The ROS 2 adapter publishes or invokes these capabilities but does not
become their new source of truth.

## Physical-Drone Portability

No ROS 2 public interface shall depend on:

    udpin:127.0.0.1:14550

or any other SITL-specific endpoint.

Transport selection remains below the ROS 2 interface boundary.

The intended transition is:

    ArduPilot SITL
         |
         v
    AirMouse Core
         |
         v
    ROS 2 Adapter

followed by:

    Physical Flight Controller
         |
         v
    AirMouse Core
         |
         v
    SAME ROS 2 Adapter

Higher-level ROS 2 consumers should therefore require little or no change
when transitioning from simulation to physical hardware.

## Design Rule

Expose real capabilities now.

Reserve interfaces required by the planned architecture.

Do not fabricate implementations merely to make the interface appear
complete.
