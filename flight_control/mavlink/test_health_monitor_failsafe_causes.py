from health_monitor import HealthFailSafeMonitor


class FakeVehicleState:
    """Minimal Vehicle State Manager substitute."""

    def get_state(self):
        return {}


monitor = HealthFailSafeMonitor(FakeVehicleState())


def make_check(status, reason):
    return {
        "status": status,
        "reason": reason,
    }


def cause_names(result):
    return [
        cause["check"]
        for cause in result["causes"]
    ]


print(
    "AirMouse V1 - Health Monitor "
    "Fail-Safe Cause Selection Test"
)


print("\nTEST 1: HEALTHY has no failure causes")

health = {
    "overall_status": monitor.HEALTHY,
    "checks": {
        "heartbeat": make_check(
            monitor.HEALTHY,
            "Heartbeat telemetry is fresh.",
        ),
        "battery": make_check(
            monitor.HEALTHY,
            "Battery level is healthy.",
        ),
    },
}

result = monitor.determine_failsafe_decision(health)

assert result["decision"] == monitor.CONTINUE
assert result["causes"] == []

print(
    "PASS: HEALTHY -> CONTINUE with no causes."
)


print("\nTEST 2: WARNING selects only warning causes")

health = {
    "overall_status": monitor.WARNING,
    "checks": {
        "heartbeat": make_check(
            monitor.HEALTHY,
            "Heartbeat telemetry is fresh.",
        ),
        "battery": make_check(
            monitor.WARNING,
            "Battery level is low.",
        ),
        "sensors": make_check(
            monitor.UNKNOWN,
            "Sensor-health telemetry is unavailable.",
        ),
    },
}

result = monitor.determine_failsafe_decision(health)

assert result["decision"] == monitor.CAUTION
assert cause_names(result) == ["battery"]

cause = result["causes"][0]

assert cause["status"] == monitor.WARNING
assert cause["reason"] == "Battery level is low."

print(
    "PASS: WARNING -> CAUTION selected only "
    "the WARNING battery cause."
)


print("\nTEST 3: UNKNOWN selects only unknown causes")

health = {
    "overall_status": monitor.UNKNOWN,
    "checks": {
        "heartbeat": make_check(
            monitor.UNKNOWN,
            "No heartbeat telemetry available.",
        ),
        "system_health": make_check(
            monitor.UNKNOWN,
            "No system-health telemetry available.",
        ),
        "battery": make_check(
            monitor.HEALTHY,
            "Battery level is healthy.",
        ),
    },
}

result = monitor.determine_failsafe_decision(health)

assert result["decision"] == monitor.HOLD

assert cause_names(result) == [
    "heartbeat",
    "system_health",
]

print(
    "PASS: UNKNOWN -> HOLD selected all and only "
    "UNKNOWN causes."
)


print("\nTEST 4: CRITICAL ignores lower-severity causes")

health = {
    "overall_status": monitor.CRITICAL,
    "checks": {
        "heartbeat": make_check(
            monitor.CRITICAL,
            "Heartbeat telemetry is critically stale.",
        ),
        "battery": make_check(
            monitor.WARNING,
            "Battery level is low.",
        ),
        "sensors": make_check(
            monitor.UNKNOWN,
            "Sensor-health telemetry is unavailable.",
        ),
    },
}

result = monitor.determine_failsafe_decision(health)

assert result["decision"] == monitor.FAILSAFE
assert cause_names(result) == ["heartbeat"]

print(
    "PASS: CRITICAL -> FAILSAFE selected only "
    "the CRITICAL cause."
)


print("\nTEST 5: Multiple critical causes")

health = {
    "overall_status": monitor.CRITICAL,
    "checks": {
        "heartbeat": make_check(
            monitor.CRITICAL,
            "Heartbeat telemetry is critically stale.",
        ),
        "battery": make_check(
            monitor.CRITICAL,
            "Battery level is critically low.",
        ),
        "sensors": make_check(
            monitor.CRITICAL,
            "Required sensor unhealthy.",
        ),
        "system_health": make_check(
            monitor.WARNING,
            "System-health telemetry is stale.",
        ),
    },
}

result = monitor.determine_failsafe_decision(health)

assert result["decision"] == monitor.FAILSAFE

assert cause_names(result) == [
    "heartbeat",
    "battery",
    "sensors",
]

print(
    "PASS: All CRITICAL causes were preserved."
)

for cause in result["causes"]:
    print(
        f"  {cause['check']}: "
        f"{cause['status']} - "
        f"{cause['reason']}"
    )


print("\nTEST 6: Cause objects are complete")

for cause in result["causes"]:
    assert set(cause.keys()) == {
        "check",
        "status",
        "reason",
    }

print(
    "PASS: Every cause contains check, status, "
    "and reason."
)


print(
    "\nPASS: Health Monitor fail-safe "
    "cause-selection tests completed."
)
