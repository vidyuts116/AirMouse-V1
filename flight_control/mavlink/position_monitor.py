import time

from pymavlink import mavutil


# SITL connection.
# TODO: Make this configurable before physical-drone integration.
CONNECTION = "udpin:127.0.0.1:14550"

# Human-readable terminal output rate.
DISPLAY_INTERVAL = 0.5


print("AirMouse V1 - MAVLink Position Monitor")
print(f"Listening on {CONNECTION} ...")

master = mavutil.mavlink_connection(CONNECTION)

heartbeat = master.wait_heartbeat(timeout=10)

if heartbeat is None:
    print("ERROR: No MAVLink heartbeat received.")
    raise SystemExit(1)

print(
    "Connected to MAVLink "
    f"system {heartbeat.get_srcSystem()}, "
    f"component {heartbeat.get_srcComponent()}."
)

print("Streaming position telemetry. Press Ctrl+C to stop.\n")


latest_global = None
latest_local = None
last_display = 0.0


try:
    while True:
        message = master.recv_match(
            type=["GLOBAL_POSITION_INT", "LOCAL_POSITION_NED"],
            blocking=True,
            timeout=1,
        )

        if message is None:
            continue

        message_type = message.get_type()

        if message_type == "GLOBAL_POSITION_INT":
            latest_global = message

        elif message_type == "LOCAL_POSITION_NED":
            latest_local = message

        now = time.monotonic()

        if now - last_display < DISPLAY_INTERVAL:
            continue

        if latest_global is None or latest_local is None:
            continue

        last_display = now

        latitude = latest_global.lat / 1e7
        longitude = latest_global.lon / 1e7

        altitude_m = latest_global.alt / 1000.0
        relative_altitude_m = latest_global.relative_alt / 1000.0

        global_vx = latest_global.vx / 100.0
        global_vy = latest_global.vy / 100.0
        global_vz = latest_global.vz / 100.0

        print(
            f"Global | "
            f"Lat: {latitude:.7f} | "
            f"Lon: {longitude:.7f} | "
            f"Alt: {altitude_m:.2f} m | "
            f"Rel Alt: {relative_altitude_m:.2f} m | "
            f"V(NED): "
            f"{global_vx:.2f}, "
            f"{global_vy:.2f}, "
            f"{global_vz:.2f} m/s"
        )

        print(
            f"Local  | "
            f"X: {latest_local.x:7.2f} m | "
            f"Y: {latest_local.y:7.2f} m | "
            f"Z: {latest_local.z:7.2f} m | "
            f"V(NED): "
            f"{latest_local.vx:6.2f}, "
            f"{latest_local.vy:6.2f}, "
            f"{latest_local.vz:6.2f} m/s"
        )

        print()

except KeyboardInterrupt:
    print("\nPosition monitoring stopped.")
