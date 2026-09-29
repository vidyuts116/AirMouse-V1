import time

from command_interface import MAVLinkCommandInterface


CONNECTION = "udpin:127.0.0.1:14550"


print("AirMouse V1 - MAVLink Mode Control Integration Test")
print(f"Connecting to {CONNECTION} ...")

vehicle = MAVLinkCommandInterface(CONNECTION)
connection = vehicle.connect()

print(
    f"Connected to MAVLink system {connection['system_id']}, "
    f"component {connection['component_id']}."
)

print("\nConfirming initial STABILIZE mode...")

initial_state = vehicle.wait_for_mode(
    "STABILIZE",
    timeout=5,
)

print(f"Initial mode: {initial_state['mode']}")

print("\nRequesting GUIDED mode...")

guided_result = vehicle.set_mode(
    "GUIDED",
    state_timeout=5,
)

print(f"Mode-change success: {guided_result['success']}")
print(f"Confirmed mode: {guided_result['state']['mode']}")

if not guided_result["success"]:
    print("ERROR: GUIDED mode request failed.")
    raise SystemExit(1)

print("\nHolding GUIDED mode for 2 seconds...")
time.sleep(2)

print("\nReturning to STABILIZE mode...")

stabilize_result = vehicle.set_mode(
    "STABILIZE",
    state_timeout=5,
)

print(f"Mode-change success: {stabilize_result['success']}")
print(f"Confirmed mode: {stabilize_result['state']['mode']}")

if not stabilize_result["success"]:
    print("ERROR: STABILIZE mode request failed.")
    raise SystemExit(1)

print("\nTesting invalid mode rejection...")

try:
    vehicle.set_mode(
        "AIRMOUSE_INVALID",
        state_timeout=2,
    )

except ValueError as error:
    print(f"Invalid mode rejected correctly: {error}")

else:
    print("ERROR: Invalid flight mode was unexpectedly accepted.")
    raise SystemExit(1)

print("\nPASS: MAVLink mode-control integration test completed.")
