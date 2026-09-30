"""Configuration helpers for standalone AirMouse MAVLink monitors.

These diagnostic utilities intentionally receive their transport
configuration externally. No SITL or physical-flight-controller
endpoint is hard-coded here.
"""

import argparse


def parse_monitor_connection(description):
    """Return the externally supplied MAVLink connection string."""

    parser = argparse.ArgumentParser(
        description=description,
    )

    parser.add_argument(
        "--connection",
        required=True,
        help=(
            "MAVLink connection string. Examples include a SITL UDP "
            "endpoint or an appropriate physical flight-controller "
            "serial/USB transport."
        ),
    )

    args = parser.parse_args()

    connection = args.connection.strip()

    if not connection:
        parser.error("--connection must not be empty.")

    return connection
