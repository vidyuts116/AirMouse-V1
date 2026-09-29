import math
import time

from pymavlink import mavutil


CONNECTION = "udpin:127.0.0.1:14550"
DISPLAY_INTERVAL = 0.5

print("AirMouse V1 - MAVLink Attitude Monitor")
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

print("Streaming ATTITUDE data. Press Ctrl+C to stop.\n")

last_display = 0.0

try:
    while True:
        attitude = master.recv_match(
            type="ATTITUDE",
            blocking=True,
            timeout=1,
        )

        if attitude is None:
            continue

        now = time.monotonic()

        if now - last_display < DISPLAY_INTERVAL:
            continue

        last_display = now

        roll_deg = math.degrees(attitude.roll)
        pitch_deg = math.degrees(attitude.pitch)
        yaw_deg = math.degrees(attitude.yaw)

        rollspeed_deg = math.degrees(attitude.rollspeed)
        pitchspeed_deg = math.degrees(attitude.pitchspeed)
        yawspeed_deg = math.degrees(attitude.yawspeed)

        print(
            f"Roll: {roll_deg:7.2f} deg | "
            f"Pitch: {pitch_deg:7.2f} deg | "
            f"Yaw: {yaw_deg:7.2f} deg | "
            f"Rates: "
            f"{rollspeed_deg:6.2f}, "
            f"{pitchspeed_deg:6.2f}, "
            f"{yawspeed_deg:6.2f} deg/s"
        )

except KeyboardInterrupt:
    print("\nAttitude monitoring stopped.")
