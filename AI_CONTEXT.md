# AirMouse V1 — AI Engineering Context

## Purpose of This File

This file is the primary orientation document for AI assistants working
with the AirMouse V1 repository.

It exists so that AI systems such as ChatGPT, Claude, Gemini, coding
agents, and IDE assistants can understand the project before proposing
changes.

The Git repository and verified test evidence are authoritative.

AI conversation history is not authoritative.

If this file conflicts with current source code or newer verified
repository documentation, inspect the repository and use the newer
verified evidence.

Do not assume that a component is complete merely because code,
documentation, or instructions exist.

AirMouse uses the following engineering states:

- PLANNED — identified but not started
- IN PROGRESS — implementation or testing underway
- IMPLEMENTED — exists but is not necessarily fully verified
- VERIFIED — demonstrated to perform its intended function
- INTEGRATED — connected to relevant subsystems and verified as part of
  the larger system

Previously VERIFIED functionality must not be discarded, reinstalled,
rewritten, or redesigned without evidence that a change is required.

---

## Project Identity

Project: **AirMouse V1**

AirMouse V1 is a modular GPS-denied autonomous multirotor UAV research
and development platform.

The project is being developed simulation-first and is intended to move
progressively toward physical hardware.

The long-term system is intended to combine:

- flight control
- inertial sensing
- onboard perception
- localisation
- mapping
- autonomous navigation
- mission logic
- health monitoring
- fail-safe behaviour
- telemetry logging
- modular payload interfaces

The central engineering objective is not merely to make individual
software packages run.

The objective is a verified closed loop:

    SENSE
      |
      v
    LOCALISE
      |
      v
    UNDERSTAND
      |
      v
    PLAN
      |
      v
    COMMAND
      |
      v
    FLIGHT CONTROLLER
      |
      v
    VEHICLE
      |
      +----------> SENSE AGAIN

---

## Competition / Mission Context

AirMouse V1 is being developed for a GPS-denied indoor autonomous UAV
use case.

The target operating concept includes:

- indoor operation
- GPS/GNSS unavailable or intentionally excluded
- autonomous navigation
- mapping
- localisation
- obstacle-aware movement
- survivor or target detection as later mission capability
- live system information at the ground-control side
- operation without dependence on cloud connectivity

Autonomy, SLAM, perception, Gazebo integration, and the complete
distributed closed loop are not yet to be assumed complete merely from
this objective.

---

## Engineering Workflow

AirMouse development follows:

    Understand / Explain
            |
            v
          Design
            |
            v
        Implement
            |
            v
           Test
            |
            v
          Debug
            |
            v
          Verify
            |
            v
        Document
            |
            v
          Commit
            |
            v
        Integrate

AI assistants must preserve this workflow.

Do not provide unexplained command dumps when teaching or implementing a
new subsystem.

For significant work, explain:

1. what is being built,
2. why AirMouse needs it,
3. how it fits the architecture,
4. what files or interfaces are involved,
5. what the command or code does,
6. what result is expected,
7. how the result will be verified,
8. what failure would mean,
9. what should be documented,
10. when the change is ready to commit.

Generated code is not proof of completion.

Terminal or test evidence is required before changing a component's
status to VERIFIED.

---

## Team Ownership

### Rohit

Role:

**Flight Control & System Integration Lead**

Primary ownership:

- ArduPilot / ArduCopter
- SITL
- MAVProxy / MAVLink
- flight-controller integration
- flight modes
- command handling
- flight safety and fail-safe integration
- GPS-denied flight-controller configuration
- autonomy-to-flight-controller interface
- system integration
- end-to-end testing
- architecture coordination

### Arif Sir

Role:

**Simulation, Environment & Virtual Sensor Lead**

Primary ownership:

- Gazebo
- UAV simulation model
- indoor environment
- simulation physics
- virtual sensors
- LiDAR simulation
- camera simulation
- IMU/sensor simulation where required
- Gazebo-to-ArduPilot integration

### Doshi

Role:

**ROS 2, Autonomy, Localisation & Navigation Lead**

Primary ownership:

- ROS 2 autonomy stack
- ROS nodes/packages
- sensor interfaces
- localisation
- SLAM
- mapping
- navigation
- exploration
- mission logic
- perception interfaces
- autonomy-to-flight-controller integration with Rohit

AI assistants should respect these ownership boundaries when suggesting
changes that may affect another member's subsystem.

---

## Current Development Environment

Rohit's verified development environment includes:

- Apple Silicon MacBook host
- Parallels Desktop
- Ubuntu 24.04 ARM64 / aarch64 guest
- approximately 3.8 GiB VM RAM
- approximately 3.8 GiB swap
- 2 vCPU
- ROS 2 Jazzy
- Python 3.12
- Git
- colcon
- ArduPilot SITL
- MAVProxy
- pymavlink

