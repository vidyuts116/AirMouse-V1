import time

from connection_manager import MAVLinkConnectionManager
from message_router import MAVLinkMessageRouter


CONNECTION = "udpin:127.0.0.1:14550"


print("AirMouse V1 - MAVLink Message Router SITL Integration Test")
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

heartbeat_count = 0
attitude_count = 0


def handle_heartbeat(message):
    global heartbeat_count
    heartbeat_count += 1


def handle_attitude(message):
    global attitude_count
    attitude_count += 1


router.subscribe("HEARTBEAT", handle_heartbeat)
router.subscribe("ATTITUDE", handle_attitude)

print("\nStarting centralized router...")
router.start()

print("Collecting SITL MAVLink traffic for 5 seconds...")
time.sleep(5)

router.stop()
manager.disconnect()

print("\n===== RESULTS =====")
print(f"HEARTBEAT messages routed: {heartbeat_count}")
print(f"ATTITUDE messages routed: {attitude_count}")

if heartbeat_count == 0:
    raise SystemExit(
        "FAIL: No HEARTBEAT messages reached the subscriber."
    )

if attitude_count == 0:
    raise SystemExit(
        "FAIL: No ATTITUDE messages reached the subscriber."
    )

if router.is_running:
    raise SystemExit(
        "FAIL: Router remained running after stop()."
    )

if manager.is_connected:
    raise SystemExit(
        "FAIL: Connection remained active after disconnect()."
    )

callback_errors = router.get_callback_errors()

if callback_errors:
    raise SystemExit(
        f"FAIL: Callback errors recorded: {callback_errors}"
    )

print("\nPASS: Real SITL MAVLink messages were centrally routed.")
print("PASS: Router and connection shut down cleanly.")
print("PASS: No subscriber errors were recorded.")

print(
    "\nPASS: MAVLink Message Router SITL integration completed."
)
