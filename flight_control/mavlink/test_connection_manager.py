from connection_manager import MAVLinkConnectionManager


CONNECTION = "udpin:127.0.0.1:14550"


print("AirMouse V1 - MAVLink Connection Manager Integration Test")
print(f"Testing connection: {CONNECTION}")

manager = MAVLinkConnectionManager(CONNECTION)


print("\nTEST 1: Initial state")

if manager.is_connected:
    raise SystemExit(
        "FAIL: New connection manager unexpectedly reports connected."
    )

print("PASS: Initial state is disconnected.")


print("\nTEST 2: Access before connection")

try:
    manager.get_connection()

except RuntimeError as error:
    print(f"PASS: Unconnected access rejected: {error}")

else:
    raise SystemExit(
        "FAIL: get_connection() succeeded before connect()."
    )


print("\nTEST 3: Establish verified connection")

connection_info = manager.connect(
    heartbeat_timeout=10,
)

print(
    f"PASS: Connected to MAVLink system "
    f"{connection_info['system_id']}, "
    f"component {connection_info['component_id']}."
)

if not manager.is_connected:
    raise SystemExit(
        "FAIL: Manager does not report connected after connect()."
    )

connection = manager.get_connection()

if connection is None:
    raise SystemExit(
        "FAIL: Verified connection object is unavailable."
    )

print("PASS: Verified connection object is available.")


print("\nTEST 4: Duplicate connection protection")

try:
    manager.connect(
        heartbeat_timeout=2,
    )

except RuntimeError as error:
    print(f"PASS: Duplicate connection rejected: {error}")

else:
    manager.disconnect()

    raise SystemExit(
        "FAIL: Duplicate connect unexpectedly succeeded."
    )


print("\nTEST 5: Disconnect and state cleanup")

manager.disconnect()

if manager.is_connected:
    raise SystemExit(
        "FAIL: Manager still reports connected after disconnect()."
    )

if manager.system_id is not None:
    raise SystemExit(
        "FAIL: System ID was not cleared after disconnect()."
    )

if manager.component_id is not None:
    raise SystemExit(
        "FAIL: Component ID was not cleared after disconnect()."
    )

print("PASS: Connection closed and state cleared.")

print(
    "\nPASS: MAVLink Connection Manager integration test completed."
)
