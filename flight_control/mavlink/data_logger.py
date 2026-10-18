"""Asynchronous routed MAVLink data logger for AirMouse V1.

The logger is deliberately transport-independent. It receives MAVLink
messages only through MAVLinkMessageRouter subscriptions and never owns
or reads directly from a MAVLink connection.
"""

import json
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class MAVLinkDataLogger:
    """Persist routed MAVLink telemetry without blocking the router."""

    DEFAULT_MESSAGE_TYPES = (
        "HEARTBEAT",
        "ATTITUDE",
        "GLOBAL_POSITION_INT",
        "LOCAL_POSITION_NED",
        "SYS_STATUS",
        "BATTERY_STATUS",
        "COMMAND_ACK",
    )

    def __init__(
        self,
        router,
        log_path,
        *,
        message_types=None,
        queue_size=4096,
    ):
        if router is None:
            raise ValueError(
                "A MAVLink message router is required."
            )

        if not log_path:
            raise ValueError(
                "A log path is required."
            )

        if queue_size <= 0:
            raise ValueError(
                "queue_size must be greater than zero."
            )

        self.router = router
        self.log_path = Path(log_path)

        selected_types = (
            message_types
            if message_types is not None
            else self.DEFAULT_MESSAGE_TYPES
        )

        self.message_types = tuple(
            message_type.upper()
            for message_type in selected_types
        )

        self._queue = queue.Queue(maxsize=queue_size)

        self._started = False
        self._writer_thread = None
        self._stop_event = threading.Event()

        # Logger lifecycle and writer health are deliberately separate.
        # A failed storage writer must never masquerade as healthy, but
        # subscriptions remain lifecycle-owned until stop() removes them.
        self._health_lock = threading.Lock()
        self._failed = False
        self._last_error = None

        self._statistics_lock = threading.Lock()

        self._statistics = {
            "received": 0,
            "written": 0,
            "dropped": 0,
            "write_errors": 0,
        }

    @property
    def is_started(self):
        """Return whether logger subscriptions and writer are active."""

        return self._started

    @property
    def is_writer_alive(self):
        """Return whether the background persistence worker is alive."""

        thread = self._writer_thread

        return (
            thread is not None
            and thread.is_alive()
        )

    @property
    def has_failed(self):
        """Return whether the persistence worker hit a fatal failure."""

        with self._health_lock:
            return self._failed

    @property
    def last_error(self):
        """Return the latest fatal persistence error, if any."""

        with self._health_lock:
            return self._last_error

    def start(self):
        """Start logging routed MAVLink messages."""

        if self._started:
            raise RuntimeError(
                "MAVLink Data Logger is already started."
            )

        self.log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._stop_event.clear()

        with self._health_lock:
            self._failed = False
            self._last_error = None

        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="airmouse-data-logger",
            daemon=True,
        )

        for message_type in self.message_types:
            self.router.subscribe(
                message_type,
                self._handle_message,
            )

        self._started = True

        try:
            self._writer_thread.start()

        except Exception:
            for message_type in self.message_types:
                self.router.unsubscribe(
                    message_type,
                    self._handle_message,
                )

            self._writer_thread = None
            self._started = False
            raise

    def stop(self, join_timeout=5):
        """Stop accepting records and flush queued records."""

        if not self._started:
            return

        for message_type in self.message_types:
            self.router.unsubscribe(
                message_type,
                self._handle_message,
            )

        self._started = False
        self._stop_event.set()

        if self._writer_thread is not None:
            self._writer_thread.join(
                timeout=join_timeout,
            )

            if self._writer_thread.is_alive():
                raise TimeoutError(
                    "MAVLink Data Logger did not stop cleanly."
                )

        self._writer_thread = None

    def get_statistics(self):
        """Return a thread-safe snapshot of logger statistics."""

        with self._statistics_lock:
            return self._statistics.copy()

    def _increment_statistic(self, name):
        """Increment one logger statistic safely."""

        with self._statistics_lock:
            self._statistics[name] += 1

    def _handle_message(self, message):
        """Queue one routed MAVLink message without blocking."""

        self._increment_statistic("received")

        try:
            payload = message.to_dict()

        except Exception:
            payload = {
                "message_type": message.get_type(),
                "representation": str(message),
            }

        record = {
            "timestamp_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "monotonic_s": time.monotonic(),
            "message_type": message.get_type(),
            "data": payload,
        }

        try:
            self._queue.put_nowait(record)

        except queue.Full:
            self._increment_statistic("dropped")

    def _writer_loop(self):
        """Write queued records until shutdown and queue drain."""

        try:
            with self.log_path.open(
                "a",
                encoding="utf-8",
            ) as log_file:

                while (
                    not self._stop_event.is_set()
                    or not self._queue.empty()
                ):
                    try:
                        record = self._queue.get(
                            timeout=0.2,
                        )

                    except queue.Empty:
                        continue

                    try:
                        json.dump(
                            record,
                            log_file,
                            separators=(",", ":"),
                            default=str,
                        )

                        log_file.write("\n")
                        log_file.flush()

                        self._increment_statistic(
                            "written"
                        )

                    except Exception:
                        self._increment_statistic(
                            "write_errors"
                        )

                    finally:
                        self._queue.task_done()

        except Exception as error:
            self._increment_statistic(
                "write_errors"
            )

            with self._health_lock:
                self._failed = True
                self._last_error = (
                    f"{type(error).__name__}: {error}"
                )
