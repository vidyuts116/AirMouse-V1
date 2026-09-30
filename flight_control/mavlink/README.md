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

## MAVLink Message Router

The `MAVLinkMessageRouter` provides the centralized MAVLink receive and dispatch layer for AirMouse V1.

Its primary purpose is to ensure that higher-level modules do not independently compete for messages using `recv_match()` on the same MAVLink connection.

### Architecture

The intended MAVLink data path is:

    SITL / Physical Pixhawk
              |
              v
    MAVLinkConnectionManager
              |
              v
     MAVLinkMessageRouter
              |
        +-----+-----+------+
        |           |      |
        v           v      v
      State       Health  Command
      Manager     Monitor  ACK handling
                    |
                    v
               ROS 2 Bridge

The Connection Manager owns transport establishment and lifecycle.

The Message Router becomes the centralized consumer of incoming MAVLink traffic and distributes received messages to interested subscribers.

### Subscription Model

Consumers register callbacks for specific MAVLink message types using:

- `subscribe()`
- `unsubscribe()`

Multiple consumers may subscribe to the same MAVLink message type.

For example, a `HEARTBEAT` may eventually be consumed by both:

- the Vehicle State Manager,
- the Health Monitor.

Duplicate callback registration for the same message type is prevented.

### Centralized Reception

The router provides:

- `receive_once()` for controlled single-message reception,
- `start()` for continuous background reception,
- `stop()` for controlled shutdown.

The continuous receiver uses a dedicated thread so that incoming MAVLink traffic can be received and distributed without requiring every consumer to independently read from the underlying connection.

Higher-level AirMouse modules should therefore receive MAVLink information through the router rather than calling `recv_match()` independently.

### Subscriber Fault Isolation

Subscriber callbacks are isolated from each other.

If one subscriber raises an exception:

- the router remains operational,
- other subscribers can continue receiving messages,
- the callback failure is recorded for diagnostics.

Recorded callback failures can be retrieved using:

    get_callback_errors()

The method returns a snapshot of the diagnostic error list rather than exposing the router's internal list directly.

Fault detection is intentionally separated from response policy.

The Message Router records callback failures but does not currently decide whether those failures require warnings, degraded operation, failsafe behaviour, or other actions. Those decisions belong to the higher-level health and safety architecture.

### Thread Safety

Subscriber registration and removal are protected by a lock.

The router takes a snapshot of the relevant subscriber list before invoking callbacks.

Callbacks are therefore not executed while the subscriber lock is held.

This keeps subscription management separate from callback execution and reduces unnecessary coupling between subscribers.

### SITL Verification

The Message Router has been verified against ArduPilot SITL together with the `MAVLinkConnectionManager`.

Verified behaviour includes:

- subscriber registration,
- multiple subscribers receiving the same message,
- routing different MAVLink message types independently,
- duplicate-subscription protection,
- subscriber removal,
- single-message reception,
- continuous background reception,
- duplicate-start protection,
- clean router shutdown,
- callback fault isolation,
- callback-error diagnostics,
- real `HEARTBEAT` routing from SITL,
- real `ATTITUDE` routing from SITL,
- clean integration with the Connection Manager.

The repository includes:

- `test_message_router.py`
- `test_message_router_sitl.py`

### Physical-Drone Portability

The Message Router contains no SITL-specific endpoint or transport assumption.

It receives an already-established MAVLink connection and therefore does not need to know whether that connection originated from:

- SITL over UDP,
- Pixhawk over USB,
- serial/UART,
- telemetry radio,
- or another supported MAVLink transport.

Transport-specific configuration remains the responsibility of the Connection Manager and future configuration layer.

This allows the same Message Router implementation to be reused when AirMouse transitions from simulation to physical hardware.

### Current Limitation

Existing earlier AirMouse modules still contain some direct `recv_match()` usage.

Those modules were developed before the centralized router existed.

They must be migrated to consume routed MAVLink messages before multiple concurrent AirMouse components are operated together.

Until that migration is completed, the router architecture should be treated as the target receive path for new higher-level modules.

## Vehicle State Manager

The `VehicleStateManager` maintains the latest structured AirMouse vehicle state from MAVLink messages delivered by the centralized `MAVLinkMessageRouter`.