ArduPilot is maintained separately from this repository.

Typical local ArduPilot location:

    ~/ardupilot

Typical Python environment used for ArduPilot/MAVLink testing:

    ~/venv-ardupilot

Do not copy the complete upstream ArduPilot repository into AirMouse-V1
without an explicit architectural decision.

Resource usage matters because the development VM is constrained.

Avoid assuming that Rohit's machine should simultaneously run full
Gazebo, SLAM, perception, ArduPilot, and every other subsystem.

---

## Repository Model

The stable integration branch is:

    main

Normal development must occur on task-specific branches.

Examples:

    flight-control/<task>
    simulation/<task>
    autonomy/<task>
    ros2/<task>
    docs/<task>

Typical workflow:

    synchronize main
        |
        v
    create feature branch
        |
        v
    implement
        |
        v
    test / verify
        |
        v
    document
        |
        v
    inspect Git diff/status
        |
        v
    commit
        |
        v
    push
        |
        v
    pull request
        |
        v
    merge
        |
        v
    update local main
        |
        v
    delete completed feature branch

Do not make routine development changes directly on `main`.

Do not blindly resolve merge conflicts.

Inspect both sides and preserve verified behaviour.


---

## Current Flight-Control Architecture

The current reusable AirMouse flight-control foundation is built around
centralized MAVLink transport and receive ownership.

The production architecture is conceptually:

    External Transport Configuration
                |
                v
    MAVLinkConnectionManager
                |
                v
      MAVLinkMessageRouter
                |
        +-------+-------+----------------+
        |               |                |
        v               v                v
    VehicleState   CommandManager    DataLogger
        |
        v
    HealthFailSafeMonitor

                |
                v
         AirMouseROSAdapter
                |
                v
      Higher-Level ROS 2 Systems

The major architectural rule is:

**The Message Router owns incoming MAVLink reception for the composed
AirMouse runtime.**

New concurrent runtime components must consume MAVLink messages through
the router rather than independently calling `recv_match()` on the shared
connection.

---

## Core Foundation Modules

The current reusable foundation consists of the following major
components.

### 1. MAVLink Connection Manager

Source:

    flight_control/mavlink/connection_manager.py

Class:

    MAVLinkConnectionManager

Responsibilities:

- establish the configured MAVLink transport,
- wait for and verify a heartbeat,
- expose the verified connection,
- prevent duplicate connection establishment,
- disconnect cleanly,
- isolate transport establishment from higher-level logic.

The Connection Manager accepts its connection string externally.

It must not be redesigned around a hard-coded SITL endpoint.

This allows the same higher-level architecture to support different
transports later, including physical flight-controller communication.

---

### 2. MAVLink Message Router

Source:

    flight_control/mavlink/message_router.py

Class:

    MAVLinkMessageRouter

Responsibilities:

- own centralized incoming MAVLink reception,
- maintain message-type subscriptions,
- dispatch messages to registered consumers,
- isolate subscriber callback failures,
- provide controlled receive-loop lifecycle.

For the composed production runtime, this is the central receive owner.

Do not introduce another independent `recv_match()` consumer on the same
shared connection.

---

### 3. Vehicle State Manager

Source:

    flight_control/mavlink/vehicle_state.py

Class:

    VehicleStateManager

Responsibilities:

- subscribe to routed MAVLink telemetry,
- decode supported vehicle telemetry,
- maintain the latest structured vehicle state,
- provide thread-safe state snapshots,
- isolate downstream consumers from raw MAVLink decoding details.

Current routed state includes information derived from:

- `HEARTBEAT`
- `ATTITUDE`
- `GLOBAL_POSITION_INT`
- `LOCAL_POSITION_NED`
- `SYS_STATUS`
- `BATTERY_STATUS`

The Vehicle State Manager records state.

It does not own the MAVLink transport.

It does not make high-level health or navigation decisions.

---

### 4. MAVLink Command Manager

Source:

    flight_control/mavlink/command_manager.py

Class:

    MAVLinkCommandManager

Responsibilities include:

- command transmission,
- ARM,
- DISARM,
- flight-mode changes,
- routed `COMMAND_ACK` handling,
- command transaction serialization,
- timeout handling,
- vehicle-state confirmation after commands.

The Command Manager receives command acknowledgements through the Message
Router.

Command success must not be inferred only from transmitting a command.

Where implemented, command acknowledgement and resulting vehicle state
must be verified.

---

### 5. Health / Fail-Safe Monitor

