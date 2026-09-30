import threading
import time

from message_router import MAVLinkMessageRouter


class FakeMessage:
    def __init__(self, message_type, sequence=0):
        self.message_type = message_type
        self.sequence = sequence

    def get_type(self):
        return self.message_type


class FakeConnection:
    def __init__(self):
        self.messages = []
        self.lock = threading.Lock()

    def add_message(self, message):
        with self.lock:
            self.messages.append(message)

    def recv_match(self, blocking=False, timeout=None):
        deadline = time.monotonic() + (timeout or 0)

        while True:
            with self.lock:
                if self.messages:
                    return self.messages.pop(0)

            if not blocking or time.monotonic() >= deadline:
                return None

            time.sleep(0.01)


print("AirMouse V1 - MAVLink Message Router Test")

connection = FakeConnection()
router = MAVLinkMessageRouter(connection)

healthy_received = []


def healthy_callback(message):
    healthy_received.append(message.sequence)


def broken_callback(message):
    raise RuntimeError(
        f"Intentional callback failure for message {message.sequence}"
    )


print("\nTEST 1: Subscription and dispatch")

router.subscribe("HEARTBEAT", healthy_callback)
router.subscribe("HEARTBEAT", healthy_callback)

message = FakeMessage("HEARTBEAT", 1)

deliveries = router.dispatch(message)

if deliveries != 1 or healthy_received != [1]:
    raise SystemExit("FAIL: Subscription/dispatch behaviour incorrect.")

print("PASS: Message dispatched exactly once.")


print("\nTEST 2: Unsubscribe")

if not router.unsubscribe("HEARTBEAT", healthy_callback):
    raise SystemExit("FAIL: Existing subscription was not removed.")

if router.dispatch(FakeMessage("HEARTBEAT", 2)) != 0:
    raise SystemExit("FAIL: Removed subscriber still received messages.")

print("PASS: Subscriber removed correctly.")


print("\nTEST 3: Continuous receiver lifecycle")

router.subscribe("HEARTBEAT", healthy_callback)
router.start()

if not router.is_running:
    raise SystemExit("FAIL: Router did not start.")

try:
    router.start()

except RuntimeError:
    pass

else:
    raise SystemExit("FAIL: Duplicate router start was accepted.")

connection.add_message(FakeMessage("HEARTBEAT", 3))
connection.add_message(FakeMessage("HEARTBEAT", 4))

deadline = time.monotonic() + 2

while len(healthy_received) < 3 and time.monotonic() < deadline:
    time.sleep(0.01)

if healthy_received != [1, 3, 4]:
    raise SystemExit(
        f"FAIL: Continuous routing incorrect: {healthy_received}"
    )

router.stop()

if router.is_running:
    raise SystemExit("FAIL: Router did not stop cleanly.")

print("PASS: Continuous receiver started, routed, and stopped.")


print("\nTEST 4: Callback fault isolation")

router.subscribe("HEARTBEAT", broken_callback)
router.start()

connection.add_message(FakeMessage("HEARTBEAT", 5))
connection.add_message(FakeMessage("HEARTBEAT", 6))

deadline = time.monotonic() + 2

while len(healthy_received) < 5 and time.monotonic() < deadline:
    time.sleep(0.01)

if healthy_received != [1, 3, 4, 5, 6]:
    raise SystemExit(
        f"FAIL: Healthy subscriber did not survive callback errors: "
        f"{healthy_received}"
    )

callback_errors = router.get_callback_errors()

if len(callback_errors) != 2:
    raise SystemExit(
        f"FAIL: Expected 2 callback errors, "
        f"found {len(callback_errors)}."
    )

if not router.is_running:
    raise SystemExit(
        "FAIL: Router stopped after subscriber exception."
    )

router.stop()

print("PASS: Broken subscriber isolated.")
print("PASS: Healthy subscriber continued receiving.")
print("PASS: Callback errors retained for diagnostics.")

print("\nPASS: MAVLink Message Router tests completed.")
