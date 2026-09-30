import threading
import time

from pymavlink import mavutil

from command_manager import MAVLinkCommandManager


class FakeRouter:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, message_type, callback):
        callbacks = self.subscribers.setdefault(
            message_type,
            [],
        )

        if callback not in callbacks:
            callbacks.append(callback)

    def unsubscribe(self, message_type, callback):
        callbacks = self.subscribers.get(
            message_type,
            [],
        )

        if callback not in callbacks:
            return False

        callbacks.remove(callback)

        if not callbacks:
            self.subscribers.pop(
                message_type,
                None,
            )

        return True

    def dispatch(self, message):
        callbacks = list(
            self.subscribers.get(
                message.get_type(),
                [],
            )
        )

        for callback in callbacks:
            callback(message)


class FakeCommandAck:
    def __init__(self, command, result):
        self.command = command
        self.result = result

    def get_type(self):
        return "COMMAND_ACK"


class FakeVehicleState:
    def __init__(self, armed=False):
        self._lock = threading.Lock()

        self._state = {
            "flight": {
                "armed": armed,
                "system_id": 1,
                "component_id": 1,
                "flight_mode": "STABILIZE",
            },
            "attitude": {},
            "global_position": {},
            "local_position": {},
            "system_health": {},
            "battery": {},
        }

    def get_state(self):
        with self._lock:
            return {
                section: values.copy()
                for section, values in self._state.items()
            }


class FakeMAV:
    def __init__(self, router):
        self.router = router
        self.transmissions = []

    def command_long_send(
        self,
        target_system,
        target_component,
        command,
        confirmation,
        param1,
        param2,
        param3,
        param4,
        param5,
        param6,
        param7,
    ):
        self.transmissions.append({
            "target_system": target_system,
            "target_component": target_component,
            "command": command,
            "confirmation": confirmation,
            "params": (
                param1,
                param2,
                param3,
                param4,
                param5,
                param6,
                param7,
            ),
        })

        def reject_command():
            time.sleep(0.05)

            ack = FakeCommandAck(
                command,
                mavutil.mavlink.MAV_RESULT_DENIED,
            )

            self.router.dispatch(ack)

        threading.Thread(
            target=reject_command,
            daemon=True,
        ).start()


class FakeConnection:
    def __init__(self, router):
        self.target_system = 1
        self.target_component = 1
        self.mav = FakeMAV(router)


print("AirMouse V1 - Command Manager Rejected ACK Test")

router = FakeRouter()
vehicle_state = FakeVehicleState(
    armed=False,
)

connection = FakeConnection(
    router,
)

manager = MAVLinkCommandManager(
    connection,
    router,
    vehicle_state,
)

manager.start()


print("\nTEST 1: Rejected ARM command")

started = time.monotonic()

result = manager.arm(
    ack_timeout=1,
    state_timeout=1,
)

elapsed = time.monotonic() - started

if result["success"] is not False:
    raise SystemExit(
        "FAIL: Rejected ARM command reported success."
    )

if result["ack"]["result"] != mavutil.mavlink.MAV_RESULT_DENIED:
    raise SystemExit(
        "FAIL: Rejected ACK result was not preserved."
    )

if result["ack"]["result_name"] != "MAV_RESULT_DENIED":
    raise SystemExit(
        "FAIL: Rejected ACK result name was incorrect."
    )

if result["state"] is not None:
    raise SystemExit(
        "FAIL: Rejected ARM command returned a confirmed state."
    )

if elapsed >= 0.8:
    raise SystemExit(
        "FAIL: ARM continued waiting for state after command rejection."
    )

state = vehicle_state.get_state()

if state["flight"]["armed"] is not False:
    raise SystemExit(
        "FAIL: Vehicle state changed after rejected ARM command."
    )

print("PASS: Rejected ARM ACK detected.")
print("PASS: ARM operation reported failure.")
print("PASS: No armed-state confirmation was attempted.")
print("PASS: Vehicle remained DISARMED.")
print(f"Failure returned after {elapsed:.3f} s.")


print("\nTEST 2: Command transmission")

if len(connection.mav.transmissions) != 1:
    raise SystemExit(
        "FAIL: Unexpected number of command transmissions."
    )

transmission = connection.mav.transmissions[0]

if transmission["command"] != (
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM
):
    raise SystemExit(
        "FAIL: Incorrect MAVLink command transmitted."
    )

if transmission["params"][0] != 1:
    raise SystemExit(
        "FAIL: Rejected ARM command did not use param1=1."
    )

print("PASS: ARM command itself was transmitted correctly.")


manager.stop()

if manager.is_started:
    raise SystemExit(
        "FAIL: Command Manager remained started."
    )

print("PASS: Command Manager stopped cleanly.")

print(
    "\nPASS: Command Manager rejected-ACK tests completed."
)
