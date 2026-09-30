from health_monitor import HealthFailSafeMonitor


class FakeVehicleState:
    """Minimal Vehicle State Manager substitute for deterministic tests."""

    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state


def make_state(updated_at=None):
    """Create a minimal vehicle-state snapshot."""

    if updated_at is None:
        system_health = {}
    else:
        system_health = {
            "updated_at": updated_at,
            "voltage_v": 12.6,
            "current_a": 1.5,
            "battery_remaining_percent": 80,
        }

    return {
        "flight": {},
        "attitude": {},
        "global_position": {},
        "local_position": {},
        "system_health": system_health,
        "battery": {},
    }


def check_status(
    test_name,
    monitor,
    state,
    now,
    expected_status,
    expected_age,
):
    print(f"\n{test_name}")

    result = monitor.evaluate_system_health_freshness(
        state=state,
        now=now,
    )

    assert result["status"] == expected_status, (
        f"Expected {expected_status}, "
        f"got {result['status']}"
    )

    if expected_age is None:
        assert result["age"] is None
    else:
        assert abs(result["age"] - expected_age) < 1e-9

    print(
        f"PASS: status={result['status']}, "
        f"age={result['age']}"
    )

    print(f"Reason: {result['reason']}")


def main():
    print(
        "AirMouse V1 - Health Monitor "
        "System Health Freshness Test"
    )

    fake_vehicle_state = FakeVehicleState(
        make_state()
    )

    monitor = HealthFailSafeMonitor(
        fake_vehicle_state
    )

    now = 100.0

    check_status(
        "TEST 1: Missing system-health telemetry",
        monitor,
        make_state(),
        now,
        monitor.UNKNOWN,
        None,
    )

    check_status(
        "TEST 2: Fresh system-health telemetry",
        monitor,
        make_state(now - 1.0),
        now,
        monitor.HEALTHY,
        1.0,
    )

    check_status(
        "TEST 3: Warning boundary",
        monitor,
        make_state(now - 3.0),
        now,
        monitor.HEALTHY,
        3.0,
    )

    check_status(
        "TEST 4: Stale system-health telemetry",
        monitor,
        make_state(now - 4.0),
        now,
        monitor.WARNING,
        4.0,
    )

    check_status(
        "TEST 5: Critical boundary",
        monitor,
        make_state(now - 6.0),
        now,
        monitor.WARNING,
        6.0,
    )

    check_status(
        "TEST 6: Critically stale system-health telemetry",
        monitor,
        make_state(now - 7.0),
        now,
        monitor.CRITICAL,
        7.0,
    )

    print(
        "\nPASS: Health Monitor system-health "
        "freshness tests completed."
    )


if __name__ == "__main__":
    main()
