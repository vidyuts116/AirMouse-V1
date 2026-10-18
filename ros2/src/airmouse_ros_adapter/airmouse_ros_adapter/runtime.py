"""Runtime composition for the AirMouse ROS 2 adapter.

This module owns lifecycle composition only. The MAVLink transport
endpoint is supplied externally so the same architecture can be used
with SITL now and physical flight-controller transports later.
"""

from flight_control.mavlink.connection_manager import (
    MAVLinkConnectionManager,
)
from flight_control.mavlink.message_router import MAVLinkMessageRouter
from flight_control.mavlink.vehicle_state import VehicleStateManager
from flight_control.mavlink.health_monitor import HealthFailSafeMonitor
from flight_control.mavlink.command_manager import MAVLinkCommandManager
from flight_control.mavlink.data_logger import MAVLinkDataLogger

from .adapter_node import AirMouseROSAdapter


class AirMouseRuntime:
    """Compose and manage the AirMouse flight-control/ROS pipeline."""

    def __init__(
        self,
        connection_string,
        *,
        connection_options=None,
        namespace="/airmouse",
        publish_rate_hz=10.0,
        log_path=None,
    ):
        if not connection_string:
            raise ValueError(
                "A MAVLink connection string is required."
            )

        self.connection_string = connection_string
        self.connection_options = dict(connection_options or {})
        self.namespace = namespace
        self.publish_rate_hz = float(publish_rate_hz)
        self.log_path = log_path

        self.connection_manager = None
        self.router = None
        self.vehicle_state = None
        self.health_monitor = None
        self.command_manager = None
        self.data_logger = None
        self.adapter = None

        self._started = False

    @property
    def is_started(self):
        return self._started

    def start(self, heartbeat_timeout=10):
        """Connect and start the complete AirMouse runtime."""

        if self._started:
            raise RuntimeError(
                "AirMouse runtime is already started."
            )

        try:
            self.connection_manager = MAVLinkConnectionManager(
                self.connection_string,
                **self.connection_options,
            )

            connection_info = self.connection_manager.connect(
                heartbeat_timeout=heartbeat_timeout,
            )

            connection = (
                self.connection_manager.get_connection()
            )

            self.router = MAVLinkMessageRouter(connection)

            self.vehicle_state = VehicleStateManager(
                self.router
            )

            self.health_monitor = HealthFailSafeMonitor(
                self.vehicle_state
            )

            self.command_manager = MAVLinkCommandManager(
                connection,
                self.router,
                self.vehicle_state,
            )

            if self.log_path:
                self.data_logger = MAVLinkDataLogger(
                    self.router,
                    self.log_path,
                )

            self.adapter = AirMouseROSAdapter(
                vehicle_state=self.vehicle_state,
                health_monitor=self.health_monitor,
                command_manager=self.command_manager,
                namespace=self.namespace,
                publish_rate_hz=self.publish_rate_hz,
            )

            # Subscribers must be registered before the sole
            # MAVLink receive loop starts.
            self.vehicle_state.start()
            self.command_manager.start()

            # The logger is a router subscriber, never a transport owner.
            # Register it before the sole MAVLink receive loop starts.
            if self.data_logger is not None:
                self.data_logger.start()

            self.router.start()

            self._started = True

            return connection_info

        except Exception:
            self.stop()
            raise

    def stop(self):
        """Stop the runtime safely in reverse ownership order."""

        # Stop ROS activity first so no new ROS-triggered command can
        # enter while the underlying flight-control stack is stopping.
        if self.adapter is not None:
            try:
                self.adapter.destroy_node()
            except Exception:
                pass
            finally:
                self.adapter = None

        if self.command_manager is not None:
            try:
                if self.command_manager.is_started:
                    self.command_manager.stop()
            except Exception:
                pass

        # Stop the logger while the router still exists. This removes its
        # subscriptions and drains queued records before transport teardown.
        if self.data_logger is not None:
            try:
                if self.data_logger.is_started:
                    self.data_logger.stop()
            except Exception:
                pass

        if self.vehicle_state is not None:
            try:
                if self.vehicle_state.is_started:
                    self.vehicle_state.stop()
            except Exception:
                pass

        if self.router is not None:
            try:
                if self.router.is_running:
                    self.router.stop()
            except Exception:
                pass

        if self.connection_manager is not None:
            try:
                if self.connection_manager.is_connected:
                    self.connection_manager.disconnect()
            except Exception:
                pass

        self._started = False
