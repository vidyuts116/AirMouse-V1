from health_monitor import HealthFailSafeMonitor


class FakeVehicleState:
    """Minimal Vehicle State Manager substitute."""

    def __init__(self, state):
        self.state = state
        self.get_state_calls = 0

    def get_state(self):
        self.get_state_calls += 1
        return self.state


def make_state(
    now,
    heartbeat_age=0.5,
    system_health_age=1.0,
    battery_percent=80,
    sensors_present=0b0111,
    sensors_enabled=0b0111,
    sensors_health=0b0111,
):
    """Create a complete deterministic vehicle-state snapshot."""

    return {
        "flight": {
            "updated_at": now - heartbeat_age,
            "armed": False,
            "flight_mode": "STABILIZE",
        },
        "system_health": {
            "updated_at": now - system_health_age,
            "battery_remaining_percent": battery_percent,
            "sensors_present": sensors_present,
            "sensors_enabled": sensors_enabled,
            "sensors_health": sensors_health,
        },
        "battery": {
            "remaining_percent": battery_percent,
        },
    }


def run_test(
    title,
    state,
    now,
    expected_status,
):
    print(f"\n{title}")

    vehicle_state = FakeVehicleState(state)
    monitor = HealthFailSafeMonitor(vehicle_state)

    result = monitor.evaluate(now=now)

    assert result["overall_status"] == expected_status
    assert result["evaluated_at"] == now

    print(
        f"PASS: overall_status="
        f"{result['overall_status']}"
    )

    for name, check in result["checks"].items():
        print(
            f"  {name}: {check['status']}"
        )

    return result, vehicle_state


print(
    "AirMouse V1 - Health Monitor Overall Assessment Test"
)

NOW = 1000.0


# --------------------------------------------------
# TEST 1
# --------------------------------------------------

state = make_state(NOW)

result, vehicle_state = run_test(
    "TEST 1: All checks healthy",
    state,
    NOW,
    HealthFailSafeMonitor.HEALTHY,
)

assert all(
    check["status"] == HealthFailSafeMonitor.HEALTHY
    for check in result["checks"].values()
)

print("PASS: Every individual check is HEALTHY.")


# --------------------------------------------------
# TEST 2
# --------------------------------------------------

state = make_state(
    NOW,
    battery_percent=25,
)

result, _ = run_test(
    "TEST 2: Battery warning",
    state,
    NOW,
    HealthFailSafeMonitor.WARNING,
)

assert (
    result["checks"]["battery"]["status"]
    == HealthFailSafeMonitor.WARNING
)

print("PASS: Battery WARNING propagated to overall status.")


# --------------------------------------------------
# TEST 3
# --------------------------------------------------

state = make_state(
    NOW,
    sensors_health=0b0101,
)

result, _ = run_test(
    "TEST 3: Critical sensor failure",
    state,
    NOW,
    HealthFailSafeMonitor.CRITICAL,
)

assert (
    result["checks"]["sensors"]["status"]
    == HealthFailSafeMonitor.CRITICAL
)

print("PASS: Sensor CRITICAL propagated to overall status.")


# --------------------------------------------------
# TEST 4
# --------------------------------------------------

state = {
    "flight": {},
    "system_health": {},
    "battery": {},
}

result, _ = run_test(
    "TEST 4: Missing telemetry",
    state,
    NOW,
    HealthFailSafeMonitor.UNKNOWN,
)

assert all(
    check["status"] == HealthFailSafeMonitor.UNKNOWN
    for check in result["checks"].values()
)

print("PASS: Missing telemetry remains UNKNOWN.")


# --------------------------------------------------
# TEST 5
# --------------------------------------------------

state = make_state(
    NOW,
    battery_percent=25,
)

# Remove heartbeat telemetry to introduce UNKNOWN
# while battery remains WARNING.
state["flight"] = {}

result, _ = run_test(
    "TEST 5: WARNING takes precedence over UNKNOWN",
    state,
    NOW,
    HealthFailSafeMonitor.WARNING,
)

assert (
    result["checks"]["heartbeat"]["status"]
    == HealthFailSafeMonitor.UNKNOWN
)

assert (
    result["checks"]["battery"]["status"]
    == HealthFailSafeMonitor.WARNING
)

print("PASS: WARNING correctly outranks UNKNOWN.")


# --------------------------------------------------
# TEST 6
# --------------------------------------------------

state = make_state(
    NOW,
    heartbeat_age=10.0,
    battery_percent=25,
)

# Missing sensor telemetry creates UNKNOWN while:
# heartbeat = CRITICAL
# battery   = WARNING
state["system_health"]["sensors_present"] = None
state["system_health"]["sensors_enabled"] = None
state["system_health"]["sensors_health"] = None

result, _ = run_test(
    "TEST 6: CRITICAL takes highest precedence",
    state,
    NOW,
    HealthFailSafeMonitor.CRITICAL,
)

assert (
    result["checks"]["heartbeat"]["status"]
    == HealthFailSafeMonitor.CRITICAL
)

assert (
    result["checks"]["battery"]["status"]
    == HealthFailSafeMonitor.WARNING
)

assert (
    result["checks"]["sensors"]["status"]
    == HealthFailSafeMonitor.UNKNOWN
)

print(
    "PASS: CRITICAL correctly outranks "
    "WARNING and UNKNOWN."
)


# --------------------------------------------------
# TEST 7
# --------------------------------------------------

state = make_state(NOW)

vehicle_state = FakeVehicleState(state)
monitor = HealthFailSafeMonitor(vehicle_state)

result = monitor.evaluate(now=NOW)

assert vehicle_state.get_state_calls == 1

print("\nTEST 7: Single state snapshot")
print(
    "PASS: evaluate() requested exactly one "
    "Vehicle State snapshot."
)


# --------------------------------------------------
# TEST 8
# --------------------------------------------------

snapshot = monitor.get_health()

snapshot["checks"]["heartbeat"]["status"] = "CORRUPTED"

fresh_snapshot = monitor.get_health()

assert (
    fresh_snapshot["checks"]["heartbeat"]["status"]
    == HealthFailSafeMonitor.HEALTHY
)

print("\nTEST 8: Health snapshot isolation")
print(
    "PASS: External mutation did not alter "
    "stored Health Monitor state."
)


print(
    "\nPASS: Health Monitor overall-assessment "
    "tests completed."
)
