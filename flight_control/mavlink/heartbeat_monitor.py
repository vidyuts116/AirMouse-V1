from pymavlink import mavutil

CONNECTION = "udpin:127.0.0.1:14550"

print("AirMouse V1 - MAVLink Heartbeat Monitor")
print(f"Listening on {CONNECTION} ...")

master = mavutil.mavlink_connection(CONNECTION)

heartbeat = master.wait_heartbeat(timeout=10)

if heartbeat is None:
    print("ERROR: No MAVLink heartbeat received.")
else:
    vehicle_type = mavutil.mavlink.enums["MAV_TYPE"][heartbeat.type].name
    autopilot_type = mavutil.mavlink.enums["MAV_AUTOPILOT"][heartbeat.autopilot].name
    system_state = mavutil.mavlink.enums["MAV_STATE"][heartbeat.system_status].name

    armed = bool(
        heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
    )

    mode_mapping = mavutil.mode_mapping_byname(heartbeat.type)

    flight_mode = "UNKNOWN"

    if mode_mapping:
        mode_by_number = {
            number: name for name, number in mode_mapping.items()
        }
        flight_mode = mode_by_number.get(heartbeat.custom_mode, "UNKNOWN")

    print("SUCCESS: MAVLink heartbeat received.")

    print("\nRaw MAVLink State")
    print("-----------------")
    print(f"System ID: {heartbeat.get_srcSystem()}")
    print(f"Component ID: {heartbeat.get_srcComponent()}")
    print(f"Vehicle type: {heartbeat.type}")
    print(f"Autopilot type: {heartbeat.autopilot}")
    print(f"Base mode: {heartbeat.base_mode}")
    print(f"Custom mode: {heartbeat.custom_mode}")
    print(f"System status: {heartbeat.system_status}")

    print("\nDecoded Vehicle State")
    print("---------------------")
    print(f"Vehicle: {vehicle_type}")
    print(f"Autopilot: {autopilot_type}")
    print(f"Flight mode: {flight_mode}")
    print(f"Armed: {'YES' if armed else 'NO'}")
    print(f"System state: {system_state}")