Source:

    flight_control/mavlink/health_monitor.py

Class:

    HealthFailSafeMonitor

Responsibilities include evaluation of:

- heartbeat freshness,
- system-health telemetry freshness,
- battery condition,
- required sensor health,
- overall health status,
- fail-safe policy decision,
- concrete failure causes.

Current health states include:

- `HEALTHY`
- `WARNING`
- `UNKNOWN`
- `CRITICAL`

Current policy decisions include:

- `CONTINUE`
- `CAUTION`
- `HOLD`
- `FAILSAFE`

The Health Monitor consumes structured Vehicle State.

It does not independently receive MAVLink traffic.

---

### 6. ROS 2 Interface Adapter

Primary sources:

    ros2/src/airmouse_ros_adapter/
    interfaces/ros2/INTERFACE_CONTRACT.md

Primary runtime classes:

    AirMouseRuntime
    AirMouseROSAdapter

Responsibilities:

- compose the verified flight-control foundation,
- expose state through ROS 2,
- expose health/fail-safe information through ROS 2,
- expose supported command operations through ROS 2 services,
- preserve separation between ROS 2 and MAVLink transport details.

The ROS 2 adapter must not become a second MAVLink implementation.

Transport selection remains below the ROS 2 interface boundary.

---

### 7. MAVLink Data Logger

Source:

    flight_control/mavlink/data_logger.py

Class:

    MAVLinkDataLogger

Responsibilities:

- subscribe to selected routed MAVLink messages,
- queue telemetry without blocking the Message Router,
- persist structured telemetry asynchronously,
- expose logging statistics,
- expose writer health/failure,
- isolate storage failures from MAVLink routing.

The logger is a downstream Message Router consumer.

It does not create a MAVLink connection.

It does not call `recv_match()`.

Its storage location is externally configurable.

An empty ROS `log_path` means logging is disabled.

---

## Runtime Composition

The current ROS runtime composes the reusable foundation in:

    ros2/src/airmouse_ros_adapter/airmouse_ros_adapter/runtime.py

Current construction sequence is conceptually:

    Connection Manager
          |
          v
       connect
          |
          v
    Message Router
          |
          +--> Vehicle State
          |
          +--> Command Manager
          |
          +--> Data Logger (when configured)
          |
          +--> Health Monitor via Vehicle State
          |
          +--> ROS 2 Adapter

Subscriber components are started before the centralized router receive
loop begins.

Current runtime startup order includes:

1. establish and verify MAVLink connection,
2. construct Message Router,
3. construct Vehicle State Manager,
4. construct Health / Fail-Safe Monitor,
5. construct Command Manager,
6. construct Data Logger when logging is configured,
7. construct ROS 2 Adapter,
8. register/start Vehicle State subscriptions,
9. register/start Command Manager subscriptions,
10. register/start Data Logger subscriptions when enabled,
11. start the Message Router receive loop.

Shutdown reverses ownership carefully so downstream consumers are removed
before transport teardown.

Do not casually change lifecycle ordering.

Any lifecycle change must be justified and regression tested.

---

## Centralized MAVLink Receive Ownership

This rule is critical.

For the current composed runtime:

    MAVLink connection
            |
            v
      Message Router
            |
      routed messages
            |
       consumers

Do not implement:

    MAVLink connection
       |      |      |
       v      v      v
    State   Logger  ROS
       recv_match()
       recv_match()
       recv_match()

Multiple competing receivers on the same connection can consume messages
intended for one another and create timing-dependent failures.

New runtime telemetry consumers should therefore normally:

1. receive the existing Message Router,
2. subscribe to the required MAVLink message type,
3. process routed messages,
4. unsubscribe during shutdown.

---

## Legacy / Standalone MAVLink Utilities

The repository also contains earlier standalone development utilities,
including:

    heartbeat_monitor.py
    attitude_monitor.py
    position_monitor.py
    system_health_monitor.py
    command_interface.py

Some of these files create their own MAVLink transport or directly call
`recv_match()`.

They represent earlier development baselines, standalone diagnostic
utilities, or historical implementation stages.

Their presence does **not** mean that new production runtime components
should copy their receive architecture.

AI assistants must distinguish between:

**standalone diagnostic / historical code**

and

**current composed AirMouse runtime architecture**

before proposing changes.

Do not automatically refactor or delete these older utilities merely
because they use direct reception.

They may remain useful as standalone tests or historical verification
tools.

However, do not use their direct-receive pattern when adding a new
concurrent component to the centralized runtime.

---

## Transport and Physical-Drone Portability

Physical-drone portability is a mandatory design requirement.

Reusable flight-control logic must not depend on a specific SITL
transport endpoint.

