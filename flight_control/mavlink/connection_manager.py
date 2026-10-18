from pymavlink import mavutil


class MAVLinkConnectionManager:
    """Manage the lifecycle of an AirMouse MAVLink connection."""

    def __init__(self, connection_string, **connection_options):
        self.connection_string = connection_string
        self.connection_options = connection_options

        self.connection = None
        self.system_id = None
        self.component_id = None

    @property
    def is_connected(self):
        """Return whether a verified MAVLink connection is active."""
        return self.connection is not None

    def connect(self, heartbeat_timeout=10):
        """Open the MAVLink transport and verify it using a heartbeat."""

        if self.connection is not None:
            raise RuntimeError("MAVLink connection is already open.")

        connection = mavutil.mavlink_connection(
            self.connection_string,
            **self.connection_options,
        )

        heartbeat = connection.wait_heartbeat(
            timeout=heartbeat_timeout,
        )

        if heartbeat is None:
            connection.close()

            raise TimeoutError(
                "No MAVLink heartbeat received within "
                f"{heartbeat_timeout} seconds."
            )

        self.connection = connection
        self.system_id = heartbeat.get_srcSystem()
        self.component_id = heartbeat.get_srcComponent()

        return {
            "system_id": self.system_id,
            "component_id": self.component_id,
        }

    def get_connection(self):
        """Return the verified pymavlink connection."""

        if self.connection is None:
            raise RuntimeError(
                "MAVLink connection has not been established."
            )

        return self.connection

    def disconnect(self):
        """Close the MAVLink connection and clear connection state."""

        if self.connection is not None:
            self.connection.close()

        self.connection = None
        self.system_id = None
        self.component_id = None