It does not establish a MAVLink transport and does not call `recv_match()` directly.

This preserves centralized MAVLink receive ownership and prevents multiple AirMouse modules from competing for messages on the same connection.

### Architecture

The vehicle-state data path is:

    SITL / Physical Flight Controller
                |
                v
      MAVLinkConnectionManager
                |
                v
       MAVLinkMessageRouter
                |
                v
        VehicleStateManager
                |
                v
       Structured Vehicle State
                |
        +-------+-------+
        |       |       |
      Health   ROS 2   Mission
      Logic    Bridge   Logic

The Connection Manager owns transport establishment.

The Message Router owns incoming MAVLink reception.

The Vehicle State Manager subscribes to routed messages and converts them into a structured, thread-safe state representation.

### MAVLink Inputs

The Vehicle State Manager currently consumes:

- `HEARTBEAT`
- `ATTITUDE`
- `GLOBAL_POSITION_INT`
- `LOCAL_POSITION_NED`
- `SYS_STATUS`
- `BATTERY_STATUS`

These messages populate six state sections:

- `flight`
- `attitude`
- `global_position`
- `local_position`
- `system_health`
- `battery`

### Flight State

`HEARTBEAT` telemetry is decoded into information including:

- MAVLink system ID,
- component ID,
- vehicle type,
- autopilot type,
- flight mode,
- armed state,
- system status,
- decoded system state.

Flight-mode and armed-state information therefore becomes available to higher-level AirMouse modules without those modules directly reading MAVLink traffic.

### Attitude State

`ATTITUDE` telemetry provides:

- roll,
- pitch,
- yaw,
- roll rate,
- pitch rate,
- yaw rate.

The reusable state layer stores these values in radians and radians per second.

Unit conversion for presentation or application-specific interfaces can be performed by higher-level consumers when required.

### Position State

`GLOBAL_POSITION_INT` is decoded into:

- latitude and longitude in degrees,
- altitude in metres,
- relative altitude in metres,
- north/east/down velocity in metres per second.

`LOCAL_POSITION_NED` is decoded into:

- north position,
- east position,
- down position,
- north/east/down velocity.

The local position follows the MAVLink NED convention.

### System Health and Battery State

`SYS_STATUS` provides structured information including:

- battery voltage,
- battery current,
- remaining battery percentage,
- communication drop rate,
- communication errors,
- sensor-present mask,
- sensor-enabled mask,
- sensor-health mask.

`BATTERY_STATUS` provides additional battery information including:

- battery ID,
- consumed current,
- consumed energy,
- remaining percentage,
- battery fault bitmask.

The Vehicle State Manager records this information but does not decide whether a particular value requires a warning or failsafe action.

Health interpretation and response policy belong to the higher-level AirMouse health and safety architecture.

### MAVLink Unknown Values

MAVLink uses sentinel values for some unavailable measurements.

The Vehicle State Manager converts supported unknown values to `None` rather than exposing them as apparently valid physical measurements.

Examples currently handled include:

- unknown `SYS_STATUS.voltage_battery`,
- unknown `SYS_STATUS.current_battery`,
- unknown battery remaining percentage,
- unknown consumed current,
- unknown consumed energy.

This prevents downstream modules from accidentally treating unavailable telemetry as genuine sensor data.

### State Snapshots and Thread Safety

State updates and snapshot retrieval are protected by a lock.

Consumers retrieve vehicle state using:

    get_state()

The returned state is a snapshot of the current structured state.

The snapshot does not expose the internal section dictionaries directly, preventing consumers from accidentally modifying the Vehicle State Manager's internal state.

Each populated state section also records an `updated_at` monotonic timestamp.

These timestamps can later support telemetry-age and stale-data detection.

### Lifecycle

The Vehicle State Manager provides:

- `start()`
- `stop()`
- `is_started`

`start()` subscribes the manager to all required MAVLink message types.

Duplicate starts are rejected.

`stop()` removes the subscriptions cleanly.

Repeated stops are safe, and the manager can subsequently be restarted.

Stopping the manager does not currently erase the most recently stored state.

### SITL Verification

The Vehicle State Manager has been verified with real ArduPilot SITL telemetry through the complete AirMouse MAVLink receive architecture:

    ArduPilot SITL
          |
          v
    Connection Manager
          |
          v
      Message Router
          |
          v
    Vehicle State Manager

