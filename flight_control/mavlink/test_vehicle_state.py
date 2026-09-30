from vehicle_state import VehicleStateManager


class FakeRouter:
    def __init__(self):
        self.subscriptions = {}
        self.subscribe_calls = []
        self.unsubscribe_calls = []

    def subscribe(self, message_type, callback):
        self.subscribe_calls.append(message_type)
        self.subscriptions[message_type] = callback

    def unsubscribe(self, message_type, callback):
        self.unsubscribe_calls.append(message_type)

        registered = self.subscriptions.get(message_type)

        if registered != callback:
            return False

        del self.subscriptions[message_type]
        return True


print("AirMouse V1 - Vehicle State Manager Behaviour Test")

router = FakeRouter()
manager = VehicleStateManager(router)


print("\nTEST 1: Initial lifecycle state")

if manager.is_started:
    raise SystemExit(
        "FAIL: New Vehicle State Manager unexpectedly reports started."
    )

print("PASS: Vehicle State Manager initially stopped.")


print("\nTEST 2: Start and subscriptions")

manager.start()

if not manager.is_started:
    raise SystemExit(
        "FAIL: Vehicle State Manager did not enter started state."
    )

expected_types = set(
    VehicleStateManager.MESSAGE_TYPES
)

actual_types = set(
    router.subscriptions.keys()
)

if actual_types != expected_types:
    raise SystemExit(
        f"FAIL: Incorrect subscriptions: {actual_types}"
    )

if len(router.subscribe_calls) != len(expected_types):
    raise SystemExit(
        "FAIL: Unexpected number of subscribe() calls."
    )

print(
    f"PASS: Subscribed to all "
    f"{len(expected_types)} required MAVLink message types."
)


print("\nTEST 3: Duplicate start protection")

try:
    manager.start()

except RuntimeError as error:
    print(
        f"PASS: Duplicate start rejected: {error}"
    )

else:
    raise SystemExit(
        "FAIL: Duplicate Vehicle State Manager start was accepted."
    )


print("\nTEST 4: Stop and unsubscribe")

manager.stop()

if manager.is_started:
    raise SystemExit(
        "FAIL: Vehicle State Manager remained started after stop()."
    )

if router.subscriptions:
    raise SystemExit(
        f"FAIL: Subscriptions remain after stop(): "
        f"{router.subscriptions}"
    )

if set(router.unsubscribe_calls) != expected_types:
    raise SystemExit(
        "FAIL: Not all required subscriptions were removed."
    )

print("PASS: All subscriptions removed cleanly.")


print("\nTEST 5: Repeated stop")

manager.stop()

if manager.is_started:
    raise SystemExit(
        "FAIL: Repeated stop changed lifecycle state incorrectly."
    )

print("PASS: Repeated stop handled safely.")


print("\nTEST 6: Restart")

manager.start()

if set(router.subscriptions.keys()) != expected_types:
    raise SystemExit(
        "FAIL: Required subscriptions were not restored on restart."
    )

manager.stop()

if router.subscriptions:
    raise SystemExit(
        "FAIL: Subscriptions remained after second shutdown."
    )

print("PASS: Vehicle State Manager restarted and stopped cleanly.")


print("\nTEST 7: State snapshot structure")

state = manager.get_state()

expected_sections = {
    "flight",
    "attitude",
    "global_position",
    "local_position",
    "system_health",
    "battery",
}

if set(state.keys()) != expected_sections:
    raise SystemExit(
        f"FAIL: Unexpected state sections: {state.keys()}"
    )

for section in expected_sections:
    if state[section] != {}:
        raise SystemExit(
            f"FAIL: Unexpected initial data in {section}."
        )

print("PASS: State snapshot structure is correct.")

print(
    "\nPASS: Vehicle State Manager behaviour tests completed."
)
