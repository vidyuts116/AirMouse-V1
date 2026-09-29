import time

from pymavlink import mavutil


class MAVLinkCommandInterface:
    """Reusable MAVLink command interface for AirMouse V1."""

    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.master = None

    def connect(self, heartbeat_timeout=10):
        """Connect to the vehicle and verify communication with a heartbeat."""

        self.master = mavutil.mavlink_connection(self.connection_string)

        heartbeat = self.master.wait_heartbeat(timeout=heartbeat_timeout)

        if heartbeat is None:
            raise TimeoutError(
                f"No MAVLink heartbeat received within "
                f"{heartbeat_timeout} seconds."
            )

        return {
            "system_id": heartbeat.get_srcSystem(),
            "component_id": heartbeat.get_srcComponent(),
        }

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
        """Send COMMAND_LONG and wait for its matching COMMAND_ACK."""

        if self.master is None:
            raise RuntimeError("MAVLink connection has not been established.")

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
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

        deadline = time.monotonic() + ack_timeout

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise TimeoutError(
                    f"No COMMAND_ACK received for command {command}."
                )

            ack = self.master.recv_match(
                type="COMMAND_ACK",
                blocking=True,
                timeout=remaining,
            )

            if ack is None:
                raise TimeoutError(
                    f"No COMMAND_ACK received for command {command}."
                )

            if ack.command != command:
                continue

            result_name = mavutil.mavlink.enums[
                "MAV_RESULT"
            ][ack.result].name

            return {
                "command": ack.command,
                "result": ack.result,
                "result_name": result_name,
            }

    def wait_for_armed_state(self, armed, timeout=5):
        """Wait until heartbeat telemetry confirms the requested armed state."""

        if self.master is None:
            raise RuntimeError("MAVLink connection has not been established.")

        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                state_name = "ARMED" if armed else "DISARMED"
                raise TimeoutError(
                    f"Vehicle did not reach {state_name} state "
                    f"within {timeout} seconds."
                )

            heartbeat = self.master.recv_match(
                type="HEARTBEAT",
                blocking=True,
                timeout=remaining,
            )

            if heartbeat is None:
                continue

            is_armed = bool(
                heartbeat.base_mode
                & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )

            if is_armed == armed:
                return {
                    "armed": is_armed,
                    "system_id": heartbeat.get_srcSystem(),
                    "component_id": heartbeat.get_srcComponent(),
                }

    def arm(self, ack_timeout=5, state_timeout=5):
        """Request vehicle arming and verify the resulting armed state."""

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
            armed=True,
            timeout=state_timeout,
        )

        return {
            "success": True,
            "ack": ack,
            "state": state,
        }

    def disarm(self, ack_timeout=5, state_timeout=5):
        """Request vehicle disarming and verify the resulting disarmed state."""

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
            armed=False,
            timeout=state_timeout,
        )

        return {
            "success": True,
            "ack": ack,
            "state": state,
        }
