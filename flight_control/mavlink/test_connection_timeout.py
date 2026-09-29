from connection_manager import MAVLinkConnectionManager


TEST_CONNECTION = "udpin:127.0.0.1:14999"


print("AirMouse V1 - MAVLink Connection Timeout Test")
print(f"Testing unused endpoint: {TEST_CONNECTION}")

manager = MAVLinkConnectionManager(TEST_CONNECTION)

try:
    manager.connect(
        heartbeat_timeout=2,
    )

except TimeoutError as error:
    print("\nPASS: Missing heartbeat handled correctly.")
    print(f"Reason: {error}")

else:
    manager.disconnect()

    raise SystemExit(
        "FAIL: Unexpected heartbeat received on unused endpoint."
    )


if manager.is_connected:
    raise SystemExit(
        "FAIL: Manager reports connected after timeout."
    )

if manager.system_id is not None:
    raise SystemExit(
        "FAIL: System ID retained after timeout."
    )

if manager.component_id is not None:
    raise SystemExit(
        "FAIL: Component ID retained after timeout."
    )

print("PASS: Connection state remained clean after failure.")

print(
    "\nPASS: MAVLink connection timeout test completed."
)
