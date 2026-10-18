import threading


class MAVLinkMessageRouter:
    """Centralized MAVLink message dispatcher for AirMouse V1."""

    def __init__(self, connection):
        if connection is None:
            raise ValueError("A valid MAVLink connection is required.")

        self.connection = connection
        self._subscribers = {}
        self._subscriber_lock = threading.Lock()

        self._running = False
        self._receiver_thread = None
        self._callback_errors = []

    def subscribe(self, message_type, callback):
        """Subscribe a callback to a MAVLink message type."""

        if not isinstance(message_type, str) or not message_type.strip():
            raise ValueError("message_type must be a non-empty string.")

        if not callable(callback):
            raise TypeError("callback must be callable.")

        normalized_type = message_type.upper()

        with self._subscriber_lock:
            callbacks = self._subscribers.setdefault(
                normalized_type,
                [],
            )

            if callback not in callbacks:
                callbacks.append(callback)

    def unsubscribe(self, message_type, callback):
        """Remove a callback from a MAVLink message type."""

        normalized_type = message_type.upper()

        with self._subscriber_lock:
            callbacks = self._subscribers.get(normalized_type)

            if not callbacks:
                return False

            try:
                callbacks.remove(callback)

            except ValueError:
                return False

            if not callbacks:
                del self._subscribers[normalized_type]

            return True

    def get_callback_errors(self):
        """Return a snapshot of recorded subscriber callback errors."""

        return list(self._callback_errors)

    @property
    def is_running(self):
        """Return whether the continuous receiver is running."""
        return self._running

    def start(self):
        """Start the centralized MAVLink receive loop."""

        if self._running:
            raise RuntimeError("MAVLink message router is already running.")

        self._running = True

        self._receiver_thread = threading.Thread(
            target=self._receive_loop,
            name="airmouse-mavlink-router",
            daemon=True,
        )

        self._receiver_thread.start()

    def stop(self, join_timeout=2):
        """Stop the centralized MAVLink receive loop."""

        self._running = False

        if self._receiver_thread is not None:
            self._receiver_thread.join(timeout=join_timeout)

            if self._receiver_thread.is_alive():
                raise TimeoutError(
                    "MAVLink message router did not stop cleanly."
                )

        self._receiver_thread = None

    def _receive_loop(self):
        """Continuously receive and dispatch MAVLink messages."""

        try:
            while self._running:
                self.receive_once(timeout=0.2)

        finally:
            self._running = False

    def receive_once(self, timeout=1):
        """Receive and dispatch one MAVLink message."""

        message = self.connection.recv_match(
            blocking=True,
            timeout=timeout,
        )

        if message is None:
            return None

        self.dispatch(message)

        return message

    def dispatch(self, message):
        """Dispatch one MAVLink message to its registered subscribers."""

        if message is None:
            return 0

        message_type = message.get_type()

        with self._subscriber_lock:
            callbacks = list(
                self._subscribers.get(message_type, [])
            )

        successful_deliveries = 0

        for callback in callbacks:
            try:
                callback(message)

            except Exception as error:
                self._callback_errors.append({
                    "message_type": message_type,
                    "callback": callback,
                    "error": error,
                })

            else:
                successful_deliveries += 1

        return successful_deliveries