Simulation may currently use configuration such as:

    udpin:127.0.0.1:14550

That value is deployment configuration, not an architectural constant.

A future physical AirMouse may communicate with the flight controller
through an appropriate mechanism such as:

- USB,
- serial/UART,
- telemetry link,
- network transport,
- another validated MAVLink transport.

The intended transition is:

    SITL transport
         |
         v
    Connection Manager
         |
         v
    SAME CORE LOGIC

followed later by:

    Physical transport
         |
         v
    Connection Manager
         |
         v
    SAME CORE LOGIC

Hardware-specific transport details should remain behind configuration or
appropriate adapters.

Do not rewrite:

- Message Router,
- Vehicle State,
- Command Manager,
- Health Monitor,
- Data Logger,
- ROS 2-facing behaviour

merely because the underlying transport changes.

Physical hardware communication has not yet been verified and must not be
reported as VERIFIED until actual hardware evidence exists.


---

## ROS 2 Integration Context

ROS 2 is the public integration boundary between the reusable AirMouse
flight-control foundation and future autonomy, localisation, mapping,
navigation and mission systems.

Current ROS distribution:

    ROS 2 Jazzy

Primary packages:

    ros2/src/airmouse_interfaces
    ros2/src/airmouse_ros_adapter

Interface contract:

    interfaces/ros2/INTERFACE_CONTRACT.md

The ROS 2 layer must reuse the existing flight-control foundation rather
than duplicate MAVLink transport, routing, state decoding, health policy,
or command-management logic.

### ROS 2 Data Flow

The intended current flow is:

    MAVLink Transport
          |
          v
    Connection Manager
          |
          v
    Message Router
          |
          v
    Flight-Control Core
          |
          v
    AirMouseROSAdapter
          |
          v
    ROS 2 Topics / Services
          |
          v
    Autonomy / Navigation / Mission Systems

Higher-level ROS 2 consumers should depend on the defined AirMouse ROS 2
interfaces rather than directly consuming the underlying MAVLink
connection.


### Implemented ROS 2 Topics

The current adapter publishes under the configurable vehicle namespace.

Default namespace:

    /airmouse

Implemented topics:

    /airmouse/state/flight
    /airmouse/state/attitude
    /airmouse/state/global_position
    /airmouse/state/local_position_ned
    /airmouse/state/battery
    /airmouse/state/system_health
    /airmouse/health/status
    /airmouse/health/failsafe
    /airmouse/interface/status

These interfaces expose structured AirMouse state rather than requiring
higher-level ROS 2 components to decode raw MAVLink messages.

The authoritative definitions and semantics are documented in:

    interfaces/ros2/INTERFACE_CONTRACT.md

Do not change topic names, units, coordinate conventions, field meanings,
or ownership boundaries without reviewing the interface contract and
affected consumers.


### Implemented ROS 2 Command Services

The current adapter exposes:

    /airmouse/command/arm
    /airmouse/command/disarm
    /airmouse/command/set_mode

These services delegate command execution to the existing
`MAVLinkCommandManager`.

The ROS 2 adapter must not implement a separate command path or directly
compete for MAVLink command acknowledgements.

ARM and DISARM operations verify the resulting armed state.

SET_MODE verifies the resulting flight mode.

Command failure, rejection, or timeout must be reported rather than
silently treated as success.

Long-running autonomous behaviours should not automatically be modelled
as simple services. Future navigation operations may require ROS 2
actions as defined by the interface architecture.


### ROS 2 Runtime Configuration

The production runtime receives deployment configuration through ROS 2
parameters rather than hard-coding environment-specific values.

Current parameters:

    connection_string
    heartbeat_timeout
    vehicle_namespace
    publish_rate_hz
    log_path

`connection_string` selects the MAVLink transport.

For SITL this may reference a UDP endpoint. For physical hardware it may
later reference the validated USB, serial, UART, telemetry, or network
transport.

Changing transport must not require rewriting the reusable flight-control
core.

`heartbeat_timeout` controls initial MAVLink connection verification.

`vehicle_namespace` controls the ROS 2 namespace. The current default is:

    /airmouse

`publish_rate_hz` controls adapter publication frequency.

`log_path` controls Data Logger storage. An empty value disables runtime
logging.

Deployment-specific values belong in configuration, not reusable core
logic.


### ROS 2 Architectural Boundaries

ROS 2 is an integration layer, not the owner of MAVLink transport.

Higher-level autonomy components should consume the AirMouse ROS 2
interfaces instead of bypassing them to access the shared MAVLink
connection directly.

