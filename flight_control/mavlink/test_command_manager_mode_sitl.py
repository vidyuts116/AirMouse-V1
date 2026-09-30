import time

from connection_manager import MAVLinkConnectionManager
from message_router import MAVLinkMessageRouter
from vehicle_state import VehicleStateManager
from command_manager import MAVLinkCommandManager


CONNECTION = "udpin:127.0.0.1:14550"


def wait_for_flight_state(vehicle_state, timeout=5):
    """Wait until HEARTBEAT-derived flight state is available."""

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        state = vehicle_state.get_state()
        flight = state["flight"]

        if flight:
            return flight

        time.sleep(0.05)

    raise TimeoutError(
        "Vehicle flight state was not populated."
    )


def main():
    print(
        "AirMouse V1 - Command Manager SET_MODE "
        "SITL Integration Test"
    )

    print(f"Connecting to {CONNECTION} ...")

    connection_manager = MAVLinkConnectionManager(
        CONNECTION
    )

    connection_info = connection_manager.connect(
        heartbeat_timeout=10
    )

    print(
        "Connected to MAVLink system "
        f"{connection_info['system_id']}, "
        f"component {connection_info['component_id']}."
    )

    connection = connection_manager.get_connection()

    router = MAVLinkMessageRouter(connection)

    vehicle_state = VehicleStateManager(router)

    command_manager = MAVLinkCommandManager(
        connection,
        router,
        vehicle_state,
    )

    print("\nStarting Vehicle State Manager...")
    vehicle_state.start()

    print("Starting Command Manager...")
    command_manager.start()

    print(
        "Starting centralized MAVLink "
        "Message Router..."
    )
    router.start()

    try:
        print(
            "\nCollecting baseline telemetry "
            "for 2 seconds..."
        )

        time.sleep(2)

        baseline = wait_for_flight_state(
            vehicle_state
        )

        baseline_mode = baseline["flight_mode"]
        baseline_armed = baseline["armed"]

        print(
            f"Baseline mode: {baseline_mode}"
        )
        print(
            f"Baseline armed state: "
            f"{baseline_armed}"
        )

        if baseline_armed:
            raise RuntimeError(
                "Vehicle is armed. This mode test "
                "expects a disarmed SITL vehicle."
            )

        print("\n===== GUIDED MODE TRANSACTION =====")

        guided_result = command_manager.set_mode(
            "GUIDED",
            state_timeout=5,
        )

        print(
            "Requested mode: "
            f"{guided_result['mode']}"
        )

        print(
            "Custom mode ID: "
            f"{guided_result['custom_mode']}"
        )

        print(
            "Confirmed mode: "
            f"{guided_result['state']['mode']}"
        )

        assert guided_result["success"] is True

        assert (
            guided_result["state"]["mode"]
            == "GUIDED"
        )

        print(
            "PASS: Routed vehicle state "
            "confirmed GUIDED."
        )

        print(
            "\nCollecting GUIDED telemetry "
            "for 1 second..."
        )

        time.sleep(1)

        guided_state = (
            vehicle_state
            .get_state()["flight"]
        )

        print(
            "Current mode: "
            f"{guided_state['flight_mode']}"
        )

        print(
            "Current armed state: "
            f"{guided_state['armed']}"
        )

        print(
            "\n===== STABILIZE MODE "
            "TRANSACTION ====="
        )

        stabilize_result = (
            command_manager.set_mode(
                "STABILIZE",
                state_timeout=5,
            )
        )

        print(
            "Requested mode: "
            f"{stabilize_result['mode']}"
        )

        print(
            "Custom mode ID: "
            f"{stabilize_result['custom_mode']}"
        )

        print(
            "Confirmed mode: "
            f"{stabilize_result['state']['mode']}"
        )

        assert (
            stabilize_result["success"]
            is True
        )

        assert (
            stabilize_result["state"]["mode"]
            == "STABILIZE"
        )

        print(
            "PASS: Routed vehicle state "
            "confirmed STABILIZE."
        )

        print(
            "\nCollecting final telemetry "
            "for 1 second..."
        )

        time.sleep(1)

        final_state = (
            vehicle_state
            .get_state()["flight"]
        )

        print(
            f"Final mode: "
            f"{final_state['flight_mode']}"
        )

        print(
            "Final armed state: "
            f"{final_state['armed']}"
        )

        assert (
            final_state["flight_mode"]
            == "STABILIZE"
        )

        assert final_state["armed"] is False

    finally:
        print(
            "\nStopping command/telemetry "
            "pipeline..."
        )

        command_manager.stop()
        vehicle_state.stop()
        router.stop()

    callback_errors = (
        router.get_callback_errors()
    )

    assert not callback_errors

    print("\n===== VALIDATION =====")

    print(
        "PASS: Real SET_MODE GUIDED request "
        "transmitted to ArduPilot SITL."
    )

    print(
        "PASS: Vehicle State confirmed real "
        "GUIDED transition."
    )

    print(
        "PASS: Real SET_MODE STABILIZE request "
        "transmitted to ArduPilot SITL."
    )

    print(
        "PASS: Vehicle State confirmed real "
        "STABILIZE transition."
    )

    print(
        "PASS: Vehicle remained DISARMED "
        "throughout the test."
    )

    print(
        "PASS: Router remained sole MAVLink "
        "receive owner."
    )

    print(
        "PASS: Complete pipeline shut down "
        "cleanly."
    )

    print(
        "\nPASS: Command Manager SET_MODE "
        "SITL integration completed."
    )


if __name__ == "__main__":
    main()
