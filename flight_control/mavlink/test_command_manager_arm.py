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
    def __init__(self):
        self._lock = threading.Lock()

        self._state = {
            "flight": {
                "armed": False,
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

    def set_armed(self, armed):
        with self._lock:
            self._state["flight"]["armed"] = armed

    def get_state(self):
        with self._lock:
            return {
                section: values.copy()
                for section, values in self._state.items()
            }


class FakeMAV:
    def __init__(self, router, vehicle_state):
        self.router = router
        self.vehicle_state = vehicle_state
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

        if command != mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            return

        requested_armed = param1 == 1

        def complete_transaction():
            time.sleep(0.05)

            ack = FakeCommandAck(
                command,
                mavutil.mavlink.MAV_RESULT_ACCEPTED,
            )

            self.router.dispatch(ack)

            time.sleep(0.05)

            self.vehicle_state.set_armed(
                requested_armed
            )

        threading.Thread(
            target=complete_transaction,
            daemon=True,
        ).start()


class FakeConnection:
    def __init__(self, router, vehicle_state):
        self.target_system = 1
        self.target_component = 1

        self.mav = FakeMAV(
            router,
            vehicle_state,
        )


print("AirMouse V1 - Command Manager ARM/DISARM Test")

router = FakeRouter()
vehicle_state = FakeVehicleState()

connection = FakeConnection(
    router,
    vehicle_state,
)

manager = MAVLinkCommandManager(
    connection,
    router,
    vehicle_state,
)

manager.start()


print("\nTEST 1: ARM transaction")

arm_result = manager.arm(
    ack_timeout=1,
    state_timeout=1,
)

if not arm_result["success"]:
    raise SystemExit(
        "FAIL: ARM transaction reported failure."
    )

if arm_result["ack"]["result"] != mavutil.mavlink.MAV_RESULT_ACCEPTED:
    raise SystemExit(
        "FAIL: ARM acknowledgement was not accepted."
    )

if arm_result["state"]["armed"] is not True:
    raise SystemExit(
        "FAIL: ARM state was not confirmed."
    )

arm_tx = connection.mav.transmissions[0]

if arm_tx["command"] != mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
    raise SystemExit(
        "FAIL: Incorrect MAVLink ARM command."
    )

if arm_tx["params"][0] != 1:
    raise SystemExit(
        "FAIL: ARM command did not use param1=1."
    )

print("PASS: ARM command transmitted.")
print("PASS: ARM COMMAND_ACK received through router.")
print("PASS: Vehicle State confirmed ARMED.")


print("\nTEST 2: DISARM transaction")

disarm_result = manager.disarm(
    ack_timeout=1,
    state_timeout=1,
)

if not disarm_result["success"]:
    raise SystemExit(
        "FAIL: DISARM transaction reported failure."
    )

if disarm_result["ack"]["result"] != mavutil.mavlink.MAV_RESULT_ACCEPTED:
    raise SystemExit(
        "FAIL: DISARM acknowledgement was not accepted."
    )

if disarm_result["state"]["armed"] is not False:
    raise SystemExit(
        "FAIL: DISARM state was not confirmed."
    )

disarm_tx = connection.mav.transmissions[1]

if disarm_tx["command"] != mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
    raise SystemExit(
        "FAIL: Incorrect MAVLink DISARM command."
    )

if disarm_tx["params"][0] != 0:
    raise SystemExit(
        "FAIL: DISARM command did not use param1=0."
    )

print("PASS: DISARM command transmitted.")
print("PASS: DISARM COMMAND_ACK received through router.")
print("PASS: Vehicle State confirmed DISARMED.")


print("\nTEST 3: Transmission sequence")

if len(connection.mav.transmissions) != 2:
    raise SystemExit(
        "FAIL: Unexpected number of command transmissions."
    )

params = [
    transmission["params"][0]
    for transmission in connection.mav.transmissions
]

if params != [1, 0]:
    raise SystemExit(
        f"FAIL: Incorrect ARM/DISARM sequence: {params}"
    )

print(f"Transmission param1 sequence: {params}")
print("PASS: ARM followed by DISARM correctly.")


manager.stop()

if manager.is_started:
    raise SystemExit(
        "FAIL: Command Manager remained started."
    )

print("\nPASS: Command Manager stopped cleanly.")

print(
    "\nPASS: Command Manager ARM/DISARM tests completed."
)