Real SITL verification successfully populated:

- flight state,
- attitude state,
- global position,
- local NED position,
- system health,
- battery state.

Testing also confirmed:

- correct MAVLink unit scaling,
- flight-mode decoding,
- armed-state decoding,
- MAVLink unknown-value handling,
- thread-safe state snapshots,
- snapshot isolation,
- lifecycle behaviour,
- subscription cleanup,
- restart behaviour,
- zero router callback errors during the verified integration run,
- clean shutdown of the complete telemetry pipeline.

The repository includes:

- `test_vehicle_state.py`
- `test_vehicle_state_sitl.py`

### Physical-Drone Portability

The reusable `VehicleStateManager` contains no SITL-specific connection string and does not establish a MAVLink transport.

It receives standard MAVLink messages exclusively through the Message Router.

The intended transition is therefore:

    Development:

    ArduPilot SITL
          |
          v
    Connection Manager
          |
          v
      Message Router
          |
          v
    Vehicle State Manager

    Physical Aircraft:

    Pixhawk / Flight Controller
          |
          v
    Connection Manager
          |
          v
      Message Router
          |
          v
    Vehicle State Manager

The transport configuration may change during physical-aircraft integration, but the Vehicle State Manager's core state-decoding architecture is intended to remain unchanged.

Physical-aircraft validation will still be required because real sensor behaviour, message availability, timing, battery configuration, estimator state, and hardware-specific conditions may differ from SITL.

---

## MAVLink Command Manager

### Purpose

The `MAVLinkCommandManager` provides the centralized command and mode-control layer for the AirMouse V1 MAVLink architecture.

Its responsibility is to transmit vehicle commands while coordinating command acknowledgements and resulting vehicle-state changes without directly consuming MAVLink receive traffic.

The Command Manager therefore separates command transmission from telemetry reception.

The intended architecture is:

    Command / Mission Logic
             |
             v
      Command Manager
        /         \
       v           v
    MAVLink      Vehicle State
    Commands      Manager
       |             ^
       v             |
    Flight         Message
    Controller      Router
       |             ^
       +-------------+

The Message Router remains the sole continuous MAVLink receive owner.

The Command Manager does not call:

- `recv_match()`
- `wait_heartbeat()`
- `mavlink_connection()`

This prevents competing MAVLink consumers from stealing telemetry or command acknowledgements from one another.

### Dependencies

The Command Manager is constructed using three existing AirMouse components:

    MAVLinkCommandManager(
        connection,
        router,
        vehicle_state,
    )

These provide:

- `connection` — the verified pymavlink connection used for MAVLink transmission,
- `router` — the centralized MAVLink Message Router,
- `vehicle_state` — the centralized Vehicle State Manager.

The Command Manager does not create its own MAVLink connection.

This keeps transport ownership separate from command logic and supports later migration from SITL to physical flight-controller communication.

### Lifecycle

The Command Manager provides:

- `start()`
- `stop()`
- `is_started`

`start()` subscribes the manager to routed `COMMAND_ACK` messages.

Duplicate starts are rejected.

`stop()` removes the `COMMAND_ACK` subscription cleanly.

Repeated stops are safe.

Commands requiring routed acknowledgements must not be transmitted through the manager before it has been started.

### COMMAND_LONG Transactions

Generic MAVLink `COMMAND_LONG` operations are transmitted through:

    send_command_long()

The method accepts:

- the MAVLink command ID,
- parameters 1 through 7,
- an acknowledgement timeout.

The transaction flow is:

    Command request
          |
          v
    Command Manager
          |
          | COMMAND_LONG
          v
    Flight Controller
          |
          | COMMAND_ACK
          v
     Message Router
          |
          v
    Command Manager

Before transmitting a command, any previously stored acknowledgement for the same command ID is cleared.

The command is then transmitted using the existing verified MAVLink connection.

The manager waits for the matching acknowledgement delivered through the Message Router.

If no acknowledgement arrives within the configured timeout, a `TimeoutError` is raised.

### Routed COMMAND_ACK Handling

The Command Manager subscribes to:

    COMMAND_ACK