The current ownership boundaries are:

    Connection Manager -> transport
    Message Router -> incoming MAVLink reception
    Vehicle State -> decoded vehicle state
    Command Manager -> flight-control commands
    Health Monitor -> health and fail-safe policy
    Data Logger -> telemetry persistence
    ROS 2 Adapter -> ROS-facing integration

Future SLAM, localisation, navigation, perception and mission logic belong
above these boundaries.

The current interface contract also identifies future requirements such
as odometry, IMU, camera, range data, point clouds and navigation goals.

These future interfaces must not be described as implemented until code
and verification evidence exist.


---

## Verified Current Engineering State

AI assistants must distinguish between implemented plans, verified
capabilities, and future objectives.

A capability must not be described as VERIFIED merely because code,
documentation, architecture, or a roadmap exists.

Verification requires actual test evidence.

### Verified Flight-Control Foundation

The following reusable foundation components have been implemented and
verified in the current development environment:

1. MAVLink Connection Manager
2. Centralized MAVLink Message Router
3. Vehicle State Manager
4. MAVLink Command Manager
5. Health / Fail-Safe Monitor
6. ROS 2 Interface Adapter
7. MAVLink Data Logger

These components form the current AirMouse core foundation.

The Data Logger completed isolated regression testing, live routed SITL
testing, full ROS runtime testing, receive-ownership auditing, portability
auditing, and repository integration before merge to `main`.

The seven-module foundation does not mean the complete AirMouse UAV is
finished.

It establishes the reusable flight-control and ROS-facing base required
for later simulation, autonomy and hardware integration.


### Verified SITL and ROS 2 Capabilities

ArduCopter SITL has been successfully built and launched.

The following simulated flight sequence has been demonstrated:

    STABILIZE
       |
       v
    GUIDED
       |
       v
      ARM
       |
       v
    TAKEOFF
       |
       v
     HOVER
       |
       v
      LAND
       |
       v
    AUTO DISARM

Programmatic MAVLink communication with ArduCopter SITL has been verified.

Verified capabilities include:

- heartbeat reception and decoding,
- vehicle source identification,
- armed/disarmed state decoding,
- flight-mode decoding,
- continuous attitude telemetry,
- position telemetry,
- system-health and battery telemetry,
- centralized routed MAVLink reception,
- structured vehicle-state maintenance,
- ARM/DISARM command execution,
- flight-mode command execution,
- routed command acknowledgement handling,
- command-result state confirmation,
- health and fail-safe evaluation,
- asynchronous routed telemetry logging,
- structured JSONL persistence.

The ROS 2 adapter has also been integrated with the reusable
flight-control foundation.

The production ROS runtime has successfully established a MAVLink
connection and persisted live routed telemetry through the Data Logger.

These results verify the current software foundation against SITL.

They do not constitute physical-aircraft verification.


### Not Yet Verified / Future Integration

The following must NOT currently be described as verified AirMouse
capabilities:

- Gazebo UAV simulation integration,
- completed indoor maze simulation,
- ArduPilot-to-Gazebo closed-loop integration,
- Gazebo-to-ROS 2 sensor integration,
- three-machine distributed runtime integration,
- ROS 2 discovery across the final team LAN,
- SLAM,
- autonomous localisation,
- autonomous navigation,
- autonomous exploration,
- survivor detection,
- complete mission logic,
- full GPS-denied autonomous mission execution,
- physical Pixhawk integration,
- physical sensor integration,
- hardware-in-the-loop validation,
- physical AirMouse flight,
- physical GPS-denied autonomous flight.

Some of these capabilities are planned architectural objectives.

Planned work must not be silently promoted to IMPLEMENTED, VERIFIED, or
INTEGRATED status.

When repository documents disagree about status, AI assistants should
prefer the newest direct test evidence and current source state, then
identify the documentation inconsistency rather than inventing progress.

Physical-drone communication and flight remain future verification
milestones.


### Engineering Status Interpretation

AirMouse uses explicit engineering status levels.

AI assistants must use these terms consistently.

#### PLANNED

The capability, component, test, or integration has been identified but
implementation has not begun.

A roadmap entry does not imply implementation.

#### IN PROGRESS

Implementation, configuration, experimentation, or testing is actively
underway but the required result has not yet been demonstrated.

#### IMPLEMENTED

The required code, configuration, interface, or component exists.

IMPLEMENTED does not automatically mean VERIFIED.

Code generation alone is not verification.

#### VERIFIED

The component or capability has been demonstrated to perform its intended
function through actual test evidence.

Verification should be associated with observable evidence such as:

- successful test execution,
- expected runtime behaviour,
- telemetry received,
- command response confirmed,
- interface behaviour demonstrated,
- recorded test output.

#### INTEGRATED

