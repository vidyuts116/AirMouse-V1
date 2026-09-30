"""Translate AirMouse core state into ROS 2 interface messages."""

from airmouse_interfaces.msg import (
    AttitudeState,
    BatteryState,
    FailSafeCause,
    FailSafeStatus,
    FlightState,
    GlobalPosition,
    HealthStatus,
    LocalPositionNED,
    SystemHealth,
)


class ROSMessageBuilder:
    """Convert transport-independent AirMouse state into ROS messages."""

    @staticmethod
    def _stamp(message, stamp):
        message.stamp = stamp
        return message

    def build_flight_state(self, state, stamp):
        flight = state.get("flight", {})

        if not flight:
            return None

        message = FlightState()
        self._stamp(message, stamp)

        message.system_id = int(flight.get("system_id", 0))
        message.component_id = int(flight.get("component_id", 0))
        message.vehicle_type = str(flight.get("vehicle_type", ""))
        message.autopilot_type = str(flight.get("autopilot_type", ""))
        message.flight_mode = str(flight.get("flight_mode", ""))
        message.armed = bool(flight.get("armed", False))
        message.system_status = int(flight.get("system_status", 0))
        message.system_state = str(flight.get("system_state", ""))

        return message

    def build_attitude_state(self, state, stamp):
        attitude = state.get("attitude", {})

        if not attitude:
            return None

        message = AttitudeState()
        self._stamp(message, stamp)

        message.roll_rad = float(attitude.get("roll_rad", 0.0))
        message.pitch_rad = float(attitude.get("pitch_rad", 0.0))
        message.yaw_rad = float(attitude.get("yaw_rad", 0.0))
        message.roll_rate_rad_s = float(
            attitude.get("roll_rate_rad_s", 0.0)
        )
        message.pitch_rate_rad_s = float(
            attitude.get("pitch_rate_rad_s", 0.0)
        )
        message.yaw_rate_rad_s = float(
            attitude.get("yaw_rate_rad_s", 0.0)
        )

        return message

    def build_global_position(self, state, stamp):
        position = state.get("global_position", {})

        if not position:
            return None

        message = GlobalPosition()
        self._stamp(message, stamp)

        message.latitude_deg = float(
            position.get("latitude_deg", 0.0)
        )
        message.longitude_deg = float(
            position.get("longitude_deg", 0.0)
        )
        message.altitude_m = float(
            position.get("altitude_m", 0.0)
        )
        message.relative_altitude_m = float(
            position.get("relative_altitude_m", 0.0)
        )
        message.velocity_north_mps = float(
            position.get("velocity_north_mps", 0.0)
        )
        message.velocity_east_mps = float(
            position.get("velocity_east_mps", 0.0)
        )
        message.velocity_down_mps = float(
            position.get("velocity_down_mps", 0.0)
        )

        return message

    def build_local_position(self, state, stamp):
        position = state.get("local_position", {})

        if not position:
            return None

        message = LocalPositionNED()
        self._stamp(message, stamp)

        message.north_m = float(position.get("north_m", 0.0))
        message.east_m = float(position.get("east_m", 0.0))
        message.down_m = float(position.get("down_m", 0.0))
        message.velocity_north_mps = float(
            position.get("velocity_north_mps", 0.0)
        )
        message.velocity_east_mps = float(
            position.get("velocity_east_mps", 0.0)
        )
        message.velocity_down_mps = float(
            position.get("velocity_down_mps", 0.0)
        )

        return message

    def build_system_health(self, state, stamp):
        health = state.get("system_health", {})

        if not health:
            return None

        message = SystemHealth()
        self._stamp(message, stamp)

        voltage = health.get("voltage_v")
        message.voltage_available = voltage is not None
        if voltage is not None:
            message.voltage_v = float(voltage)

        current = health.get("current_a")
        message.current_available = current is not None
        if current is not None:
            message.current_a = float(current)

        remaining = health.get("battery_remaining_percent")
        message.battery_remaining_available = remaining is not None
        if remaining is not None:
            message.battery_remaining_percent = int(remaining)

        message.drop_rate_comm = int(
            health.get("drop_rate_comm", 0)
        )
        message.errors_comm = int(
            health.get("errors_comm", 0)
        )
        message.sensors_present = int(
            health.get("sensors_present", 0)
        )
        message.sensors_enabled = int(
            health.get("sensors_enabled", 0)
        )
        message.sensors_health = int(
            health.get("sensors_health", 0)
        )

        return message

    def build_battery_state(self, state, stamp):
        battery = state.get("battery", {})
        system_health = state.get("system_health", {})

        if not battery and not system_health:
            return None

        message = BatteryState()
        self._stamp(message, stamp)

        message.battery_id = int(
            battery.get("battery_id", 0)
        )

        consumed = battery.get("current_consumed_mah")
        message.current_consumed_available = consumed is not None
        if consumed is not None:
            message.current_consumed_mah = int(consumed)

        energy = battery.get("energy_consumed_hj")
        message.energy_consumed_available = energy is not None
        if energy is not None:
            message.energy_consumed_hj = int(energy)

        remaining = battery.get("remaining_percent")
        if remaining is None:
            remaining = system_health.get(
                "battery_remaining_percent"
            )

        message.remaining_percent_available = remaining is not None
        if remaining is not None:
            message.remaining_percent = int(remaining)

        voltage = system_health.get("voltage_v")
        message.voltage_available = voltage is not None
        if voltage is not None:
            message.voltage_v = float(voltage)

        current = system_health.get("current_a")
        message.current_available = current is not None
        if current is not None:
            message.current_a = float(current)

        message.fault_bitmask = int(
            battery.get("fault_bitmask", 0)
        )

        return message

    def build_health_status(self, health, stamp):
        if not health:
            return None

        checks = health.get("checks", {})

        message = HealthStatus()
        self._stamp(message, stamp)

        message.overall_status = str(
            health.get("overall_status", "UNKNOWN")
        )
        message.heartbeat_status = str(
            checks.get("heartbeat", {}).get(
                "status",
                "UNKNOWN",
            )
        )
        message.system_health_status = str(
            checks.get("system_health", {}).get(
                "status",
                "UNKNOWN",
            )
        )
        message.battery_status = str(
            checks.get("battery", {}).get(
                "status",
                "UNKNOWN",
            )
        )
        message.sensor_status = str(
            checks.get("sensors", {}).get(
                "status",
                "UNKNOWN",
            )
        )

        return message

    def build_failsafe_status(self, decision, stamp):
        if not decision:
            return None

        message = FailSafeStatus()
        self._stamp(message, stamp)

        message.health_status = str(
            decision.get("health_status", "UNKNOWN")
        )
        message.decision = str(
            decision.get("decision", "HOLD")
        )

        for cause_data in decision.get("causes", []):
            cause = FailSafeCause()
            cause.check = str(cause_data.get("check", ""))
            cause.status = str(cause_data.get("status", ""))
            cause.reason = str(cause_data.get("reason", ""))
            message.causes.append(cause)

        return message
