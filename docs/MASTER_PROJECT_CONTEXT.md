# AirMouse V1 — Master Project Context

## 1. Project Identity

Project Name: AirMouse V1

Project Type:
GPS-denied autonomous multirotor UAV research and development platform.

AirMouse V1 is being developed as a modular UAV platform for autonomous
operation, reconnaissance, navigation research, simulation, system
integration and future experimental localisation technologies.

The project will initially be developed and validated in simulation before
progressively moving toward hardware implementation.

---

## 2. Primary Aim

The primary aim of AirMouse V1 is to develop a modular autonomous UAV
platform capable of operating in environments where conventional GPS/GNSS
navigation is unavailable, unreliable or intentionally excluded.

The platform should ultimately integrate:

- flight control,
- inertial sensing,
- onboard perception,
- localisation,
- mapping,
- autonomous navigation,
- mission logic,
- safety mechanisms,
- and modular payload interfaces.

The system must be designed so that simulation components can later be
replaced progressively by real hardware.

---

## 3. Development Philosophy

AirMouse development follows:

Explain → Implement → Test → Verify → Document → Commit → Integrate

A component is not considered complete merely because software has been
installed or code has been written.

Progress must be supported by actual test evidence.

Project status terminology:

PLANNED
Work has been identified but implementation has not begun.

IN PROGRESS
Implementation or testing is underway.

IMPLEMENTED
The component exists but has not necessarily passed complete verification.

VERIFIED
The component has been demonstrated to perform its intended function.

INTEGRATED
The component has been successfully connected to the relevant AirMouse
subsystems and verified as part of the larger system.

Previously VERIFIED components must not be reinstalled or rebuilt without
evidence that doing so is necessary.

---

## 4. Team Structure

### Rohit
Role:
Flight Control & System Integration Lead

Primary responsibilities:

- ArduPilot / ArduCopter
- Software-In-The-Loop (SITL)
- MAVProxy
- MAVLink
- flight modes
- flight-controller behaviour
- flight safety and failsafes
- GPS-denied flight-controller configuration
- autonomy-to-flight-controller interface
- cross-system integration
- end-to-end testing
- final system architecture coordination

Rohit acts as the principal integration point between the flight-control,
simulation and autonomy subsystems.

### Arif Sir
Role:
Simulation, Environment & Virtual Sensor Lead

Primary responsibilities:

- Gazebo simulation environment
- UAV simulation model
- indoor/outdoor simulation environments
- simulated sensors
- LiDAR simulation
- camera simulation where required
- IMU/sensor simulation where required
- simulation physics
- environmental testing scenarios
- ArduPilot ↔ Gazebo interface
- simulation-side debugging

### Doshi
Role:
ROS 2, Autonomy, Localisation & Navigation Lead

Primary responsibilities:

- ROS 2 autonomy stack
- ROS nodes and packages
- sensor-data interfaces
- localisation
- SLAM
- mapping
- autonomous navigation
- mission logic
- perception interfaces
- navigation planning
- ROS ↔ flight-controller interface in coordination with Rohit

---

## 5. Current Development Environment

Rohit's verified development platform:

Host:
Apple Silicon MacBook

Virtualisation:
Parallels Desktop

Guest OS:
Ubuntu 24.04.5 LTS

Architecture:
ARM64 / aarch64

Virtual-machine resources:

- approximately 3.8 GiB RAM
- approximately 3.8 GiB swap
- 2 vCPU

Graphics:

- Mesa
- virgl
- Apple M1 compatibility renderer
- accelerated rendering available
- OpenGL 4.0 core profile

Development tools verified include:

- Git 2.43.0
- GCC 13.3.0
- Python 3.12.3
- ROS 2 Jazzy
- colcon
- ArduPilot development environment
- MAVProxy

Resource constraints must be considered when running multiple simulation
components simultaneously.

---

## 6. Verified ROS 2 Baseline

The following has been VERIFIED on Rohit's Ubuntu environment:

ROS distribution:
ROS 2 Jazzy

Workspace:

~/airmouse_ws

Package:

airmouse_core

Node:

/airmouse_status_node

Topic:

/airmouse/status

Message type:

std_msgs/msg/String

Verified message:

AirMouse system online

Publishing rate:

approximately 0.5 Hz

The workspace has successfully been built using colcon and sourced.

This provides the initial ROS 2 foundation for AirMouse.

---

## 7. Verified ArduPilot Baseline

ArduPilot repository:

~/ardupilot

Python environment:

~/venv-ardupilot

The following have been VERIFIED:

- ArduPilot repository
- required submodules
- ArduPilot prerequisite installation
- sim_vehicle.py
- MAVProxy
- ArduCopter SITL build
- ArduCopter SITL launch
- MAVLink communication through MAVProxy

---

## 8. Verified Virtual Flight Test

