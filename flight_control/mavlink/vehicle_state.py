import threading
import time

from pymavlink import mavutil


class VehicleStateManager:
    """Maintain the latest structured vehicle state from routed MAVLink data."""

    MESSAGE_TYPES = (
        "HEARTBEAT",
        "ATTITUDE",
        "GLOBAL_POSITION_INT",
        "LOCAL_POSITION_NED",
        "SYS_STATUS",
        "BATTERY_STATUS",
    )

    def __init__(self, router):
        if router is None:
            raise ValueError("A MAVLink message router is required.")

        self.router = router
        self._lock = threading.Lock()
        self._started = False

        self._state = {
            "flight": {},
            "attitude": {},
            "global_position": {},
            "local_position": {},
            "system_health": {},
            "battery": {},
        }

    @property
    def is_started(self):
        """Return whether the manager is subscribed to the router."""
        return self._started

    def start(self):
        """Subscribe the state manager to required MAVLink message types."""

        if self._started:
            raise RuntimeError("Vehicle State Manager is already started.")

        for message_type in self.MESSAGE_TYPES:
            self.router.subscribe(
                message_type,
                self._handle_message,
            )

        self._started = True

    def stop(self):
        """Remove all Vehicle State Manager router subscriptions."""

        if not self._started:
            return

        for message_type in self.MESSAGE_TYPES:
            self.router.unsubscribe(
                message_type,
                self._handle_message,
            )

        self._started = False

    def get_state(self):
        """Return a snapshot of the current vehicle state."""

        with self._lock:
            return {
                section: values.copy()
                for section, values in self._state.items()
            }

    def _handle_message(self, message):
        """Route an incoming MAVLink message to its state decoder."""

        message_type = message.get_type()
        timestamp = time.monotonic()

        handlers = {
            "HEARTBEAT": self._update_heartbeat,
            "ATTITUDE": self._update_attitude,
            "GLOBAL_POSITION_INT": self._update_global_position,
            "LOCAL_POSITION_NED": self._update_local_position,
            "SYS_STATUS": self._update_system_health,
            "BATTERY_STATUS": self._update_battery,
        }

        handler = handlers.get(message_type)

        if handler is not None:
            handler(message, timestamp)

    def _update_heartbeat(self, message, timestamp):
        """Update flight state from a MAVLink HEARTBEAT."""

        armed = bool(
            message.base_mode
            & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        )

        mode_mapping = mavutil.mode_mapping_byname(message.type)
        flight_mode = "UNKNOWN"

        if mode_mapping:
            mode_by_number = {
                number: name
                for name, number in mode_mapping.items()
            }

            flight_mode = mode_by_number.get(
                message.custom_mode,
                "UNKNOWN",
            )

        vehicle_type = mavutil.mavlink.enums[
            "MAV_TYPE"
        ][message.type].name

        autopilot_type = mavutil.mavlink.enums[
            "MAV_AUTOPILOT"
        ][message.autopilot].name

        system_state = mavutil.mavlink.enums[
            "MAV_STATE"
        ][message.system_status].name

        with self._lock:
            self._state["flight"] = {
                "system_id": message.get_srcSystem(),
                "component_id": message.get_srcComponent(),
                "vehicle_type": vehicle_type,
                "autopilot_type": autopilot_type,
                "flight_mode": flight_mode,
                "armed": armed,
                "system_status": message.system_status,
                "system_state": system_state,
                "updated_at": timestamp,
            }

    def _update_attitude(self, message, timestamp):
        """Update attitude state from a MAVLink ATTITUDE message."""

        with self._lock:
            self._state["attitude"] = {
                "roll_rad": message.roll,
                "pitch_rad": message.pitch,
                "yaw_rad": message.yaw,
                "roll_rate_rad_s": message.rollspeed,
                "pitch_rate_rad_s": message.pitchspeed,
                "yaw_rate_rad_s": message.yawspeed,
                "updated_at": timestamp,
            }

    def _update_global_position(self, message, timestamp):
        """Update global position and velocity state."""

        with self._lock:
            self._state["global_position"] = {
                "latitude_deg": message.lat / 1e7,
                "longitude_deg": message.lon / 1e7,
                "altitude_m": message.alt / 1000.0,
                "relative_altitude_m": (
                    message.relative_alt / 1000.0
                ),
                "velocity_north_mps": message.vx / 100.0,
                "velocity_east_mps": message.vy / 100.0,
                "velocity_down_mps": message.vz / 100.0,
                "updated_at": timestamp,
            }

    def _update_local_position(self, message, timestamp):
        """Update local NED position and velocity state."""

        with self._lock:
            self._state["local_position"] = {
                "north_m": message.x,
                "east_m": message.y,
                "down_m": message.z,
                "velocity_north_mps": message.vx,
                "velocity_east_mps": message.vy,
                "velocity_down_mps": message.vz,
                "updated_at": timestamp,
            }

    def _update_system_health(self, message, timestamp):
        """Update system-health and primary power state."""

        voltage_battery = message.voltage_battery
        current_battery = message.current_battery

        voltage_v = None
        if voltage_battery != 65535:
            voltage_v = voltage_battery / 1000.0

        current_a = None
        if current_battery != -1:
            current_a = current_battery / 100.0

        battery_remaining = message.battery_remaining
        if battery_remaining == -1:
            battery_remaining = None

        with self._lock:
            self._state["system_health"] = {
                "voltage_v": voltage_v,
                "current_a": current_a,
                "battery_remaining_percent": battery_remaining,
                "drop_rate_comm": message.drop_rate_comm,
                "errors_comm": message.errors_comm,
                "sensors_present": (
                    message.onboard_control_sensors_present
                ),
                "sensors_enabled": (
                    message.onboard_control_sensors_enabled
                ),
                "sensors_health": (
                    message.onboard_control_sensors_health
                ),
                "updated_at": timestamp,
            }

    def _update_battery(self, message, timestamp):
        """Update detailed battery state."""

        current_consumed = message.current_consumed
        if current_consumed == -1:
            current_consumed = None

        energy_consumed = message.energy_consumed
        if energy_consumed == -1:
            energy_consumed = None

        battery_remaining = message.battery_remaining
        if battery_remaining == -1:
            battery_remaining = None

        with self._lock:
            self._state["battery"] = {
                "battery_id": message.id,
                "current_consumed_mah": current_consumed,
                "energy_consumed_hj": energy_consumed,
                "remaining_percent": battery_remaining,
                "fault_bitmask": message.fault_bitmask,
                "updated_at": timestamp,
            }
