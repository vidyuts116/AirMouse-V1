import time

from connection_manager import MAVLinkConnectionManager
from message_router import MAVLinkMessageRouter
from vehicle_state import VehicleStateManager
from command_manager import MAVLinkCommandManager


CONNECTION = "udpin:127.0.0.1:14550"


print("AirMouse V1 - Command Manager ARM/DISARM SITL Integration Test")
print(f"Connecting to {CONNECTION} ...")

manager = MAVLinkConnectionManager(CONNECTION)

connection_info = manager.connect(
    heartbeat_timeout=10,
)

print(
    f"Connected to MAVLink system "
    f"{connection_info['system_id']}, "
    f"component {connection_info['component_id']}."
)

connection = manager.get_connection()

router = MAVLinkMessageRouter(connection)
vehicle_state = VehicleStateManager(router)

command_manager = MAVLinkCommandManager(
    connection,
    router,
    vehicle_state,
)


print("\nStarting Vehicle State Manager...")
vehicle_state.start()

print("Starting Command Manager...")
command_manager.start()

print("Starting centralized MAVLink Message Router...")
router.start()


try:
    print("\nCollecting baseline telemetry for 2 seconds...")
    time.sleep(2)

    baseline = vehicle_state.get_state()
    flight = baseline["flight"]

    if not flight:
        raise SystemExit(
            "FAIL: No HEARTBEAT-derived flight state available."
        )

    print(f"Baseline mode: {flight.get('flight_mode')}")
    print(f"Baseline armed state: {flight.get('armed')}")

    if flight.get("armed"):
        raise SystemExit(
            "FAIL: SITL is already armed. "
            "Start this test from a DISARMED state."
        )


    print("\n===== ARM TRANSACTION =====")

    arm_result = command_manager.arm(
        ack_timeout=5,
        state_timeout=5,
    )

    print(
        "ARM ACK: "
        f"{arm_result['ack']['result_name']}"
    )

    if not arm_result["success"]:
        raise SystemExit(
            f"FAIL: ARM command rejected: {arm_result['ack']}"
        )

    if arm_result["state"]["armed"] is not True:
        raise SystemExit(
            "FAIL: ARM transaction did not confirm ARMED state."
        )

    print("PASS: ARM COMMAND_ACK accepted.")
    print("PASS: Routed vehicle state confirmed ARMED.")


    print("\nCollecting armed telemetry for 1 second...")
    time.sleep(1)

    armed_snapshot = vehicle_state.get_state()
    armed_flight = armed_snapshot["flight"]

    if armed_flight.get("armed") is not True:
        raise SystemExit(
            "FAIL: Vehicle State did not remain ARMED."
        )

    print(
        f"Current mode: {armed_flight.get('flight_mode')}"
    )
    print(
        f"Current armed state: {armed_flight.get('armed')}"
    )


    print("\n===== DISARM TRANSACTION =====")

    disarm_result = command_manager.disarm(
        ack_timeout=5,
        state_timeout=5,
    )

    print(
        "DISARM ACK: "
        f"{disarm_result['ack']['result_name']}"
    )

    if not disarm_result["success"]:
        raise SystemExit(
            f"FAIL: DISARM command rejected: "
            f"{disarm_result['ack']}"
        )

    if disarm_result["state"]["armed"] is not False:
        raise SystemExit(
            "FAIL: DISARM transaction did not confirm DISARMED state."
        )

    print("PASS: DISARM COMMAND_ACK accepted.")
    print("PASS: Routed vehicle state confirmed DISARMED.")


    print("\nCollecting final telemetry for 1 second...")
    time.sleep(1)

    final_snapshot = vehicle_state.get_state()
    final_flight = final_snapshot["flight"]

    if final_flight.get("armed") is not False:
        raise SystemExit(
            "FAIL: Final vehicle state is not DISARMED."
        )

    print(
        f"Final mode: {final_flight.get('flight_mode')}"
    )
    print(
        f"Final armed state: {final_flight.get('armed')}"
    )


finally:
    print("\nStopping command/telemetry pipeline...")

    command_manager.stop()
    vehicle_state.stop()
    router.stop()
    manager.disconnect()


print("\n===== VALIDATION =====")

if command_manager.is_started:
    raise SystemExit(
        "FAIL: Command Manager remained started."
    )

if vehicle_state.is_started:
    raise SystemExit(
        "FAIL: Vehicle State Manager remained started."
    )

if router.is_running:
    raise SystemExit(
        "FAIL: Message Router remained running."
    )

if manager.is_connected:
    raise SystemExit(
        "FAIL: MAVLink connection remained active."
    )

callback_errors = router.get_callback_errors()

if callback_errors:
    raise SystemExit(
        f"FAIL: Router callback errors recorded: {callback_errors}"
    )

print("PASS: Real ARM command transmitted to ArduPilot SITL.")
print("PASS: ARM acknowledgement returned through Message Router.")
print("PASS: Vehicle State confirmed real ARMED transition.")
print("PASS: Real DISARM command transmitted to ArduPilot SITL.")
print("PASS: DISARM acknowledgement returned through Message Router.")
print("PASS: Vehicle State confirmed real DISARMED transition.")
print("PASS: Router remained sole MAVLink receive owner.")
print("PASS: Complete pipeline shut down cleanly.")

print(
    "\nPASS: Command Manager ARM/DISARM SITL integration completed."
)
