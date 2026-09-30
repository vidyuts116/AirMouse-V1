from health_monitor import HealthFailSafeMonitor


class FakeVehicleState:
    """Minimal Vehicle State Manager substitute."""

    def get_state(self):
        return {}


monitor = HealthFailSafeMonitor(FakeVehicleState())


def test_mapping(health_status, expected_decision):
    result = monitor.determine_failsafe_decision(
        {
            "overall_status": health_status,
            "checks": {},
            "evaluated_at": 1000.0,
        }
    )

    assert result["health_status"] == health_status
    assert result["decision"] == expected_decision

    print(
        f"PASS: {health_status} -> "
        f"{result['decision']}"
    )


print(
    "AirMouse V1 - Health Monitor Fail-Safe Decision Test"
)


print("\nTEST 1: HEALTHY decision")

test_mapping(
    HealthFailSafeMonitor.HEALTHY,
    HealthFailSafeMonitor.CONTINUE,
)


print("\nTEST 2: WARNING decision")

test_mapping(
    HealthFailSafeMonitor.WARNING,
    HealthFailSafeMonitor.CAUTION,
)


print("\nTEST 3: UNKNOWN decision")

test_mapping(
    HealthFailSafeMonitor.UNKNOWN,
    HealthFailSafeMonitor.HOLD,
)


print("\nTEST 4: CRITICAL decision")

test_mapping(
    HealthFailSafeMonitor.CRITICAL,
    HealthFailSafeMonitor.FAILSAFE,
)


print("\nTEST 5: Invalid health status")

try:
    monitor.determine_failsafe_decision(
        {
            "overall_status": "NOT_A_REAL_STATUS",
            "checks": {},
            "evaluated_at": 1000.0,
        }
    )

except ValueError as exc:
    print(f"PASS: Invalid status rejected: {exc}")

else:
    raise AssertionError(
        "Invalid health status was not rejected."
    )


print("\nTEST 6: Use stored health assessment")

monitor._health = {
    "overall_status": HealthFailSafeMonitor.WARNING,
    "checks": {},
    "evaluated_at": 1000.0,
}

result = monitor.determine_failsafe_decision()

assert (
    result["health_status"]
    == HealthFailSafeMonitor.WARNING
)

assert (
    result["decision"]
    == HealthFailSafeMonitor.CAUTION
)

print(
    "PASS: Stored WARNING assessment produced "
    "CAUTION decision."
)


print(
    "\nPASS: Health Monitor fail-safe decision "
    "tests completed."
)