The Message Router delivers acknowledgements to:

    _handle_command_ack()

Received acknowledgements are stored according to their MAVLink command ID.

Waiting command operations are coordinated using a threading condition.

The public acknowledgement wait operation is:

    wait_for_command_ack()

A successfully retrieved acknowledgement is consumed and removed from the internal acknowledgement store.

This prevents an old acknowledgement from being reused by a later transaction.

Returned acknowledgement information includes:

- command ID,
- MAVLink result value,
- decoded MAVLink result name.

Examples of MAVLink result states include:

- `MAV_RESULT_ACCEPTED`
- `MAV_RESULT_DENIED`
- `MAV_RESULT_FAILED`
- other result values defined by the active MAVLink dialect.

### Command Transaction Serialization

MAVLink `COMMAND_ACK` correlation is primarily based on command ID.

To prevent concurrent command transactions from consuming or overwriting one another's acknowledgements, `COMMAND_LONG` transactions are serialized using an internal command lock.

The transaction boundary is effectively:

    acquire command lock
            |
            v
    clear stale ACK
            |
            v
    transmit command
            |
            v
    wait for routed ACK
            |
            v
    consume ACK
            |
            v
    release command lock

Testing confirmed that a second command transaction remains blocked while the first transaction is waiting for completion.

After the first transaction completes, the next command is allowed to transmit.

This deliberately favors deterministic command handling over parallel command transmission.

### Vehicle-State Confirmation

A successful MAVLink acknowledgement confirms that the flight controller processed or accepted a command request.

It does not by itself prove that the aircraft has reached the requested state.

For state-changing operations, AirMouse therefore performs a second verification step using the centralized Vehicle State Manager.

The resulting pattern is:

    Send request
        |
        v
    Receive acknowledgement
        |
        v
    Verify actual vehicle state

This distinction is important for reliable autonomous operation.

### Armed-State Confirmation

The Command Manager provides:

    wait_for_armed_state()

This method does not receive MAVLink heartbeats directly.

Instead, it repeatedly retrieves the current snapshot from the Vehicle State Manager and checks the routed flight state.

It can confirm either:

- ARMED
- DISARMED

The returned state information includes:

- armed state,
- system ID,
- component ID,
- current flight mode.

If the requested state is not observed within the configured timeout, a `TimeoutError` is raised.

### ARM Operation

The public arming operation is:

    arm()

Arming uses:

    MAV_CMD_COMPONENT_ARM_DISARM

with:

    param1 = 1

The transaction is:

    ARM request
        |
        v
    COMMAND_LONG
        |
        v
    COMMAND_ACK
        |
        v
    Check ACK result
        |
        v
    Vehicle State Manager
        |
        v
    Confirm ARMED

If the acknowledgement is not `MAV_RESULT_ACCEPTED`, the operation reports failure and does not wait for an armed-state transition.

If the acknowledgement is accepted, the manager waits for routed vehicle telemetry to confirm that the aircraft actually became armed.

### DISARM Operation

The public disarming operation is:

    disarm()

Disarming uses:

    MAV_CMD_COMPONENT_ARM_DISARM

with:

    param1 = 0

The transaction is:

    DISARM request
        |
        v
    COMMAND_LONG
        |
        v
    COMMAND_ACK
        |
        v
    Check ACK result
        |
        v
    Vehicle State Manager
        |
        v
    Confirm DISARMED

As with arming, command acceptance and actual vehicle-state transition are treated as separate stages.

### Flight-Mode State Confirmation

The Command Manager provides:

    wait_for_mode()

Requested mode names are normalized to uppercase.

The method reads routed state snapshots from the Vehicle State Manager until the requested flight mode is observed.

It does not directly consume MAVLink `HEARTBEAT` messages.

If the requested mode is not observed within the configured timeout, a `TimeoutError` is raised.

### SET_MODE Operation

The public flight-mode operation is:

    set_mode()

The requested mode is first validated against the flight controller's available mode mapping.

Unsupported modes are rejected before any MAVLink mode-change request is transmitted.

Valid mode changes are transmitted using:

    set_mode_send()

with:

    MAV_MODE_FLAG_CUSTOM_MODE_ENABLED

After transmission, the Command Manager waits for the Vehicle State Manager to confirm the requested mode through routed telemetry.

