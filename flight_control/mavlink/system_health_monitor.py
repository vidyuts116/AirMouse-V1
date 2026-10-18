import time

from pymavlink import mavutil

from .monitor_config import parse_monitor_connection


CONNECTION = parse_monitor_connection(
    "AirMouse V1 MAVLink System Health Monitor"
)

# Human-readable terminal output rate.
DISPLAY_INTERVAL = 1.0


print("AirMouse V1 - MAVLink System Health Monitor")
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

print("Streaming system-health telemetry. Press Ctrl+C to stop.\n")


latest_sys_status = None
latest_battery_status = None
last_display = 0.0


try:
    while True:
        message = master.recv_match(
            type=["SYS_STATUS", "BATTERY_STATUS"],
            blocking=True,
            timeout=1,
        )

        if message is None:
            continue

        message_type = message.get_type()

        if message_type == "SYS_STATUS":
            latest_sys_status = message

        elif message_type == "BATTERY_STATUS":
            latest_battery_status = message

        now = time.monotonic()

        if now - last_display < DISPLAY_INTERVAL:
            continue

        if latest_sys_status is None or latest_battery_status is None:
            continue

        last_display = now

        voltage_v = latest_sys_status.voltage_battery / 1000.0

        # MAVLink current_battery is expressed in 10 mA units.
        current_a = latest_sys_status.current_battery / 100.0

        battery_remaining = latest_sys_status.battery_remaining

        print(
            f"Power  | "
            f"Voltage: {voltage_v:.2f} V | "
            f"Current: {current_a:.2f} A | "
            f"Remaining: {battery_remaining}%"
        )

        print(
            f"Comms  | "
            f"Drop rate: {latest_sys_status.drop_rate_comm} | "
            f"Errors: {latest_sys_status.errors_comm}"
        )

        print(
            f"System | "
            f"Present mask: {latest_sys_status.onboard_control_sensors_present} | "
            f"Enabled mask: {latest_sys_status.onboard_control_sensors_enabled} | "
            f"Health mask: {latest_sys_status.onboard_control_sensors_health}"
        )

        print(
            f"Battery| "
            f"ID: {latest_battery_status.id} | "
            f"Consumed: {latest_battery_status.current_consumed} mAh | "
            f"Energy: {latest_battery_status.energy_consumed} hJ | "
            f"Fault mask: {latest_battery_status.fault_bitmask}"
        )

        print()

except KeyboardInterrupt:
    print("\nSystem health monitoring stopped.")