The verified component has been connected to the relevant AirMouse
subsystems and demonstrated to operate correctly as part of the larger
system.

Integration requires more than independently working components.

The hierarchy is conceptually:

    PLANNED
       |
       v
    IN PROGRESS
       |
       v
    IMPLEMENTED
       |
       v
    VERIFIED
       |
       v
    INTEGRATED

Do not skip status levels merely because an architecture document
describes the intended final system.

Do not mark a component VERIFIED because an AI generated its code.

Do not mark a subsystem INTEGRATED because both sides of an interface
work independently.

When uncertain, report the lower evidence-supported status and identify
what test would be required to advance it.


---

## AI Engineering Rules

This section defines how an AI assistant should work on AirMouse V1.

The purpose is not merely to generate code quickly.

The objective is to make controlled engineering changes while preserving
the verified architecture, safety boundaries, portability requirements,
documentation quality, and learning value of the project.

### Required Engineering Workflow

For substantial AirMouse development, follow:

    Understand
       |
       v
    Design
       |
       v
    Implement
       |
       v
      Test
       |
       v
      Debug
       |
       v
     Verify
       |
       v
    Document
       |
       v
     Commit

Do not jump directly from a requirement to a large code change.

Before implementation, determine:

- what problem is being solved,
- which existing component owns that responsibility,
- what interfaces already exist,
- what architectural constraints apply,
- what existing verified behaviour must be preserved,
- how the change will be tested,
- how the change affects simulation-to-hardware portability.

Prefer small, inspectable engineering increments over large speculative
rewrites.

After each meaningful increment:

1. inspect the result,
2. run the appropriate test,
3. debug failures before continuing,
4. verify the intended behaviour,
5. inspect Git diff/status,
6. document the verified result when appropriate.


### Architecture Preservation Rules

Existing VERIFIED architecture must be treated as an engineering
constraint unless evidence demonstrates that it must change.

Do not replace working architecture merely because another design appears
cleaner, newer, shorter, or more familiar.

Before modifying an existing core component, determine:

- what responsibility it currently owns,
- which components depend on it,
- what tests already protect it,
- what verified behaviour could regress,
- whether the requested change belongs in that component,
- whether the change preserves physical-drone portability.

The current ownership model must be preserved:

    Connection Manager
        owns transport establishment

    Message Router
        owns centralized incoming MAVLink reception

    Vehicle State Manager
        owns structured vehicle-state decoding and storage

    Command Manager
        owns flight-control command transactions

    Health / Fail-Safe Monitor
        owns health interpretation and fail-safe policy

    Data Logger
        owns asynchronous telemetry persistence

    ROS 2 Adapter
        owns the ROS-facing integration boundary

Do not duplicate these responsibilities in new modules without an
explicit architectural reason.

In particular, do not introduce competing MAVLink receive loops into the
composed runtime.

New concurrent MAVLink consumers should normally subscribe through the
existing Message Router.

Do not bypass Vehicle State by repeatedly decoding the same MAVLink
telemetry independently in higher-level modules when the required state
is already available.

Do not bypass Command Manager for supported flight-control operations.

Do not move transport-specific configuration into reusable higher-level
modules.

Do not make ROS 2 nodes depend directly on SITL-specific endpoints.

Do not treat standalone historical utilities as the preferred production
architecture.

If an architectural change is genuinely required:

1. explain why the existing design is insufficient,
2. identify affected components,
3. identify regression risks,
4. design the replacement or extension,
5. test it independently,
6. verify integration behaviour,
7. update the relevant documentation,
8. preserve a clear Git history.


### Physical-Drone Portability Rules

Physical-drone portability is mandatory for AirMouse V1.

New reusable core logic must be designed so that moving from ArduPilot
SITL to the physical flight controller does not require rewriting the
core architecture.

The intended model is:

    Simulation
        |
        v
    SITL MAVLink Transport
        |
        v
    Connection Manager
        |
        v
    Reusable AirMouse Core

and later:

    Physical Drone
        |
        v
    Physical MAVLink Transport
        |
        v
    Connection Manager
        |
        v
    SAME Reusable AirMouse Core

Transport and deployment details must remain configurable.

Examples of deployment-specific details include:

- UDP endpoints,
- IP addresses,
- serial device paths,
- UART interfaces,
- baud rates,
- telemetry-radio configuration,
- physical flight-controller connection details.

These values must not become architectural assumptions inside reusable
modules.

The following components should remain reusable across simulation and
physical deployment wherever their responsibility remains unchanged:

- Message Router,
- Vehicle State Manager,
- Command Manager,
- Health / Fail-Safe Monitor,
- Data Logger,
- ROS 2 Adapter.

