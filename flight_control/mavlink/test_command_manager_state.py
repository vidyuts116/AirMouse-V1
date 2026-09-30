import threading
import time

from command_manager import MAVLinkCommandManager


class FakeRouter:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, message_type, callback):
        self.subscribers.setdefault(message_type, []).append(callback)

    def unsubscribe(self, message_type, callback):
        callbacks = self.subscribers.get(message_type, [])

        if callback in callbacks:
            callbacks.remove(callback)
            return True

        return False


class FakeMAV:
    pass


class FakeConnection:
    def __init__(self):
        self.target_system = 1
        self.target_component = 1
        self.mav = FakeMAV()


class FakeVehicleState:
    def __init__(self):
        self._lock = threading.Lock()

        self._state = {
            "flight": {},
            "attitude": {},
            "global_position": {},
            "local_position": {},
            "system_health": {},
            "battery": {},
        }

    def set_flight_state(
        self,
        armed,
        system_id=1,
        component_id=1,
        flight_mode="STABILIZE",
    ):
        with self._lock:
            self._state["flight"] = {
                "armed": armed,
                "system_id": system_id,
                "component_id": component_id,
                "flight_mode": flight_mode,
            }

    def get_state(self):
        with self._lock:
            return {
                section: values.copy()
                for section, values in self._state.items()
            }


print("AirMouse V1 - Command Manager Vehicle State Wait Test")

connection = FakeConnection()
router = FakeRouter()
vehicle_state = FakeVehicleState()

manager = MAVLinkCommandManager(
    connection,
    router,
    vehicle_state,
)


print("\nTEST 1: Immediate matching state")

vehicle_state.set_flight_state(
    armed=False,
    flight_mode="STABILIZE",
)

result = manager.wait_for_armed_state(
    False,
    timeout=0.5,
)

if result["armed"] is not False:
    raise SystemExit(
        "FAIL: Existing disarmed state was not detected."
    )

if result["flight_mode"] != "STABILIZE":
    raise SystemExit(
        "FAIL: Flight mode was not returned correctly."
    )

print("PASS: Existing DISARMED state detected immediately.")


print("\nTEST 2: Wait for state transition")

transition_result = {}
transition_error = {}


def wait_for_armed():
    try:
        transition_result["state"] = manager.wait_for_armed_state(
            True,
            timeout=1.0,
            poll_interval=0.01,
        )

    except Exception as error:
        transition_error["error"] = error


waiter = threading.Thread(
    target=wait_for_armed,
    name="armed-state-test-waiter",
)

waiter.start()

time.sleep(0.1)

if not waiter.is_alive():
    raise SystemExit(
        "FAIL: Armed-state waiter returned before state changed."
    )

vehicle_state.set_flight_state(
    armed=True,
    flight_mode="GUIDED",
)

waiter.join(timeout=1.0)

if waiter.is_alive():
    raise SystemExit(
        "FAIL: Armed-state waiter did not wake after state changed."
    )

if transition_error:
    raise SystemExit(
        f"FAIL: Armed-state waiter raised: "
        f"{transition_error['error']}"
    )

state = transition_result.get("state")

if state is None:
    raise SystemExit(
        "FAIL: Armed-state waiter returned no result."
    )

if state["armed"] is not True:
    raise SystemExit(
        "FAIL: Armed state was not confirmed."
    )

if state["flight_mode"] != "GUIDED":
    raise SystemExit(
        "FAIL: Updated flight mode was not returned."
    )

print("PASS: Waiter remained blocked before state transition.")
print("PASS: Waiter detected routed ARMED state.")
print(f"Mode after transition: {state['flight_mode']}")


print("\nTEST 3: State timeout")

vehicle_state.set_flight_state(
    armed=False,
    flight_mode="STABILIZE",
)

started = time.monotonic()

try:
    manager.wait_for_armed_state(
        True,
        timeout=0.2,
        poll_interval=0.01,
    )

except TimeoutError as error:
    elapsed = time.monotonic() - started

    print(
        f"PASS: Missing ARMED state timed out after "
        f"{elapsed:.3f} s."
    )
    print(f"Timeout message: {error}")

else:
    raise SystemExit(
        "FAIL: Missing ARMED state did not raise TimeoutError."
    )


print("\nTEST 4: Empty initial flight state")

vehicle_state = FakeVehicleState()

manager = MAVLinkCommandManager(
    connection,
    router,
    vehicle_state,
)

try:
    manager.wait_for_armed_state(
        True,
        timeout=0.1,
        poll_interval=0.01,
    )

except TimeoutError:
    print("PASS: Empty flight state handled safely.")

else:
    raise SystemExit(
        "FAIL: Empty flight state unexpectedly matched."
    )


print(
    "\nPASS: Command Manager vehicle-state wait tests completed."
)
