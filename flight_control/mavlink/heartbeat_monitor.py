from pymavlink import mavutil

CONNECTION = "udpin:127.0.0.1:14550"

print("AirMouse V1 - MAVLink Heartbeat Monitor")
print(f"Listening on {CONNECTION} ...")

master = mavutil.mavlink_connection(CONNECTION)

heartbeat = master.wait_heartbeat(timeout=10)

if heartbeat is None:
    print("ERROR: No MAVLink heartbeat received.")
else:
    print("SUCCESS: MAVLink heartbeat received.")
    print(f"System ID: {master.target_system}")
    print(f"Component ID: {master.target_component}")
    print(f"Vehicle type: {heartbeat.type}")
    print(f"Autopilot type: {heartbeat.autopilot}")
    print(f"Base mode: {heartbeat.base_mode}")
    print(f"Custom mode: {heartbeat.custom_mode}")
    print(f"System status: {heartbeat.system_status}")