The Connection Manager provides the boundary through which the configured
MAVLink transport is established.

Do not hard-code:

    udpin:127.0.0.1:14550

into new reusable core components.

A SITL endpoint may appear in:

- test configuration,
- launch configuration,
- runtime parameters,
- development scripts,
- documentation examples,

when it is clearly treated as deployment configuration rather than core
logic.

When physical hardware arrives, validate the actual communication
mechanism before selecting the production connection configuration.

Do not assume in advance that the final connection will use a particular
USB, serial, UART, telemetry-radio, or network configuration.

Physical-hardware verification must progress deliberately:

    Simulation Verification
            |
            v
    Bench / Hardware Interface Testing
            |
            v
    Hardware-in-the-Loop where appropriate
            |
            v
    Controlled Physical Testing
            |
            v
    Flight Testing

Simulation success must not be reported as physical-flight verification.

Hardware-specific behaviour should be isolated behind configuration,
interfaces, or adapters wherever practical.

If a future physical-flight requirement genuinely requires changing core
logic, first identify:

1. why configuration or an adapter is insufficient,
2. which verified modules are affected,
3. what simulation behaviour must remain compatible,
4. what new hardware behaviour is required,
5. what regression tests are necessary.


### Testing, Verification and Git Discipline

Generated code is not automatically verified code.

An AI assistant must not describe a component as VERIFIED merely because:

- source code was written,
- the code looks correct,
- syntax compilation succeeded,
- documentation was created,
- a test was proposed,
- a command was provided,
- another AI predicted that it should work.

Verification requires evidence from the actual development environment.

The normal validation progression should be:

    Source Inspection
          |
          v
    Syntax / Static Checks
          |
          v
    Focused Component Test
          |
          v
    Regression Test
          |
          v
    Relevant Integration Test
          |
          v
    Runtime Evidence
          |
          v
    VERIFIED

Not every change requires every level, but the evidence must match the
claim being made.

A syntax check verifies syntax.

An isolated unit test verifies the behaviour covered by that test.

A SITL integration test verifies the tested simulation path.

None of these independently verifies physical-flight behaviour.

When a command is given to the developer, wait for its actual output
before treating the command as successfully completed.

Do not invent terminal output.

Do not assume a command succeeded because it was expected to succeed.

When a test fails:

1. preserve the failure output,
2. identify the failing layer,
3. understand the likely cause,
4. make the smallest justified correction,
5. rerun the relevant test,
6. run regression checks where necessary.

Avoid fixing unrelated code while debugging a focused failure.

### Git Discipline

The `main` branch represents the stable integrated project.

Normal development should occur on task-specific branches.

Before modifying repository files:

1. verify the current branch,
2. inspect the working tree,
3. understand the current HEAD,
4. avoid overwriting unrelated work.

Before committing:

1. inspect changed files,
2. run relevant tests,
3. run `git diff --check`,
4. inspect the intended diff,
5. stage only intended files,
6. verify the staged file inventory.

Use meaningful commits describing the engineering change.

Do not silently commit unrelated generated files, build products, logs,
temporary telemetry, caches, or environment artifacts.

After a pull request is merged:

1. return to `main`,
2. fetch the remote state,
3. update `main`,
4. verify the merged commit/content,
5. verify the working tree,
6. remove the completed feature branch when appropriate.

Do not delete an unmerged branch merely because local development appears
complete.

Git history is part of the engineering record.


### Learning and Team Collaboration Rules

AirMouse V1 is both an engineering project and a learning process.

AI assistants should help team members understand the system they are
building rather than reducing development to blind command execution.

Before introducing a significant new component or concept, explain:

1. what it is,
2. why AirMouse needs it,
3. what problem it solves,
4. how it works conceptually,
5. how it connects to existing AirMouse components,
6. which team member owns the relevant responsibility,
7. what successful implementation will look like.

Commands should be accompanied by enough explanation for the developer to
understand their purpose.

Do not provide a large unexplained sequence of commands when the work can
be divided into meaningful engineering checkpoints.

Prefer:

    Explain
       |
       v
    Small Implementation
       |
       v
    Observe Result
       |
       v
    Understand Result
       |
       v
    Continue

over:

    Paste Large Script
       |
       v
    Hope It Works

When terminal output is required for the next engineering decision, stop
at that checkpoint and inspect the actual result before continuing.

Do not fabricate progress beyond the evidence supplied by the developer.

### Team Collaboration

AirMouse is divided across three primary engineering responsibilities.

Rohit owns:

- flight control,
- ArduPilot / ArduCopter,
- SITL,
- MAVLink,
- flight-controller integration,
- safety / fail-safe integration,
- cross-system integration,
- end-to-end system coordination.