The complete mode-change flow is:

    Requested mode
          |
          v
    Validate mode mapping
          |
          v
      SET_MODE
          |
          v
    Flight Controller
          |
          v
    HEARTBEAT telemetry
          |
          v
     Message Router
          |
          v
    Vehicle State Manager
          |
          v
    Command Manager
          |
          v
    Confirm requested mode

This preserves centralized MAVLink receive ownership while still verifying the real vehicle state.

### Failure and Timeout Behaviour

The Command Manager distinguishes several failure classes.

A missing `COMMAND_ACK` produces an acknowledgement timeout.

A rejected command acknowledgement causes the command operation to report failure without waiting for a state transition.

An accepted command followed by failure to observe the requested vehicle state produces a state-confirmation timeout.

An unsupported flight mode is rejected before transmission.

These distinctions are important because:

    command transmitted

does not necessarily mean:

    command accepted

and:

    command accepted

does not necessarily mean:

    requested physical state reached

The architecture keeps these stages explicitly separate.

### SITL Verification

The Command Manager has been tested against real ArduPilot SITL through the complete AirMouse MAVLink pipeline.

ARM/DISARM integration verified:

    DISARMED
        |
        v
      ARM
        |
        v
    COMMAND_ACK accepted
        |
        v
    Vehicle State = ARMED
        |
        v
     DISARM
        |
        v
    COMMAND_ACK accepted
        |
        v
    Vehicle State = DISARMED

SET_MODE integration verified:

    STABILIZE
        |
        v
      GUIDED
        |
        v
    Vehicle State = GUIDED
        |
        v
     STABILIZE
        |
        v
    Vehicle State = STABILIZE

Testing confirmed:

- real `COMMAND_LONG` transmission to ArduPilot SITL,
- routed `COMMAND_ACK` handling,
- acknowledgement timeout behaviour,
- acknowledgement consumption,
- rejected acknowledgement handling,
- command transaction serialization,
- routed armed-state confirmation,
- real ARM transition,
- real DISARM transition,
- routed mode-state confirmation,
- unsupported-mode rejection,
- real STABILIZE-to-GUIDED transition,
- real GUIDED-to-STABILIZE transition,
- continued concurrent telemetry processing,
- Message Router remaining the sole continuous MAVLink receive owner,
- clean shutdown of the command and telemetry pipeline.

The repository includes Command Manager tests covering:

- vehicle-state waiting,
- mode-state waiting,
- SET_MODE behaviour,
- ARM/DISARM behaviour,
- rejected acknowledgements,
- ARM/DISARM SITL integration,
- SET_MODE SITL integration.

### Physical-Drone Portability

The Command Manager contains no hard-coded SITL connection string and does not create its own MAVLink transport.

Instead, it receives an already established connection from the Connection Manager.

The development architecture is:

    ArduPilot SITL
          |
          v
    Connection Manager
          |
          +------------------+
          |                  |
          v                  v
    Message Router      Command Manager
          |                  |
          v                  |
    Vehicle State <----------+

The intended physical-aircraft architecture is:

    Pixhawk / Flight Controller
          |
          v
    Connection Manager
          |
          +------------------+
          |                  |
          v                  v
    Message Router      Command Manager
          |                  |
          v                  |
    Vehicle State <----------+

During physical-aircraft integration, the transport configuration can change from the SITL UDP endpoint to the appropriate Pixhawk USB, serial, or UART connection.

The reusable Command Manager command logic is intended to remain transport-independent.

Physical-aircraft validation will still be mandatory because real hardware introduces conditions not fully represented by SITL, including:

- physical arming checks,
- safety-switch behaviour,
- sensor-health requirements,
- estimator readiness,
- battery conditions,
- RC or GCS interactions,
- flight-controller parameters,
- hardware failsafes,
- communication latency,
- real actuator and vehicle state.

The transition plan remains:

    SITL validation
          |
          v
    Bench / hardware integration
          |
          v
    HIL or controlled validation
          |
          v
    Controlled physical testing
          |
          v
    Flight testing


## Health / Fail-Safe Monitor

The AirMouse Health / Fail-Safe Monitor provides a transport-independent safety assessment layer above the Vehicle State Manager.

Implementation:

    flight_control/mavlink/health_monitor.py

