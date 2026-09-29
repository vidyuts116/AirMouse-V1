from pymavlink import mavutil

from command_interface import MAVLinkCommandInterface


CONNECTION = "udpin:127.0.0.1:14550"


print("AirMouse V1 - MAVLink Command Interface Test")
print(f"Connecting to {CONNECTION} ...")

vehicle = MAVLinkCommandInterface(CONNECTION)

connection_info = vehicle.connect()

print(
    "Connected to MAVLink "
    f"system {connection_info['system_id']}, "
    f"component {connection_info['component_id']}."
)

print("\nRequesting AUTOPILOT_VERSION message...")

result = vehicle.send_command_long(
    mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
    param1=mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION,
)

print("\nCOMMAND_ACK received")
print("--------------------")
print(f"Command ID: {result['command']}")
print(f"Result code: {result['result']}")
print(f"Result: {result['result_name']}")
