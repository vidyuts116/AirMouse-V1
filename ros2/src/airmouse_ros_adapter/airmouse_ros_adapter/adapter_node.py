"""ROS 2 publishing adapter for the AirMouse flight-control core."""

from threading import Lock

import rclpy
from rclpy.node import Node

from airmouse_interfaces.msg import (
    AdapterStatus,
    AttitudeState,
    BatteryState,
    FailSafeStatus,
    FlightState,
    GlobalPosition,
    HealthStatus,
    LocalPositionNED,
    SystemHealth,
)

from airmouse_interfaces.srv import (
    Arm,
    Disarm,
    SetMode,
)

from .message_builder import ROSMessageBuilder


class AirMouseROSAdapter(Node):
    """Expose AirMouse flight-control state through ROS 2."""

    DEFAULT_NAMESPACE = "/airmouse"
    DEFAULT_PUBLISH_RATE_HZ = 10.0

    def __init__(
        self,
        vehicle_state,
        health_monitor,
        command_manager=None,
        namespace=DEFAULT_NAMESPACE,
        publish_rate_hz=DEFAULT_PUBLISH_RATE_HZ,
    ):
        super().__init__("airmouse_ros_adapter")

        if vehicle_state is None:
            raise ValueError("Vehicle State Manager is required.")

        if health_monitor is None:
            raise ValueError("Health Fail-Safe Monitor is required.")

        if publish_rate_hz <= 0:
            raise ValueError("Publish rate must be greater than zero.")

        self.vehicle_state = vehicle_state
        self.health_monitor = health_monitor
        self.command_manager = command_manager

        self.namespace_prefix = namespace.rstrip("/")
        if not self.namespace_prefix:
            self.namespace_prefix = self.DEFAULT_NAMESPACE

        self.publish_rate_hz = float(publish_rate_hz)

        self.builder = ROSMessageBuilder()
        self._publish_lock = Lock()
        self._last_publish_time = None

        self.flight_publisher = self.create_publisher(
            FlightState,
            self._topic("state/flight"),
            10,
        )

        self.attitude_publisher = self.create_publisher(
            AttitudeState,
            self._topic("state/attitude"),
            10,
        )

        self.global_position_publisher = self.create_publisher(
            GlobalPosition,
            self._topic("state/global_position"),
            10,
        )

        self.local_position_publisher = self.create_publisher(
            LocalPositionNED,
            self._topic("state/local_position_ned"),
            10,
        )

        self.battery_publisher = self.create_publisher(
            BatteryState,
            self._topic("state/battery"),
            10,
        )

        self.system_health_publisher = self.create_publisher(
            SystemHealth,
            self._topic("state/system_health"),
            10,
        )

        self.health_publisher = self.create_publisher(
            HealthStatus,
            self._topic("health/status"),
            10,
        )

        self.failsafe_publisher = self.create_publisher(
            FailSafeStatus,
            self._topic("health/failsafe"),
            10,
        )

        self.adapter_status_publisher = self.create_publisher(
            AdapterStatus,
            self._topic("interface/status"),
            10,
        )

        self.timer = self.create_timer(
            1.0 / self.publish_rate_hz,
            self.publish_once,
        )

        self.arm_service = None
        self.disarm_service = None
        self.set_mode_service = None

        if self.command_manager is not None:
            self.arm_service = self.create_service(
                Arm,
                self._topic("command/arm"),
                self._handle_arm,
            )

            self.disarm_service = self.create_service(
                Disarm,
                self._topic("command/disarm"),
                self._handle_disarm,
            )

            self.set_mode_service = self.create_service(
                SetMode,
                self._topic("command/set_mode"),
                self._handle_set_mode,
            )

    def _topic(self, suffix):
        """Build a topic name beneath the configured AirMouse namespace."""
        return f"{self.namespace_prefix}/{suffix}"

    def _now_message(self):
        """Return the current ROS clock time as a ROS Time message."""
        return self.get_clock().now().to_msg()

    def publish_once(self):
        """Publish one coherent snapshot of available AirMouse state."""

        with self._publish_lock:
            stamp = self._now_message()

            state = self.vehicle_state.get_state()

            flight_message = self.builder.build_flight_state(
                state,
                stamp,
            )
            if flight_message is not None:
                self.flight_publisher.publish(flight_message)

            attitude_message = self.builder.build_attitude_state(
                state,
                stamp,
            )
            if attitude_message is not None:
                self.attitude_publisher.publish(attitude_message)

            global_position_message = (
                self.builder.build_global_position(
                    state,
                    stamp,
                )
            )
            if global_position_message is not None:
                self.global_position_publisher.publish(
                    global_position_message
                )

            local_position_message = (
                self.builder.build_local_position(
                    state,
                    stamp,
                )
            )
            if local_position_message is not None:
                self.local_position_publisher.publish(
                    local_position_message
                )

            system_health_message = (
                self.builder.build_system_health(
                    state,
                    stamp,
                )
            )
            if system_health_message is not None:
                self.system_health_publisher.publish(
                    system_health_message
                )

            battery_message = self.builder.build_battery_state(
                state,
                stamp,
            )
            if battery_message is not None:
                self.battery_publisher.publish(
                    battery_message
                )

            health = self.health_monitor.evaluate(state=state)

            health_message = self.builder.build_health_status(
                health,
                stamp,
            )
            if health_message is not None:
                self.health_publisher.publish(health_message)

            decision = (
                self.health_monitor.determine_failsafe_decision(
                    health
                )
            )

            failsafe_message = self.builder.build_failsafe_status(
                decision,
                stamp,
            )
            if failsafe_message is not None:
                self.failsafe_publisher.publish(
                    failsafe_message
                )

            self._last_publish_time = stamp

            self.adapter_status_publisher.publish(
                self._build_adapter_status(
                    state,
                    health,
                    stamp,
                )
            )

    def _require_command_manager(self):
        """Ensure the command boundary is available and running."""

        if self.command_manager is None:
            raise RuntimeError(
                "AirMouse command manager is unavailable."
            )

        if not getattr(
            self.command_manager,
            "is_started",
            False,
        ):
            raise RuntimeError(
                "AirMouse command manager is not started."
            )

    def _handle_arm(self, request, response):
        """Delegate a ROS arm request to MAVLinkCommandManager."""

        del request

        try:
            self._require_command_manager()
            result = self.command_manager.arm()

            response.success = bool(result.get("success", False))

            state = result.get("state") or {}

            response.resulting_armed_state = bool(
                state.get("armed", False)
            )
            response.resulting_mode = str(
                state.get("flight_mode") or ""
            )

            if response.success:
                response.message = "Arm command completed."
            else:
                ack = result.get("ack") or {}
                result_name = ack.get(
                    "result_name",
                    "UNKNOWN",
                )
                response.message = (
                    f"Arm command rejected: {result_name}."
                )

        except Exception as exc:
            response.success = False
            response.resulting_armed_state = False
            response.resulting_mode = ""
            response.message = (
                f"Arm command failed: "
                f"{type(exc).__name__}: {exc}"
            )

        return response

    def _handle_disarm(self, request, response):
        """Delegate a ROS disarm request to MAVLinkCommandManager."""

        del request

        try:
            self._require_command_manager()
            result = self.command_manager.disarm()

            response.success = bool(result.get("success", False))

            state = result.get("state") or {}

            response.resulting_armed_state = bool(
                state.get("armed", False)
            )
            response.resulting_mode = str(
                state.get("flight_mode") or ""
            )

            if response.success:
                response.message = "Disarm command completed."
            else:
                ack = result.get("ack") or {}
                result_name = ack.get(
                    "result_name",
                    "UNKNOWN",
                )
                response.message = (
                    f"Disarm command rejected: {result_name}."
                )

        except Exception as exc:
            response.success = False
            response.resulting_armed_state = False
            response.resulting_mode = ""
            response.message = (
                f"Disarm command failed: "
                f"{type(exc).__name__}: {exc}"
            )

        return response

    def _handle_set_mode(self, request, response):
        """Delegate a ROS mode request to MAVLinkCommandManager."""

        try:
            self._require_command_manager()

            requested_mode = request.mode.strip()

            if not requested_mode:
                raise ValueError(
                    "Requested flight mode must not be empty."
                )

            result = self.command_manager.set_mode(
                requested_mode
            )

            response.success = bool(
                result.get("success", False)
            )

            state = result.get("state") or {}

            response.resulting_mode = str(
                state.get("mode")
                or result.get("mode")
                or ""
            )

            response.armed = bool(
                state.get("armed", False)
            )

            if response.success:
                response.message = (
                    "Flight-mode change completed."
                )
            else:
                response.message = (
                    "Flight-mode change was not completed."
                )

        except Exception as exc:
            response.success = False
            response.resulting_mode = ""
            response.armed = False
            response.message = (
                f"Set-mode command failed: "
                f"{type(exc).__name__}: {exc}"
            )

        return response

    def _build_adapter_status(self, state, health, stamp):
        """Build adapter-readiness status without inventing telemetry."""

        message = AdapterStatus()

        message.stamp = stamp
        message.adapter_running = True

        message.vehicle_state_available = any(
            bool(section)
            for section in state.values()
        )

        message.health_available = (
            health.get("evaluated_at") is not None
        )

        message.command_interface_available = (
            self.command_manager is not None
            and getattr(
                self.command_manager,
                "is_started",
                False,
            )
        )

        if self._last_publish_time is not None:
            message.last_publish_time = self._last_publish_time
        else:
            message.last_publish_time = stamp

        return message


def main(args=None):
    """
    Standalone execution is intentionally unavailable.

    The adapter requires live AirMouse core objects. Their lifecycle and
    MAVLink transport ownership belong to the flight-control composition
    layer, not this ROS translation module.
    """

    rclpy.init(args=args)

    try:
        raise RuntimeError(
            "AirMouseROSAdapter requires VehicleStateManager and "
            "HealthFailSafeMonitor instances from the AirMouse "
            "flight-control composition layer."
        )
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
