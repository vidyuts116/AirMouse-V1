import threading
import time

from pymavlink import mavutil

from command_manager import MAVLinkCommandManager


class FakeMAV:
    def __init__(self):
        self.set_mode_calls = []

    def set_mode_send(
        self,
        target_system,
        base_mode,
        custom_mode,
    ):
        self.set_mode_calls.append({
            "target_system": target_system,
            "base_mode": base_mode,
            "custom_mode": custom_mode,
        })


class FakeConnection:
    def __init__(self):
        self.target_system = 1
        self.target_component = 1
        self.mav = FakeMAV()

    def mode_mapping(self):
        return {
            "STABILIZE": 0,
            "GUIDED": 4,
            "LOITER": 5,
            "LAND": 9,
        }


class FakeRouter:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, message_type, callback):
        self.subscribers.setdefault(
            message_type,
            [],
        ).append(callback)

    def unsubscribe(self, message_type, callback):
        callbacks = self.subscribers.get(
            message_type,
            [],
        )

        if callback in callbacks:
            callbacks.remove(callback)


class FakeVehicleState:
    def __init__(self):
        self._lock = threading.Lock()

        self._flight = {
            "flight_mode": "STABILIZE",
            "armed": False,
            "system_id": 1,
            "component_id": 1,
        }

    def get_state(self):
        with self._lock:
            return {
                "flight": self._flight.copy(),
            }

    def set_mode(self, mode_name):
        with self._lock:
            self._flight["flight_mode"] = mode_name


def main():
    print(
        "AirMouse V1 - Command Manager SET_MODE Test"
    )

    connection = FakeConnection()
    router = FakeRouter()
    vehicle_state = FakeVehicleState()

    manager = MAVLinkCommandManager(
        connection,
        router,
        vehicle_state,
    )

    manager.start()

    print("\nTEST 1: SET_MODE transmission")

    result_holder = {}
    error_holder = {}

    def change_mode():
        try:
            result_holder["result"] = manager.set_mode(
                "guided",
                state_timeout=1,
            )
        except Exception as error:
            error_holder["error"] = error

    worker = threading.Thread(
        target=change_mode,
    )

    worker.start()

    deadline = time.monotonic() + 1

    while not connection.mav.set_mode_calls:
        if time.monotonic() >= deadline:
            raise AssertionError(
                "SET_MODE was not transmitted."
            )

        time.sleep(0.01)

    call = connection.mav.set_mode_calls[0]

    assert call["target_system"] == 1

    assert (
        call["base_mode"]
        == mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    )

    assert call["custom_mode"] == 4

    print("PASS: SET_MODE transmitted correctly.")
    print(
        f"Target system: {call['target_system']}"
    )
    print(
        f"Custom mode ID: {call['custom_mode']}"
    )

    print("\nTEST 2: Wait for routed mode state")

    time.sleep(0.05)

    assert worker.is_alive()

    print(
        "PASS: Operation waited for vehicle-state "
        "confirmation."
    )

    vehicle_state.set_mode("GUIDED")

    worker.join(timeout=1)

    assert not worker.is_alive()

    if "error" in error_holder:
        raise error_holder["error"]

    result = result_holder["result"]

    assert result["success"] is True
    assert result["mode"] == "GUIDED"
    assert result["custom_mode"] == 4
    assert result["state"]["mode"] == "GUIDED"

    print(
        "PASS: Routed vehicle state confirmed GUIDED."
    )

    print("\nTEST 3: Case normalization")

    assert result["mode"] == "GUIDED"

    print(
        "PASS: Lowercase request normalized to GUIDED."
    )

    print("\nTEST 4: Unsupported mode")

    try:
        manager.set_mode(
            "NOT_A_REAL_MODE",
            state_timeout=0.1,
        )

    except ValueError as error:
        print(
            f"PASS: Unsupported mode rejected: {error}"
        )

    else:
        raise AssertionError(
            "Unsupported mode was not rejected."
        )

    assert len(connection.mav.set_mode_calls) == 1

    print(
        "PASS: Invalid mode produced no MAVLink "
        "transmission."
    )

    print("\nTEST 5: Manager lifecycle")

    manager.stop()

    assert manager.is_started is False

    print(
        "PASS: Command Manager stopped cleanly."
    )

    print(
        "\nPASS: Command Manager SET_MODE tests "
        "completed."
    )


if __name__ == "__main__":
    main()