The monitor does not receive MAVLink messages directly and does not transmit MAVLink commands.

Instead, it evaluates structured state snapshots produced by the Vehicle State Manager.

The architecture is:

    ArduPilot SITL / Physical Flight Controller
                    |
                    v
            Connection Manager
                    |
                    v
              Message Router
                    |
                    v
          Vehicle State Manager
                    |
                    v
        Health / Fail-Safe Monitor
                    |
                    v
          Health / Safety Decision

This separation keeps MAVLink transport, telemetry decoding, health assessment, and command execution as distinct responsibilities.

### Health States

The monitor classifies health using four states:

- `HEALTHY`
- `WARNING`
- `CRITICAL`
- `UNKNOWN`

`UNKNOWN` is intentionally preserved rather than treating missing telemetry as healthy.

This prevents unavailable information from silently becoming a false indication of safety.

### Heartbeat Freshness

The monitor evaluates the age of the most recently routed flight-controller heartbeat using the monotonic `updated_at` timestamp stored by the Vehicle State Manager.

Default thresholds are:

    Warning age:   > 2 seconds
    Critical age:  > 5 seconds

The resulting states are:

    age <= 2 s          -> HEALTHY
    2 s < age <= 5 s   -> WARNING
    age > 5 s           -> CRITICAL
    no heartbeat        -> UNKNOWN

Using monotonic timestamps prevents wall-clock adjustments from affecting telemetry-age calculations.

### System-Health Freshness

`SYS_STATUS` freshness is evaluated independently from heartbeat freshness.

Default thresholds are:

    Warning age:   > 3 seconds
    Critical age:  > 6 seconds

The resulting states are:

    age <= 3 s          -> HEALTHY
    3 s < age <= 6 s   -> WARNING
    age > 6 s           -> CRITICAL
    no telemetry        -> UNKNOWN

This allows the system to distinguish between a live flight controller and stale health telemetry.

### Battery-Level Evaluation

Battery percentage is evaluated using:

1. `BATTERY_STATUS` when available,
2. `SYS_STATUS` as a fallback.

Default thresholds are:

    Above 30%       -> HEALTHY
    21% to 30%      -> WARNING
    20% or below    -> CRITICAL
    unavailable     -> UNKNOWN

`BATTERY_STATUS` has priority when both sources provide a remaining-battery percentage.

These thresholds are configurable and should be treated as development defaults rather than final physical-aircraft battery policy.

### Sensor-Health Evaluation

Sensor health is evaluated from the MAVLink sensor bitmasks provided through `SYS_STATUS`.

The monitor considers sensors that are both:

- present, and
- enabled.

If every required sensor reports healthy, the result is:

    HEALTHY

If one or more enabled and present sensors report unhealthy, the result is:

    CRITICAL

If the required sensor-health information is unavailable, the result is:

    UNKNOWN

Disabled sensors are not incorrectly treated as failed required sensors.

### Overall Health Assessment

The `evaluate()` method obtains one Vehicle State snapshot and evaluates:

- heartbeat freshness,
- system-health freshness,
- battery level,
- sensor health.

The overall severity precedence is:

    CRITICAL
        |
        v
    WARNING
        |
        v
    UNKNOWN
        |
        v
    HEALTHY

Therefore:

- any `CRITICAL` check makes the overall result `CRITICAL`,
- otherwise any `WARNING` check makes it `WARNING`,
- otherwise any `UNKNOWN` check makes it `UNKNOWN`,
- only an entirely healthy assessment becomes `HEALTHY`.

Using one state snapshot per overall evaluation prevents different checks from unintentionally evaluating different telemetry snapshots.

### Fail-Safe Policy Decisions

The monitor maps overall health states to policy decisions:

    HEALTHY   -> CONTINUE
    WARNING   -> CAUTION
    UNKNOWN   -> HOLD
    CRITICAL  -> FAILSAFE

These decisions represent safety policy outputs.

They do not directly transmit flight-control commands.

This distinction is intentional.

For example:

    CRITICAL
        |
        v
    FAILSAFE decision

does not automatically mean:

    RTL

or:

    LAND

or:

    DISARM

The appropriate physical response depends on vehicle state, altitude, flight phase, available navigation, mission context, hardware configuration, and the type of failure.

