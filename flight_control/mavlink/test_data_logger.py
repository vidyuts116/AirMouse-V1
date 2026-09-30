import json
import tempfile
import time
from pathlib import Path

from data_logger import MAVLinkDataLogger


class FakeRouter:
    """Minimal router contract used to test logger subscriptions."""

    def __init__(self):
        self.subscribers = {}

    def subscribe(self, message_type, callback):
        callbacks = self.subscribers.setdefault(
            message_type.upper(),
            [],
        )

        if callback not in callbacks:
            callbacks.append(callback)

    def unsubscribe(self, message_type, callback):
        callbacks = self.subscribers.get(
            message_type.upper(),
            [],
        )

        try:
            callbacks.remove(callback)
        except ValueError:
            return False

        if not callbacks:
            self.subscribers.pop(
                message_type.upper(),
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


class FakeMessage:
    def __init__(self, message_type, sequence):
        self.message_type = message_type
        self.sequence = sequence

    def get_type(self):
        return self.message_type

    def to_dict(self):
        return {
            "mavpackettype": self.message_type,
            "sequence": self.sequence,
        }

    def __str__(self):
        return (
            f"FakeMessage("
            f"{self.message_type}, {self.sequence})"
        )


print("AirMouse V1 - MAVLink Data Logger Test")

with tempfile.TemporaryDirectory() as temp_directory:
    log_path = Path(temp_directory) / "airmouse.jsonl"

    router = FakeRouter()

    logger = MAVLinkDataLogger(
        router,
        log_path,
        message_types=(
            "HEARTBEAT",
            "ATTITUDE",
        ),
        queue_size=32,
    )

    print("\nTEST 1: Initial lifecycle")

    if logger.is_started:
        raise SystemExit(
            "FAIL: Logger unexpectedly started."
        )

    logger.start()

    if not logger.is_started:
        raise SystemExit(
            "FAIL: Logger did not start."
        )

    try:
        logger.start()

    except RuntimeError:
        pass

    else:
        raise SystemExit(
            "FAIL: Duplicate logger start was accepted."
        )

    print("PASS: Logger lifecycle start validated.")

    print("\nTEST 2: Router subscriptions")

    expected_types = {
        "HEARTBEAT",
        "ATTITUDE",
    }

    if set(router.subscribers) != expected_types:
        raise SystemExit(
            "FAIL: Logger subscriptions incorrect: "
            f"{set(router.subscribers)}"
        )

    print("PASS: Logger subscribed through router.")

    print("\nTEST 3: Routed message logging")

    router.dispatch(
        FakeMessage("HEARTBEAT", 1)
    )

    router.dispatch(
        FakeMessage("ATTITUDE", 2)
    )

    router.dispatch(
        FakeMessage("HEARTBEAT", 3)
    )

    deadline = time.monotonic() + 2

    while (
        logger.get_statistics()["written"] < 3
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)

    statistics = logger.get_statistics()

    if statistics["received"] != 3:
        raise SystemExit(
            "FAIL: Expected 3 received records, "
            f"found {statistics['received']}."
        )

    if statistics["written"] != 3:
        raise SystemExit(
            "FAIL: Expected 3 written records, "
            f"found {statistics['written']}."
        )

    if statistics["dropped"] != 0:
        raise SystemExit(
            "FAIL: Unexpected dropped records."
        )

    if statistics["write_errors"] != 0:
        raise SystemExit(
            "FAIL: Unexpected write errors."
        )

    print("PASS: Routed messages reached logger.")
    print("PASS: Logger statistics correct.")

    print("\nTEST 4: JSONL persistence")

    with log_path.open(
        "r",
        encoding="utf-8",
    ) as log_file:
        records = [
            json.loads(line)
            for line in log_file
            if line.strip()
        ]

    if len(records) != 3:
        raise SystemExit(
            f"FAIL: Expected 3 JSONL records, "
            f"found {len(records)}."
        )

    expected_sequence = [1, 2, 3]

    actual_sequence = [
        record["data"]["sequence"]
        for record in records
    ]

    if actual_sequence != expected_sequence:
        raise SystemExit(
            "FAIL: JSONL ordering incorrect: "
            f"{actual_sequence}"
        )

    for record in records:
        if "timestamp_utc" not in record:
            raise SystemExit(
                "FAIL: UTC timestamp missing."
            )

        if "monotonic_s" not in record:
            raise SystemExit(
                "FAIL: monotonic timestamp missing."
            )

        if "message_type" not in record:
            raise SystemExit(
                "FAIL: message type missing."
            )

        if "data" not in record:
            raise SystemExit(
                "FAIL: message payload missing."
            )

    print("PASS: Valid structured JSONL persisted.")
    print("PASS: Message ordering preserved.")

    print("\nTEST 5: Clean shutdown")

    logger.stop()

    if logger.is_started:
        raise SystemExit(
            "FAIL: Logger remained started."
        )

    if router.subscribers:
        raise SystemExit(
            "FAIL: Logger subscriptions remained after stop."
        )

    print("PASS: Logger stopped.")
    print("PASS: Router subscriptions removed.")

    print("\nTEST 6: No logging after shutdown")

    previous_statistics = logger.get_statistics()

    router.dispatch(
        FakeMessage("HEARTBEAT", 4)
    )

    time.sleep(0.1)

    final_statistics = logger.get_statistics()

    if (
        final_statistics["received"]
        != previous_statistics["received"]
    ):
        raise SystemExit(
            "FAIL: Logger received data after shutdown."
        )

    with log_path.open(
        "r",
        encoding="utf-8",
    ) as log_file:
        final_records = [
            line
            for line in log_file
            if line.strip()
        ]

    if len(final_records) != 3:
        raise SystemExit(
            "FAIL: Log changed after shutdown."
        )

    print("PASS: Shutdown prevents further logging.")

print(
    "\nPASS: MAVLink Data Logger isolated tests completed."
)
