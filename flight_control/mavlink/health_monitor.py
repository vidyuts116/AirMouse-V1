import threading
import time


class HealthFailSafeMonitor:
    """Evaluate AirMouse vehicle health from structured routed vehicle state."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    CONTINUE = "CONTINUE"
    CAUTION = "CAUTION"
    HOLD = "HOLD"
    FAILSAFE = "FAILSAFE"

    DEFAULT_THRESHOLDS = {
        "heartbeat_warning_age": 2.0,
        "heartbeat_critical_age": 5.0,
        "system_health_warning_age": 3.0,
        "system_health_critical_age": 6.0,
        "battery_warning_percent": 30,
        "battery_critical_percent": 20,
    }

    def __init__(self, vehicle_state, thresholds=None):
        if vehicle_state is None:
            raise ValueError(
                "A Vehicle State Manager is required."
            )

        self.vehicle_state = vehicle_state

        self.thresholds = self.DEFAULT_THRESHOLDS.copy()

        if thresholds is not None:
            self.thresholds.update(thresholds)

        self._lock = threading.Lock()

        self._health = {
            "overall_status": self.UNKNOWN,
            "checks": {},
            "evaluated_at": None,
        }

    def evaluate_heartbeat(self, state=None, now=None):
        """Evaluate flight-controller heartbeat freshness."""

        if state is None:
            state = self.vehicle_state.get_state()

        if now is None:
            now = time.monotonic()

        flight = state.get("flight", {})

        updated_at = flight.get("updated_at")

        if updated_at is None:
            return {
                "status": self.UNKNOWN,
                "age": None,
                "reason": "No heartbeat telemetry available.",
            }

        age = max(0.0, now - updated_at)

        warning_age = self.thresholds[
            "heartbeat_warning_age"
        ]

        critical_age = self.thresholds[
            "heartbeat_critical_age"
        ]

        if age > critical_age:
            status = self.CRITICAL
            reason = "Heartbeat telemetry is critically stale."

        elif age > warning_age:
            status = self.WARNING
            reason = "Heartbeat telemetry is stale."

        else:
            status = self.HEALTHY
            reason = "Heartbeat telemetry is fresh."

        return {
            "status": status,
            "age": age,
            "reason": reason,
        }

    def evaluate_system_health_freshness(
        self,
        state=None,
        now=None,
    ):
        """Evaluate SYS_STATUS telemetry freshness."""

        if state is None:
            state = self.vehicle_state.get_state()

        if now is None:
            now = time.monotonic()

        system_health = state.get("system_health", {})
        updated_at = system_health.get("updated_at")

        if updated_at is None:
            return {
                "status": self.UNKNOWN,
                "age": None,
                "reason": "No system-health telemetry available.",
            }

        age = max(0.0, now - updated_at)

        warning_age = self.thresholds[
            "system_health_warning_age"
        ]

        critical_age = self.thresholds[
            "system_health_critical_age"
        ]

        if age > critical_age:
            status = self.CRITICAL
            reason = (
                "System-health telemetry is critically stale."
            )

        elif age > warning_age:
            status = self.WARNING
            reason = "System-health telemetry is stale."

        else:
            status = self.HEALTHY
            reason = "System-health telemetry is fresh."

        return {
            "status": status,
            "age": age,
            "reason": reason,
        }

    def evaluate_battery_level(self, state=None):
        """Evaluate remaining battery percentage."""

        if state is None:
            state = self.vehicle_state.get_state()

        battery = state.get("battery", {})
        system_health = state.get("system_health", {})

        remaining_percent = battery.get(
            "remaining_percent"
        )

        source = "BATTERY_STATUS"

        if remaining_percent is None:
            remaining_percent = system_health.get(
                "battery_remaining_percent"
            )
            source = "SYS_STATUS"

        if remaining_percent is None:
            return {
                "status": self.UNKNOWN,
                "remaining_percent": None,
                "source": None,
                "reason": "Battery percentage is unavailable.",
            }

        warning_percent = self.thresholds[
            "battery_warning_percent"
        ]

        critical_percent = self.thresholds[
            "battery_critical_percent"
        ]

        if remaining_percent <= critical_percent:
            status = self.CRITICAL
            reason = "Battery level is critically low."

        elif remaining_percent <= warning_percent:
            status = self.WARNING
            reason = "Battery level is low."

        else:
            status = self.HEALTHY
            reason = "Battery level is healthy."

        return {
            "status": status,
            "remaining_percent": remaining_percent,
            "source": source,
            "reason": reason,
        }

    def evaluate_sensor_health(self, state=None):
        """Evaluate enabled and present MAVLink sensor health."""

        if state is None:
            state = self.vehicle_state.get_state()

        system_health = state.get("system_health", {})

        sensors_present = system_health.get(
            "sensors_present"
        )
        sensors_enabled = system_health.get(
            "sensors_enabled"
        )
        sensors_health = system_health.get(
            "sensors_health"
        )

        if (
            sensors_present is None
            or sensors_enabled is None
            or sensors_health is None
        ):
            return {
                "status": self.UNKNOWN,
                "required_mask": None,
                "unhealthy_mask": None,
                "reason": (
                    "Sensor-health telemetry is unavailable."
                ),
            }

        required_mask = (
            sensors_present
            & sensors_enabled
        )

        unhealthy_mask = (
            required_mask
            & ~sensors_health
        )

        if unhealthy_mask:
            status = self.CRITICAL
            reason = (
                "One or more enabled and present "
                "sensors report unhealthy."
            )

        else:
            status = self.HEALTHY
            reason = (
                "All enabled and present sensors "
                "report healthy."
            )

        return {
            "status": status,
            "required_mask": required_mask,
            "unhealthy_mask": unhealthy_mask,
            "reason": reason,
        }

    def evaluate(self, state=None, now=None):
        """Evaluate all health checks and store the combined assessment."""

        if state is None:
            state = self.vehicle_state.get_state()

        if now is None:
            now = time.monotonic()

        checks = {
            "heartbeat": self.evaluate_heartbeat(
                state=state,
                now=now,
            ),
            "system_health": self.evaluate_system_health_freshness(
                state=state,
                now=now,
            ),
            "battery": self.evaluate_battery_level(
                state=state,
            ),
            "sensors": self.evaluate_sensor_health(
                state=state,
            ),
        }

        statuses = {
            check["status"]
            for check in checks.values()
        }

        if self.CRITICAL in statuses:
            overall_status = self.CRITICAL

        elif self.WARNING in statuses:
            overall_status = self.WARNING

        elif self.UNKNOWN in statuses:
            overall_status = self.UNKNOWN

        else:
            overall_status = self.HEALTHY

        assessment = {
            "overall_status": overall_status,
            "checks": checks,
            "evaluated_at": now,
        }

        with self._lock:
            self._health = assessment

        return self.get_health()

    def determine_failsafe_decision(self, health=None):
        """Map a health assessment to a fail-safe policy decision."""

        if health is None:
            health = self.get_health()

        overall_status = health.get("overall_status")

        decision_mapping = {
            self.HEALTHY: self.CONTINUE,
            self.WARNING: self.CAUTION,
            self.UNKNOWN: self.HOLD,
            self.CRITICAL: self.FAILSAFE,
        }

        if overall_status not in decision_mapping:
            raise ValueError(
                f"Unsupported health status: {overall_status}"
            )

        decision = decision_mapping[overall_status]

        target_status = {
            self.HEALTHY: None,
            self.WARNING: self.WARNING,
            self.UNKNOWN: self.UNKNOWN,
            self.CRITICAL: self.CRITICAL,
        }[overall_status]

        causes = []

        if target_status is not None:
            for name, check in health.get("checks", {}).items():
                if check.get("status") == target_status:
                    causes.append(
                        {
                            "check": name,
                            "status": check.get("status"),
                            "reason": check.get("reason"),
                        }
                    )

        return {
            "health_status": overall_status,
            "decision": decision,
            "causes": causes,
        }

    def get_health(self):
        """Return a snapshot of the latest health assessment."""

        with self._lock:
            return {
                "overall_status": self._health["overall_status"],
                "checks": {
                    name: values.copy()
                    for name, values in self._health["checks"].items()
                },
                "evaluated_at": self._health["evaluated_at"],
            }