A basic simulated ArduCopter flight sequence has been demonstrated.

Verified sequence:

1. ArduCopter SITL started.
2. MAVProxy connected.
3. STABILIZE mode available.
4. Vehicle changed to GUIDED mode.
5. Vehicle armed.
6. Simulated takeoff executed to approximately 5 metres.
7. Vehicle maintained simulated flight/hover.
8. LAND command issued.
9. Vehicle landed.
10. Vehicle automatically disarmed following landing.

This represents the initial verified flight-control baseline.

It must be preserved while higher-level systems are introduced.

---

## 9. Intended Virtual System Architecture

The complete simulation environment will eventually consist conceptually of:

ArduPilot SITL
        ↕
      MAVLink
        ↕
ROS 2 / Autonomy
        ↕
Localisation / SLAM / Navigation
        ↕
Gazebo
        ↕
Virtual UAV + Sensors + Environment

The final architecture may require appropriate middleware or interface
components between these systems.

Interfaces must be tested independently before full integration.

---

## 10. Distributed Development Architecture

The team may use three separate computers.

Each machine may run its own Ubuntu virtual machine with approximately
4 GiB RAM available to Ubuntu.

Rather than forcing one computer to run every subsystem, workloads can be
distributed.

Conceptual arrangement:

ROHIT MACHINE
ArduPilot SITL
MAVProxy / MAVLink
Flight-control integration

ARIF MACHINE
Gazebo
UAV simulation
Virtual sensors
Simulation environments

DOSHI MACHINE
ROS 2
SLAM
Localisation
Navigation
Autonomy

This distribution reduces the computational load placed on any individual
8 GB host computer.

---

## 11. Local Network Architecture

When the team is physically together, the three computers may communicate
through a common Wi-Fi router.

Internet access is not inherently required for basic LAN communication
after the required software has already been installed.

Conceptually:

                  Wi-Fi Router
                      |
          ---------------------------
          |            |            |
       Rohit VM      Arif VM      Doshi VM
       ArduPilot      Gazebo        ROS 2

The router provides the local network connecting the systems.

Before distributed simulation begins, the team must verify:

- each VM has a valid LAN IP address,
- machines can reach one another,
- required ports are reachable,
- firewalls do not block required communication,
- ROS 2 discovery works across the intended network,
- MAVLink traffic reaches the intended destination.

Actual network configuration must be documented once tested.

---

## 12. Remote Development

The three team members do not need to remain physically together for normal
software development.

Source code and documentation will be synchronised through the private
GitHub repository whenever internet access is available.

Real-time distributed simulation over the internet is a separate networking
problem and must not be assumed to work merely because GitHub collaboration
works.

Initial multi-machine simulation should therefore be validated on a common
local network.

---

## 13. Git Repository

Central repository:

AirMouse-V1

Repository owner:

vidyuts116

Repository visibility:

PRIVATE

Routine development should be performed using each member's personal
GitHub account as an authorised collaborator.

Members must not normally perform development using a shared GitHub login.

Each development machine must maintain its own Git identity.

---

## 14. Git Development Model

The `main` branch represents the stable integrated project.

Normal development should not occur directly on `main`.

Each member works through task-appropriate branches.

Typical examples:

flight-control/<task>

simulation/<task>

autonomy/<task>

Typical workflow:

1. Synchronise with the current repository.
2. Create or switch to the appropriate development branch.
3. Make a controlled change.
4. Test the change.
5. Document the result.
6. Inspect Git status.
7. Stage intended files.
8. Commit with a meaningful message.
9. Push the branch to GitHub.
10. Review/integrate through the agreed team process.

Changes should reach `main` only after appropriate verification.

---

## 15. Concurrent File Changes

Multiple team members should avoid unnecessarily editing the same file at
the same time.

Responsibility separation should reduce conflicts.

If two branches modify the same lines of the same file, Git may produce a
merge conflict.

Merge conflicts must be reviewed rather than resolved by blindly selecting
one version.

Shared architecture and interface documents should therefore be changed
deliberately.

---

## 16. Repository Structure

The intended high-level structure is:

AirMouse-V1/

README.md

docs/
    MASTER_PROJECT_CONTEXT.md
    PROJECT_STATE.md

    members/
        rohit_progress.md
        arif_progress.md
        doshi_progress.md

    architecture/
        system_architecture.md
        interfaces.md

    decisions/
        architecture_decisions.md

    testing/
        integration_tests.md

    research/
        research_candidates.md
        rf_navigation_future.md

flight_control/

simulation/

ros2/

interfaces/

tools/

Large third-party source repositories should not automatically be copied
into AirMouse-V1.

For example, the complete upstream ArduPilot repository should remain a
separate dependency unless the team deliberately adopts another dependency
management strategy.

---

## 17. Documentation Rules

