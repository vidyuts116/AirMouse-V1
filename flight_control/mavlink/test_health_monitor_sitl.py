import time

from connection_manager import MAVLinkConnectionManager
from message_router import MAVLinkMessageRouter
from vehicle_state import VehicleStateManager
from health_monitor import HealthFailSafeMonitor


CONNECTION = "udpin:127.0.0.1:14550"
COLLECTION_TIME = 5


print(
    "AirMouse V1 - Health / Fail-Safe Monitor "
    "SITL Integration Test"
)

print(f"Connecting to {CONNECTION} ...")


connection_manager = MAVLinkConnectionManager(
    CONNECTION
)

connection_info = connection_manager.connect(
    heartbeat_timeout=10,
)

print(
    "Connected to MAVLink system "
    f"{connection_info['system_id']}, "
    f"component {connection_info['component_id']}."
)


connection = connection_manager.get_connection()

router = MAVLinkMessageRouter(
    connection
)

vehicle_state = VehicleStateManager(
    router
)

health_monitor = HealthFailSafeMonitor(
    vehicle_state
)


try:
    print("\nStarting Vehicle State Manager...")
    vehicle_state.start()

    print(
        "Starting centralized MAVLink "
        "Message Router..."
    )
    router.start()

    print(
        f"\nCollecting real SITL telemetry for "
        f"{COLLECTION_TIME} seconds..."
    )

    time.sleep(COLLECTION_TIME)

    print("\nEvaluating real routed vehicle state...")

    health = health_monitor.evaluate()

    decision = (
        health_monitor.determine_failsafe_decision(
            health
        )
    )

finally:
    print("\nStopping telemetry pipeline...")

    if router.is_running:
        router.stop()

    if vehicle_state.is_started:
        vehicle_state.stop()

    if connection_manager.is_connected:
        connection_manager.disconnect()


print("\n===== HEALTH ASSESSMENT =====")

print(
    f"Overall status: "
    f"{health['overall_status']}"
)

print(
    f"Evaluated at: "
    f"{health['evaluated_at']}"
)


print("\n===== INDIVIDUAL CHECKS =====")

for name, check in health["checks"].items():

    print(f"\n[{name.upper()}]")

    for key, value in check.items():
        print(f"{key}: {value}")


print("\n===== FAIL-SAFE POLICY =====")

print(
    f"Health status: "
    f"{decision['health_status']}"
)

print(
    f"Decision: "
    f"{decision['decision']}"
)

print("Causes:")

if decision["causes"]:
    for cause in decision["causes"]:
        print(
            f"  {cause['check']}: "
            f"{cause['status']} - "
            f"{cause['reason']}"
        )
else:
    print("  None")


print("\n===== VALIDATION =====")


required_checks = {
    "heartbeat",
    "system_health",
    "battery",
    "sensors",
}

actual_checks = set(
    health["checks"].keys()
)

if actual_checks != required_checks:
    raise SystemExit(
        "FAIL: Health assessment did not contain "
        "the expected checks."
    )

print(
    "PASS: All expected health checks evaluated."
)


valid_statuses = {
    health_monitor.HEALTHY,
    health_monitor.WARNING,
    health_monitor.CRITICAL,
    health_monitor.UNKNOWN,
}

for name, check in health["checks"].items():

    if check["status"] not in valid_statuses:
        raise SystemExit(
            f"FAIL: Invalid health status for "
            f"{name}: {check['status']}"
        )

print(
    "PASS: All individual health statuses valid."
)


if health["overall_status"] not in valid_statuses:
    raise SystemExit(
        "FAIL: Invalid overall health status."
    )

print(
    "PASS: Overall health status valid."
)


valid_decisions = {
    health_monitor.CONTINUE,
    health_monitor.CAUTION,
    health_monitor.HOLD,
    health_monitor.FAILSAFE,
}

if decision["decision"] not in valid_decisions:
    raise SystemExit(
        "FAIL: Invalid fail-safe policy decision."
    )

print(
    "PASS: Fail-safe policy decision valid."
)


expected_decision = {
    health_monitor.HEALTHY:
        health_monitor.CONTINUE,

    health_monitor.WARNING:
        health_monitor.CAUTION,

    health_monitor.UNKNOWN:
        health_monitor.HOLD,

    health_monitor.CRITICAL:
        health_monitor.FAILSAFE,
}[health["overall_status"]]


if decision["decision"] != expected_decision:
    raise SystemExit(
        "FAIL: Fail-safe decision does not match "
        "overall health status."
    )

print(
    "PASS: Fail-safe policy matches "
    "overall health status."
)


heartbeat = health["checks"]["heartbeat"]

if heartbeat["status"] == health_monitor.UNKNOWN:
    raise SystemExit(
        "FAIL: Real SITL heartbeat was not "
        "available to Health Monitor."
    )

print(
    "PASS: Real routed SITL heartbeat "
    "evaluated."
)


system_health = health["checks"][
    "system_health"
]

if (
    system_health["status"]
    == health_monitor.UNKNOWN
):
    raise SystemExit(
        "FAIL: Real SITL SYS_STATUS was not "
        "available to Health Monitor."
    )

print(
    "PASS: Real routed SITL system-health "
    "telemetry evaluated."
)


callback_errors = router.get_callback_errors()

if callback_errors:
    raise SystemExit(
        "FAIL: Router callback errors recorded: "
        f"{callback_errors}"
    )

print(
    "PASS: No Message Router subscriber errors."
)


if router.is_running:
    raise SystemExit(
        "FAIL: Router remained active "
        "after shutdown."
    )

if vehicle_state.is_started:
    raise SystemExit(
        "FAIL: Vehicle State Manager remained "
        "subscribed after shutdown."
    )

if connection_manager.is_connected:
    raise SystemExit(
        "FAIL: MAVLink connection remained "
        "active after shutdown."
    )

print(
    "PASS: Complete telemetry pipeline "
    "shut down cleanly."
)


print(
    "\nPASS: Health / Fail-Safe Monitor "
    "SITL integration completed."
)