Actual command execution remains the responsibility of a higher-level safety/control layer using the Command Manager.

This prevents the health-monitoring layer from unexpectedly controlling the aircraft.

### Fail-Safe Causes

The fail-safe decision also identifies the checks responsible for the current policy decision.

Each reported cause contains:

- check name,
- health status,
- reason.

Only causes matching the effective overall severity are selected.

For example, if the assessment contains:

    heartbeat = CRITICAL
    battery   = WARNING
    sensors   = UNKNOWN

the overall status becomes:

    CRITICAL

and the fail-safe causes identify the critical heartbeat condition rather than mixing lower-severity conditions into the primary failure cause.

Multiple causes at the same effective severity are preserved.

### State Snapshot Isolation

Health assessments are returned as snapshots.

External modification of a returned health structure does not modify the monitor's stored assessment.

This follows the same defensive-state approach used by the Vehicle State Manager.

### SITL Verification

The Health / Fail-Safe Monitor has been verified against real telemetry from ArduPilot SITL through the complete receive architecture:

    ArduPilot SITL
          |
          v
    Connection Manager
          |
          v
      Message Router
          |
          v
    Vehicle State Manager
          |
          v
    Health / Fail-Safe Monitor

The verified SITL run successfully evaluated:

- real heartbeat freshness,
- real `SYS_STATUS` freshness,
- real battery state,
- real sensor-health masks,
- overall health,
- fail-safe policy.

During the verified integration run, the system reported:

    Overall status: HEALTHY
    Heartbeat:      HEALTHY
    System health:  HEALTHY
    Battery:        HEALTHY
    Sensors:        HEALTHY
    Decision:       CONTINUE

Testing also confirmed:

- no Message Router subscriber errors,
- no direct MAVLink receive ownership inside the Health Monitor,
- no MAVLink command transmission from the Health Monitor,
- clean shutdown of the telemetry pipeline.

The repository includes tests covering:

- heartbeat freshness,
- system-health freshness,
- battery-level evaluation,
- sensor-health evaluation,
- overall health aggregation,
- fail-safe policy mapping,
- fail-safe cause selection,
- real SITL integration.

### Receive and Command Ownership

The Health / Fail-Safe Monitor does not call `recv_match()`.

The centralized Message Router remains the sole continuous MAVLink receive owner.

The monitor also does not call MAVLink command transmission functions.

Its responsibility is:

    Observe structured state
            |
            v
       Assess health
            |
            v
      Produce policy

not:

    Receive MAVLink directly

and not:

    Control the aircraft directly

This separation reduces concurrency risk and keeps safety-policy logic independently testable.

### Physical-Drone Portability

The reusable Health / Fail-Safe Monitor contains:

- no SITL connection string,
- no UDP-specific logic,
- no serial-specific logic,
- no direct Pixhawk dependency,
- no MAVLink receive loop,
- no direct command transmission.

It consumes only structured Vehicle State snapshots.

The development architecture is:

    ArduPilot SITL
          |
          v
    Connection Manager
          |
          v
      Message Router
          |
          v
    Vehicle State Manager
          |
          v
    Health / Fail-Safe Monitor

The intended physical-aircraft architecture is:

    Pixhawk / Flight Controller
          |
          v
    Connection Manager
          |
          v
      Message Router
          |
          v
    Vehicle State Manager
          |
          v
    Health / Fail-Safe Monitor

The core Health Monitor architecture is therefore intended to remain unchanged when moving from SITL to the physical AirMouse aircraft.

Physical-aircraft validation will still be mandatory.

In particular, development thresholds must be reviewed against the real aircraft's:

- battery chemistry,
- cell count,
- battery capacity,
- voltage behaviour under load,
- telemetry rates,
- sensor configuration,
- estimator configuration,
- flight-controller parameters,
- expected communication latency,
- hardware failsafes,
- mission requirements.

The final physical-aircraft fail-safe response must also be validated separately before automatic actions such as HOLD, RTL, LAND, or other recovery behaviour are enabled.

The transition remains:

    SITL validation
          |
          v
    Bench / hardware integration
          |
          v
    HIL or controlled validation
          |
          v
    Controlled physical testing
          |
          v
    Flight testing