Arif Sir owns:

- Gazebo,
- simulation environment,
- UAV simulation model,
- virtual sensors,
- simulation physics,
- ArduPilot-to-Gazebo simulation integration.

Doshi owns:

- ROS 2 autonomy development,
- localisation,
- SLAM,
- mapping,
- navigation,
- exploration,
- mission logic,
- autonomy-side interfaces.

These ownership boundaries help coordinate development.

They do not prohibit collaboration.

Changes affecting another member's subsystem should preserve agreed
interfaces and should not silently redesign that subsystem.

Shared interfaces are contracts between team responsibilities.

When changing a shared interface:

1. identify all affected subsystems,
2. explain why the interface must change,
3. preserve backward compatibility where reasonable,
4. update the interface documentation,
5. coordinate corresponding implementation changes,
6. verify the integration again.

The Git repository is the authoritative shared engineering record.

An AI conversation is not the project memory.

Important architecture, interface, verification, and status changes should
ultimately be represented in the repository.


---

## Next Integration Stage

The seven-module AirMouse core foundation is complete.

The project must now transition from isolated subsystem development toward
controlled integration.

This does not mean immediately combining every subsystem.

Integration must proceed incrementally so that failures can be isolated
to a specific interface or subsystem.

The broad progression is:

    Verified Core Foundation
             |
             v
    Team LAN Verification
             |
             v
    ArduPilot <-> Gazebo Integration
             |
             v
    Gazebo <-> ROS 2 Sensor Integration
             |
             v
    ROS 2 <-> AirMouse Flight-Control Integration
             |
             v
    Localisation / SLAM
             |
             v
    Navigation / Mission Logic
             |
             v
    Distributed Closed Loop
             |
             v
    Failure and Safety Testing
             |
             v
    Hardware Transition

Each boundary must be tested before depending on it for the next stage.


### Distributed Integration Model

The intended integration environment may use three Ubuntu VMs connected
through the same local network.

Conceptually:

    Rohit VM
    ArduPilot / AirMouse Flight Control
              |
              v
         Local Network
          /         \
         v           v
    Arif VM       Doshi VM
    Gazebo        ROS 2 Autonomy
    Sensors       SLAM / Navigation

Primary responsibilities remain:

    Rohit -> flight-control and system integration
    Arif  -> simulation and virtual sensors
    Doshi -> autonomy, localisation and navigation

The systems should not be connected all at once.

First verify basic bidirectional network communication between the three
VMs.

Then verify each software interface independently before attempting the
complete distributed closed loop.


### Integration Checkpoint Sequence

Distributed integration must proceed through controlled checkpoints.

Checkpoint 1 — LAN

Verify:

- all three Ubuntu VMs have valid LAN addresses,
- bidirectional connectivity works,
- required ports are reachable,
- firewalls do not block intended traffic.

Checkpoint 2 — ArduPilot and Gazebo

Verify the simulation interface between Rohit's ArduPilot environment and
Arif's Gazebo environment before involving the autonomy stack.

Checkpoint 3 — Gazebo and ROS 2

Verify that Doshi's ROS 2 environment can receive the required simulated
sensor information from the Gazebo side.

Checkpoint 4 — ROS 2 and AirMouse Flight Control

Verify that higher-level ROS 2 components can consume AirMouse state and
health interfaces and use the defined command interface.

Checkpoint 5 — Closed Loop

Only after the individual boundaries are verified should the team attempt:

    Sensors
       |
       v
    ROS 2 Autonomy
       |
       v
    AirMouse Flight Control
       |
       v
    ArduPilot
       |
       v
    Simulated Vehicle
       |
       v
    Sensors Again

Do not begin debugging the complete distributed system before its
individual communication boundaries have been verified.


### Autonomy Progression

Completion of the seven-module core foundation does not mean that the
AirMouse autonomous mission stack is complete.

After the required integration boundaries are verified, autonomy
development may progressively introduce:

- sensor interfaces,
- localisation,
- SLAM,
- mapping,
- navigation,
- exploration,
- mission logic,
- perception,
- survivor detection where required.

These capabilities must be implemented and verified incrementally.

The intended higher-level control relationship is:

    Sensors
       |
       v
    Localisation / SLAM
       |
       v
    Navigation / Mission Logic
       |
       v
    ROS 2 AirMouse Interface
       |
       v
    Flight-Control Core
       |
       v
    ArduPilot
       |
       v
    Vehicle

Higher-level autonomy should use the defined AirMouse interfaces rather
than bypassing the verified flight-control foundation.

No future autonomy capability should be marked VERIFIED until supported
by actual test evidence.
