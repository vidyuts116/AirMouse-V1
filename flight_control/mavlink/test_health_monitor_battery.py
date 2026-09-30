from health_monitor import HealthFailSafeMonitor


class FakeVehicleState:
    """Minimal Vehicle State Manager substitute for deterministic tests."""

    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state


def make_state(
    battery_percent=None,
    system_health_percent=None,
):
    """Create a minimal vehicle-state snapshot."""

    battery = {}
    system_health = {}

    if battery_percent is not None:
        battery["remaining_percent"] = battery_percent

    if system_health_percent is not None:
        system_health[
            "battery_remaining_percent"
        ] = system_health_percent

    return {
        "flight": {},
        "attitude": {},
        "global_position": {},
        "local_position": {},
        "system_health": system_health,
        "battery": battery,
    }


def check_battery(
    test_name,
    monitor,
    state,
    expected_status,
    expected_percent,
    expected_source,
):
    print(f"\n{test_name}")

    result = monitor.evaluate_battery_level(
        state=state
    )

    assert result["status"] == expected_status, (
        f"Expected status {expected_status}, "
        f"got {result['status']}"
    )

    assert (
        result["remaining_percent"]
        == expected_percent
    ), (
        f"Expected percentage {expected_percent}, "
        f"got {result['remaining_percent']}"
    )

    assert result["source"] == expected_source, (
        f"Expected source {expected_source}, "
        f"got {result['source']}"
    )

    print(
        f"PASS: status={result['status']}, "
        f"remaining={result['remaining_percent']}, "
        f"source={result['source']}"
    )

    print(f"Reason: {result['reason']}")


def main():
    print(
        "AirMouse V1 - Health Monitor "
        "Battery Level Test"
    )

    fake_vehicle_state = FakeVehicleState(
        make_state()
    )

    monitor = HealthFailSafeMonitor(
        fake_vehicle_state
    )

    check_battery(
        "TEST 1: Healthy battery",
        monitor,
        make_state(battery_percent=80),
        monitor.HEALTHY,
        80,
        "BATTERY_STATUS",
    )

    check_battery(
        "TEST 2: Warning boundary",
        monitor,
        make_state(battery_percent=30),
        monitor.WARNING,
        30,
        "BATTERY_STATUS",
    )

    check_battery(
        "TEST 3: Critical boundary",
        monitor,
        make_state(battery_percent=20),
        monitor.CRITICAL,
        20,
        "BATTERY_STATUS",
    )

    check_battery(
        "TEST 4: Very low battery",
        monitor,
        make_state(battery_percent=5),
        monitor.CRITICAL,
        5,
        "BATTERY_STATUS",
    )

    check_battery(
        "TEST 5: Battery percentage unavailable",
        monitor,
        make_state(),
        monitor.UNKNOWN,
        None,
        None,
    )

    check_battery(
        "TEST 6: SYS_STATUS fallback",
        monitor,
        make_state(
            system_health_percent=55,
        ),
        monitor.HEALTHY,
        55,
        "SYS_STATUS",
    )

    check_battery(
        "TEST 7: BATTERY_STATUS has priority",
        monitor,
        make_state(
            battery_percent=25,
            system_health_percent=80,
        ),
        monitor.WARNING,
        25,
        "BATTERY_STATUS",
    )

    print(
        "\nPASS: Health Monitor battery-level "
        "tests completed."
    )


if __name__ == "__main__":
    main()
