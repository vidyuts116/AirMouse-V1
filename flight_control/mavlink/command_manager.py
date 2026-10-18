import threading
import time

from pymavlink import mavutil


class MAVLinkCommandManager:
    """Coordinate MAVLink commands using routed acknowledgements and vehicle state."""

    def __init__(self, connection, router, vehicle_state):
        if connection is None:
            raise ValueError("A valid MAVLink connection is required.")

        if router is None:
            raise ValueError("A MAVLink message router is required.")

        if vehicle_state is None:
            raise ValueError("A Vehicle State Manager is required.")

        self.connection = connection
        self.router = router
        self.vehicle_state = vehicle_state

        self._started = False

        self._ack_condition = threading.Condition()
        self._command_acks = {}

        # MAVLink COMMAND_ACK correlation is primarily based on command ID.
        # Serialize command transactions so concurrent operations cannot
        # consume or overwrite each other's acknowledgements.
        self._command_lock = threading.Lock()

    @property
    def is_started(self):
        """Return whether the manager is subscribed to routed MAVLink traffic."""
        return self._started

    def start(self):
        """Subscribe to routed COMMAND_ACK messages."""

        if self._started:
            raise RuntimeError("MAVLink Command Manager is already started.")

        self.router.subscribe(
            "COMMAND_ACK",
            self._handle_command_ack,
        )

        self._started = True

    def stop(self):
        """Remove Command Manager router subscriptions."""

        if not self._started:
            return

        self.router.unsubscribe(
            "COMMAND_ACK",
            self._handle_command_ack,
        )

        self._started = False

    def send_command_long(
        self,
        command,
        param1=0,
        param2=0,
        param3=0,
        param4=0,
        param5=0,
        param6=0,
        param7=0,
        ack_timeout=5,
    ):
        """Send COMMAND_LONG and wait for its routed COMMAND_ACK."""

        if not self._started:
            raise RuntimeError(
                "MAVLink Command Manager must be started before "
                "sending commands."
            )

        with self._command_lock:
            self._clear_command_ack(command)

            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                command,
                0,
                param1,
                param2,
                param3,
                param4,
                param5,
                param6,
                param7,
            )

            return self.wait_for_command_ack(
                command,
                timeout=ack_timeout,
            )

    def _clear_command_ack(self, command):
        """Remove any previously recorded ACK for a command."""

        with self._ack_condition:
            self._command_acks.pop(command, None)

    def wait_for_command_ack(self, command, timeout=5):
        """Wait for a routed COMMAND_ACK matching the requested command."""

        if not self._started:
            raise RuntimeError(
                "MAVLink Command Manager must be started before waiting "
                "for command acknowledgements."
            )

        deadline = time.monotonic() + timeout

        with self._ack_condition:
            while command not in self._command_acks:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise TimeoutError(
                        f"No COMMAND_ACK received for command {command}."
                    )

                self._ack_condition.wait(timeout=remaining)

            ack = self._command_acks.pop(command)

        result_name = mavutil.mavlink.enums[
            "MAV_RESULT"
        ][ack.result].name

        return {
            "command": ack.command,
            "result": ack.result,
            "result_name": result_name,
        }

    def wait_for_armed_state(self, armed, timeout=5, poll_interval=0.05):
        """Wait until routed vehicle state confirms the requested armed state."""

        deadline = time.monotonic() + timeout

        while True:
            state = self.vehicle_state.get_state()
            flight = state["flight"]

            if flight and flight.get("armed") is armed:
                return {
                    "armed": flight["armed"],
                    "system_id": flight.get("system_id"),
                    "component_id": flight.get("component_id"),
                    "flight_mode": flight.get("flight_mode"),
                }

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                state_name = "ARMED" if armed else "DISARMED"

                raise TimeoutError(
                    f"Vehicle did not reach {state_name} state "
                    f"within {timeout} seconds."
                )

            time.sleep(min(poll_interval, remaining))

    def wait_for_mode(
        self,
        mode_name,
        timeout=5,
        poll_interval=0.05,
    ):
        """Wait until routed vehicle state confirms the requested mode."""

        requested_mode = mode_name.upper()
        deadline = time.monotonic() + timeout

        while True:
            state = self.vehicle_state.get_state()
            flight = state["flight"]

            if flight:
                current_mode = flight.get("flight_mode")

                if current_mode == requested_mode:
                    return {
                        "mode": current_mode,
                        "armed": flight.get("armed"),
                        "system_id": flight.get("system_id"),
                        "component_id": flight.get("component_id"),
                    }

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise TimeoutError(
                    f"Vehicle did not reach {requested_mode} mode "
                    f"within {timeout} seconds."
                )

            time.sleep(min(poll_interval, remaining))

    def set_mode(self, mode_name, state_timeout=5):
        """Request a flight-mode change and verify routed vehicle state."""

        if not self._started:
            raise RuntimeError(
                "MAVLink Command Manager must be started before "
                "changing flight mode."
            )

        requested_mode = mode_name.upper()

        mode_mapping = self.connection.mode_mapping()

        if (
            not mode_mapping
            or requested_mode not in mode_mapping
        ):
            raise ValueError(
                f"Unsupported flight mode: {requested_mode}"
            )

        requested_mode_id = mode_mapping[requested_mode]

        self.connection.mav.set_mode_send(
            self.connection.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            requested_mode_id,
        )

        state = self.wait_for_mode(
            requested_mode,
            timeout=state_timeout,
        )

        return {
            "success": True,
            "mode": requested_mode,
            "custom_mode": requested_mode_id,
            "state": state,
        }

    def arm(self, ack_timeout=5, state_timeout=5):
        """Request arming and verify the resulting routed vehicle state."""

        ack = self.send_command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=1,
            ack_timeout=ack_timeout,
        )

        if ack["result"] != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            return {
                "success": False,
                "ack": ack,
                "state": None,
            }

        state = self.wait_for_armed_state(
            True,
            timeout=state_timeout,
        )

        return {
            "success": True,
            "ack": ack,
            "state": state,
        }

    def disarm(self, ack_timeout=5, state_timeout=5):
        """Request disarming and verify the resulting routed vehicle state."""

        ack = self.send_command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=0,
            ack_timeout=ack_timeout,
        )

        if ack["result"] != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            return {
                "success": False,
                "ack": ack,
                "state": None,
            }

        state = self.wait_for_armed_state(
            False,
            timeout=state_timeout,
        )

        return {
            "success": True,
            "ack": ack,
            "state": state,
        }

    def _handle_command_ack(self, message):
        """Record a routed COMMAND_ACK and wake waiting command operations."""

        command = message.command

        with self._ack_condition:
            self._command_acks[command] = message
            self._ack_condition.notify_all()
