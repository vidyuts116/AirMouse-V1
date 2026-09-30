from health_monitor import HealthFailSafeMonitor


class FakeVehicleState:
    """Minimal Vehicle State Manager substitute."""

    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state


def make_state(present=None, enabled=None, health=None):
    """Create minimal system-health state."""

    system_health = {}

    if present is not None:
        system_health["sensors_present"] = present

    if enabled is not None:
        system_health["sensors_enabled"] = enabled

    if health is not None:
        system_health["sensors_health"] = health

    return {
        "system_health": system_health,
    }


def run_test(name, state, expected_status,
             expected_required=None,
             expected_unhealthy=None):

    monitor = HealthFailSafeMonitor(
        FakeVehicleState(state)
    )

    result = monitor.evaluate_sensor_health()

    assert result["status"] == expected_status

    if expected_required is not None:
        assert result["required_mask"] == expected_required

    if expected_unhealthy is not None:
        assert result["unhealthy_mask"] == expected_unhealthy

    print(
        f"PASS: status={result['status']}, "
        f"required_mask={result['required_mask']}, "
        f"unhealthy_mask={result['unhealthy_mask']}"
    )

    print(f"Reason: {result['reason']}")


print(
    "AirMouse V1 - Health Monitor Sensor Health Test"
)


print("\nTEST 1: Missing sensor-health telemetry")

run_test(
    "missing",
    make_state(),
    HealthFailSafeMonitor.UNKNOWN,
)


print("\nTEST 2: All required sensors healthy")

# Bits:
# present = 1111
# enabled = 0111
# health  = 0111
#
# required = present & enabled = 0111
# unhealthy = 0000

run_test(
    "healthy",
    make_state(
        present=0b1111,
        enabled=0b0111,
        health=0b0111,
    ),
    HealthFailSafeMonitor.HEALTHY,
    expected_required=0b0111,
    expected_unhealthy=0,
)


print("\nTEST 3: Required sensor unhealthy")

# required = 0111
# health   = 0101
#
# Bit 1 is required but unhealthy.
# unhealthy = 0010

run_test(
    "unhealthy",
    make_state(
        present=0b1111,
        enabled=0b0111,
        health=0b0101,
    ),
    HealthFailSafeMonitor.CRITICAL,
    expected_required=0b0111,
    expected_unhealthy=0b0010,
)


print("\nTEST 4: Disabled unhealthy sensor ignored")

# Sensor bit 3 exists but is disabled.
#
# present  = 1111
# enabled  = 0111
# health   = 0111
#
# Bit 3 not being healthy must not cause failure.

run_test(
    "disabled",
    make_state(
        present=0b1111,
        enabled=0b0111,
        health=0b0111,
    ),
    HealthFailSafeMonitor.HEALTHY,
    expected_required=0b0111,
    expected_unhealthy=0,
)


print("\nTEST 5: Extra health bits harmless")

# Health can contain bits outside our required mask.
# Those must not create a false failure.

run_test(
    "extra",
    make_state(
        present=0b0011,
        enabled=0b0011,
        health=0b1111,
    ),
    HealthFailSafeMonitor.HEALTHY,
    expected_required=0b0011,
    expected_unhealthy=0,
)


print(
    "\nPASS: Health Monitor sensor-health tests completed."
)
