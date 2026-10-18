import threading
import time

from command_manager import MAVLinkCommandManager


class FakeMAV:
    pass


class FakeConnection:
    def __init__(self):
        self.target_system = 1
        self.target_component = 1
        self.mav = FakeMAV()


class FakeRouter:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, message_type, callback):
        callbacks = self.subscribers.setdefault(message_type, [])

        if callback not in callbacks:
            callbacks.append(callback)

    def unsubscribe(self, message_type, callback):
        callbacks = self.subscribers.get(message_type, [])

        if callback not in callbacks:
            return False

        callbacks.remove(callback)

        if not callbacks:
            del self.subscribers[message_type]

        return True


class FakeVehicleState:
    def __init__(self):
        self._lock = threading.Lock()

        self._state = {
            "flight": {},
        }

    def set_flight_state(
        self,
        mode,
        armed=False,
        system_id=1,
        component_id=1,
    ):
        with self._lock:
            self._state["flight"] = {
                "flight_mode": mode,
                "armed": armed,
                "system_id": system_id,
                "component_id": component_id,
            }

    def clear_flight_state(self):
        with self._lock:
            self._state["flight"] = {}

    def get_state(self):
        with self._lock:
            return {
                "flight": self._state["flight"].copy(),
            }


print("AirMouse V1 - Command Manager Mode State Wait Test")

connection = FakeConnection()
router = FakeRouter()
vehicle_state = FakeVehicleState()

manager = MAVLinkCommandManager(
    connection,
    router,
    vehicle_state,
)


print("\nTEST 1: Immediate matching mode")

vehicle_state.set_flight_state(
    "STABILIZE",
    armed=False,
)

start = time.monotonic()

state = manager.wait_for_mode(
    "stabilize",
    timeout=0.5,
)

elapsed = time.monotonic() - start

if state["mode"] != "STABILIZE":
    raise SystemExit(
        f"FAIL: Expected STABILIZE, got {state['mode']}."
    )

if state["armed"] is not False:
    raise SystemExit(
        "FAIL: Armed state was not preserved."
    )

if elapsed >= 0.2:
    raise SystemExit(
        "FAIL: Existing matching mode was not detected immediately."
    )

print("PASS: Existing STABILIZE mode detected immediately.")
print(f"Mode: {state['mode']}")
print(f"Armed: {state['armed']}")


print("\nTEST 2: Wait for mode transition")

vehicle_state.set_flight_state(
    "STABILIZE",
    armed=False,
)

result = {}
error = {}


def wait_for_guided():
    try:
        result["state"] = manager.wait_for_mode(
            "GUIDED",
            timeout=1,
        )

    except Exception as exc:
        error["exception"] = exc


waiter = threading.Thread(
    target=wait_for_guided,
)

waiter.start()

time.sleep(0.15)

if not waiter.is_alive():
    raise SystemExit(
        "FAIL: Mode waiter returned before GUIDED transition."
    )

print("PASS: Waiter remained blocked before mode transition.")

vehicle_state.set_flight_state(
    "GUIDED",
    armed=False,
)

waiter.join(timeout=1)

if waiter.is_alive():
    raise SystemExit(
        "FAIL: Mode waiter did not detect GUIDED transition."
    )

if "exception" in error:
    raise SystemExit(
        f"FAIL: Mode waiter raised: {error['exception']}"
    )

state = result.get("state")

if state is None:
    raise SystemExit(
        "FAIL: Mode waiter returned no state."
    )

if state["mode"] != "GUIDED":
    raise SystemExit(
        f"FAIL: Expected GUIDED, got {state['mode']}."
    )

print("PASS: Waiter detected routed GUIDED state.")
print(f"Mode after transition: {state['mode']}")


print("\nTEST 3: Mode timeout")

vehicle_state.set_flight_state(
    "STABILIZE",
    armed=False,
)

start = time.monotonic()

try:
    manager.wait_for_mode(
        "GUIDED",
        timeout=0.2,
    )

except TimeoutError as exc:
    elapsed = time.monotonic() - start

    if elapsed < 0.18:
        raise SystemExit(
            "FAIL: Mode timeout occurred too early."
        )

    print(
        f"PASS: Missing GUIDED mode timed out "
        f"after {elapsed:.3f} s."
    )
    print(f"Timeout message: {exc}")

else:
    raise SystemExit(
        "FAIL: Missing GUIDED mode did not raise TimeoutError."
    )


print("\nTEST 4: Empty initial flight state")

vehicle_state.clear_flight_state()

result = {}
error = {}


def wait_from_empty_state():
    try:
        result["state"] = manager.wait_for_mode(
            "GUIDED",
            timeout=1,
        )

    except Exception as exc:
        error["exception"] = exc


waiter = threading.Thread(
    target=wait_from_empty_state,
)

waiter.start()

time.sleep(0.1)

if not waiter.is_alive():
    raise SystemExit(
        "FAIL: Empty flight state caused premature return."
    )

vehicle_state.set_flight_state(
    "GUIDED",
    armed=True,
)

waiter.join(timeout=1)

if waiter.is_alive():
    raise SystemExit(
        "FAIL: Waiter did not recover from empty flight state."
    )

if "exception" in error:
    raise SystemExit(
        f"FAIL: Empty-state waiter raised: {error['exception']}"
    )

state = result.get("state")

if state is None or state["mode"] != "GUIDED":
    raise SystemExit(
        "FAIL: GUIDED was not detected after empty initial state."
    )

if state["armed"] is not True:
    raise SystemExit(
        "FAIL: Updated armed state was not returned."
    )

print("PASS: Empty flight state handled safely.")
print("PASS: Later GUIDED state detected correctly.")


print("\nTEST 5: Case normalization")

vehicle_state.set_flight_state(
    "GUIDED",
    armed=False,
)

state = manager.wait_for_mode(
    "guided",
    timeout=0.5,
)

if state["mode"] != "GUIDED":
    raise SystemExit(
        "FAIL: Lower-case requested mode was not normalized."
    )

print("PASS: Requested mode name normalized correctly.")


print(
    "\nPASS: Command Manager mode-state wait tests completed."
)
