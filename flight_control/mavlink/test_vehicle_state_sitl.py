import time

from connection_manager import MAVLinkConnectionManager
from message_router import MAVLinkMessageRouter
from vehicle_state import VehicleStateManager


CONNECTION = "udpin:127.0.0.1:14550"
COLLECTION_TIME = 8


print("AirMouse V1 - Vehicle State SITL Integration Test")
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

router = MAVLinkMessageRouter(
    manager.get_connection()
)

vehicle_state = VehicleStateManager(router)

try:
    print("\nStarting Vehicle State Manager...")
    vehicle_state.start()

    print("Starting centralized MAVLink Message Router...")
    router.start()

    print(
        f"Collecting real SITL telemetry for "
        f"{COLLECTION_TIME} seconds..."
    )

    time.sleep(COLLECTION_TIME)

finally:
    print("\nStopping telemetry pipeline...")

    if router.is_running:
        router.stop()

    if vehicle_state.is_started:
        vehicle_state.stop()

    if manager.is_connected:
        manager.disconnect()


state = vehicle_state.get_state()


print("\n===== VEHICLE STATE SNAPSHOT =====")

for section, values in state.items():
    print(f"\n[{section.upper()}]")

    if not values:
        print("No data received.")
        continue

    for key, value in values.items():
        print(f"{key}: {value}")


print("\n===== VALIDATION =====")

required_sections = (
    "flight",
    "attitude",
    "global_position",
    "local_position",
    "system_health",
)

for section in required_sections:
    if not state[section]:
        raise SystemExit(
            f"FAIL: No state collected for {section}."
        )

print("PASS: Core vehicle-state sections populated.")

if not state["flight"].get("flight_mode"):
    raise SystemExit(
        "FAIL: Flight mode was not decoded."
    )

print(
    f"PASS: Flight mode decoded as "
    f"{state['flight']['flight_mode']}."
)

if "armed" not in state["flight"]:
    raise SystemExit(
        "FAIL: Armed state was not decoded."
    )

print(
    f"PASS: Armed state decoded as "
    f"{state['flight']['armed']}."
)

if "roll_rad" not in state["attitude"]:
    raise SystemExit(
        "FAIL: Attitude state incomplete."
    )

print("PASS: Attitude state populated.")

if "north_m" not in state["local_position"]:
    raise SystemExit(
        "FAIL: Local NED position incomplete."
    )

print("PASS: Local NED state populated.")

if "voltage_v" not in state["system_health"]:
    raise SystemExit(
        "FAIL: System-health state incomplete."
    )

print("PASS: System-health state populated.")

if state["battery"]:
    print("PASS: BATTERY_STATUS state also received.")
else:
    print(
        "INFO: BATTERY_STATUS was not received during "
        "this collection window."
    )

callback_errors = router.get_callback_errors()

if callback_errors:
    raise SystemExit(
        f"FAIL: Router callback errors recorded: "
        f"{callback_errors}"
    )

print("PASS: No Vehicle State subscriber errors.")

if router.is_running:
    raise SystemExit(
        "FAIL: Router remained active after shutdown."
    )

if vehicle_state.is_started:
    raise SystemExit(
        "FAIL: Vehicle State Manager remained subscribed."
    )

if manager.is_connected:
    raise SystemExit(
        "FAIL: MAVLink connection remained active."
    )

print("PASS: Complete telemetry pipeline shut down cleanly.")

print(
    "\nPASS: Vehicle State SITL integration test completed."
)
