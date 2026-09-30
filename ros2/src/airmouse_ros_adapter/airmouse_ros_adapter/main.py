"""Executable composition entry point for AirMouse ROS 2."""

import rclpy
from rclpy.node import Node

from .runtime import AirMouseRuntime


class RuntimeConfigurationNode(Node):
    """Read AirMouse runtime configuration from ROS parameters."""

    def __init__(self):
        super().__init__("airmouse_runtime_configuration")

        self.declare_parameter("connection_string", "")
        self.declare_parameter("heartbeat_timeout", 10.0)
        self.declare_parameter("vehicle_namespace", "/airmouse")
        self.declare_parameter("publish_rate_hz", 10.0)

    def read_configuration(self):
        connection_string = (
            self.get_parameter("connection_string")
            .get_parameter_value()
            .string_value
            .strip()
        )

        heartbeat_timeout = (
            self.get_parameter("heartbeat_timeout")
            .get_parameter_value()
            .double_value
        )

        namespace = (
            self.get_parameter("vehicle_namespace")
            .get_parameter_value()
            .string_value
            .strip()
        )

        publish_rate_hz = (
            self.get_parameter("publish_rate_hz")
            .get_parameter_value()
            .double_value
        )

        if not connection_string:
            raise ValueError(
                "ROS parameter 'connection_string' is required. "
                "No MAVLink transport endpoint will be guessed."
            )

        if heartbeat_timeout <= 0:
            raise ValueError(
                "heartbeat_timeout must be greater than zero."
            )

        if publish_rate_hz <= 0:
            raise ValueError(
                "publish_rate_hz must be greater than zero."
            )

        if not namespace:
            namespace = "/airmouse"

        return {
            "connection_string": connection_string,
            "heartbeat_timeout": heartbeat_timeout,
            "namespace": namespace,
            "publish_rate_hz": publish_rate_hz,
        }


def main(args=None):
    """Start the complete AirMouse flight-control/ROS runtime."""

    rclpy.init(args=args)

    config_node = None
    runtime = None

    try:
        config_node = RuntimeConfigurationNode()
        config = config_node.read_configuration()

        config_node.get_logger().info(
            "Starting AirMouse runtime."
        )
        config_node.get_logger().info(
            f"Vehicle namespace: {config['namespace']}"
        )
        config_node.get_logger().info(
            f"Publish rate: {config['publish_rate_hz']} Hz"
        )

        runtime = AirMouseRuntime(
            connection_string=config["connection_string"],
            namespace=config["namespace"],
            publish_rate_hz=config["publish_rate_hz"],
        )

        connection_info = runtime.start(
            heartbeat_timeout=config["heartbeat_timeout"]
        )

        config_node.get_logger().info(
            "MAVLink connection verified: "
            f"system {connection_info['system_id']}, "
            f"component {connection_info['component_id']}."
        )

        config_node.destroy_node()
        config_node = None

        rclpy.spin(runtime.adapter)

    except KeyboardInterrupt:
        pass

    except Exception as exc:
        if config_node is not None:
            config_node.get_logger().error(
                f"AirMouse runtime failed: "
                f"{type(exc).__name__}: {exc}"
            )
        else:
            print(
                "AirMouse runtime failed: "
                f"{type(exc).__name__}: {exc}"
            )

        raise

    finally:
        if runtime is not None:
            runtime.stop()

        if config_node is not None:
            try:
                config_node.destroy_node()
            except Exception:
                pass

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