Documentation is part of the engineering process, not an afterthought.

Every meaningful milestone should record:

- task,
- owner,
- date,
- configuration,
- commands where relevant,
- test performed,
- expected result,
- actual result,
- status,
- known problems,
- next action.

The repository should allow another team member to reconstruct why an
engineering decision was made.

---

## 18. AI-Assisted Development

Different members may use different AI systems.

No AI conversation should be considered the authoritative project record.

The Git repository is the common project memory.

AI assistants should use the repository documentation to understand:

- project objective,
- current architecture,
- verified progress,
- member responsibilities,
- current interfaces,
- known problems,
- next milestones.

AI assistants must not mark tasks as completed solely because instructions
or code were generated.

Verification requires evidence from the actual development environment.

---

## 19. GPS-Denied Navigation Objective

AirMouse V1 is intended to progress beyond GPS-dependent autonomous flight.

Potential navigation components may include:

- inertial sensing,
- visual perception,
- LiDAR,
- visual odometry,
- SLAM,
- sensor fusion,
- local mapping,
- obstacle detection,
- autonomous path planning.

The exact architecture must be determined experimentally rather than assumed.

---

## 20. Future RF-Based Navigation Research

A future research direction is to investigate radio-frequency-based
localisation or navigation correction for GPS-denied environments.

The broad concept is to investigate whether known or synchronised radio
references can provide measurements useful for correcting accumulated
navigation drift.

Possible future research areas include:

- radio timing measurements,
- ranging,
- time-of-flight techniques,
- synchronised reference nodes,
- multilateration,
- RF-assisted localisation,
- RF + INS fusion,
- RF + visual localisation,
- RF + SLAM correction.

This is currently a RESEARCH DIRECTION, not a verified AirMouse capability.

No accuracy, range or operational capability should be claimed until
experimentally demonstrated.

---

## 21. Hardware Direction

Virtual development precedes full hardware integration.

The intended AirMouse V1 physical platform is approximately a
500–550 mm X-frame multirotor platform.

Current design targets include approximately:

- 2.0–2.4 kg expected all-up operating mass range
- approximately 3 kg target maximum take-off mass

These remain engineering targets and must be validated against the final
propulsion, battery, structural and payload design.

The platform should support modular payload development.

Potential future payloads include:

- camera systems,
- onboard companion computer,
- Raspberry Pi-class computing,
- LiDAR,
- additional sensing,
- experimental localisation hardware.

---

## 22. Simulation-to-Hardware Strategy

Development should progress approximately through:

Phase A
Software environment and fundamentals

Phase B
ROS 2 baseline

Phase C
ArduPilot SITL baseline

Phase D
Gazebo simulation

Phase E
Virtual sensors

Phase F
ROS 2 ↔ simulation integration

Phase G
Autonomy and localisation

Phase H
ROS 2 ↔ ArduPilot control interface

Phase I
Distributed closed-loop simulation

Phase J
Failure and safety testing

Phase K
Hardware-in-the-loop / hardware transition where appropriate

Phase L
Controlled physical flight testing

Phase M
Advanced GPS-denied experiments

The exact order may change when engineering dependencies require it.

---

## 23. Research and Intellectual Property

AirMouse is also intended to provide a platform for multiple research
outputs rather than a single research paper.

Potential research areas should be recorded under:

docs/research/

Research documentation must distinguish:

- existing published methods,
- team implementation,
- experimental modifications,
- genuinely novel contributions.

Potential patentable ideas must not be described as novel merely because
they were independently conceived by the team.

Prior-art research and appropriate professional IP guidance will be required
before making patentability claims.

---

## 24. Definition of Project Success

AirMouse V1 should not be considered successful merely because individual
software packages run independently.

The important milestone is an integrated system in which:

1. The simulated or physical UAV has a functional flight controller.
2. Sensor information reaches the autonomy stack.
3. The system estimates its state/localisation.
4. Navigation logic generates appropriate commands.
5. Commands reach the flight controller.
6. The vehicle responds correctly.
7. Feedback returns to the autonomy system.
8. The loop continues safely.
9. Failures are detected and handled appropriately.
10. Results can be reproduced and documented.

Conceptually:

SENSE
  ↓
LOCALISE
  ↓
UNDERSTAND
  ↓
PLAN
  ↓
COMMAND
  ↓
FLIGHT CONTROLLER
  ↓
VEHICLE
  ↓
SENSE AGAIN

This closed loop is the central engineering objective.

---

## 25. Current Project Rule

Do not restart the roadmap merely because development moves to another
computer, another AI assistant or another conversation.

Always determine the verified current state first.

Continue from evidence.

AirMouse development follows:

Explain
   ↓
Implement
   ↓
Test
   ↓
Verify
   ↓
Document
   ↓
Commit
   ↓
Integrate
