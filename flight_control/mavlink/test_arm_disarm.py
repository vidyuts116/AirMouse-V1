import time

from command_interface import MAVLinkCommandInterface


CONNECTION = "udpin:127.0.0.1:14550"


print("AirMouse V1 - MAVLink ARM/DISARM Integration Test")
print(f"Connecting to {CONNECTION} ...")

vehicle = MAVLinkCommandInterface(CONNECTION)

connection = vehicle.connect()

print(
    f"Connected to MAVLink system {connection['system_id']}, "
    f"component {connection['component_id']}."
)

print("\nConfirming initial DISARMED state...")

initial_state = vehicle.wait_for_armed_state(
    armed=False,
    timeout=5,
)

print(f"Initial armed state: {initial_state['armed']}")

print("\nSending ARM request...")

arm_result = vehicle.arm(
    ack_timeout=5,
    state_timeout=5,
)

print(f"ARM success: {arm_result['success']}")
print(f"ARM ACK: {arm_result['ack']['result_name']}")

if not arm_result["success"]:
    print("ERROR: ARM request was rejected.")
    raise SystemExit(1)

print(f"Confirmed armed state: {arm_result['state']['armed']}")

print("\nHolding ARMED state for 2 seconds...")
time.sleep(2)

print("\nSending DISARM request...")

disarm_result = vehicle.disarm(
    ack_timeout=5,
    state_timeout=5,
)

print(f"DISARM success: {disarm_result['success']}")
print(f"DISARM ACK: {disarm_result['ack']['result_name']}")

if not disarm_result["success"]:
    print("ERROR: DISARM request was rejected.")
    raise SystemExit(1)

print(
    f"Confirmed armed state after DISARM: "
    f"{disarm_result['state']['armed']}"
)

print("\nPASS: ARM/DISARM integration cycle completed.")
