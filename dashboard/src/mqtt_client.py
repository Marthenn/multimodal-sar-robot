import json
import time
from PySide6.QtCore import QThread, Signal
import paho.mqtt.client as mqtt


class MQTTClient(QThread):
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self, broker_host="vlg2.local", broker_port=1883, topic="sar-robot/sound"
    ):
        super().__init__()
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.client = None
        self.is_running = True

    def run(self):
        try:
            # Create a new client instance
            self.client = mqtt.Client()

            # Set up callbacks
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

            # Connect to broker
            self.error_occurred.emit(
                f"Attempting to connect to {self.broker_host}:{self.broker_port}"
            )
            self.client.connect(self.broker_host, self.broker_port, 60)

            # Start the loop
            self.client.loop_start()

            # Keep the thread running
            while self.is_running:
                time.sleep(0.1)  # Reduce CPU usage while keeping thread responsive

        except Exception as e:
            self.error_occurred.emit(f"MQTT Error: {str(e)}")
        finally:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()

    def stop(self):
        """Stop the MQTT client thread."""
        self.is_running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self.wait()

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            self.error_occurred.emit("Successfully connected to broker")
            self.connected.emit()
            # Subscribe to topic
            self.client.subscribe(self.topic)
            self.error_occurred.emit(f"Subscribed to topic: {self.topic}")
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized",
            }
            error_msg = error_messages.get(rc, f"Connection failed with code {rc}")
            self.error_occurred.emit(error_msg)

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        self.disconnected.emit()
        if rc != 0:
            self.error_occurred.emit(f"Unexpected disconnection (code {rc})")

    def _on_message(self, client, userdata, msg):
        """Callback when message is received."""
        try:
            payload = json.loads(msg.payload.decode())
            self.message_received.emit(payload)
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid JSON received: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"Error processing message: {str(e)}")

    def publish(self, topic, message):
        """Publish a message to a topic."""
        if self.client:
            try:
                result = self.client.publish(topic, message)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    return True
                else:
                    self.error_occurred.emit(f"Publish failed with code {result.rc}")
                    return False
            except Exception as e:
                self.error_occurred.emit(f"Error publishing message: {str(e)}")
                return False
        else:
            self.error_occurred.emit("Cannot publish: Client not initialized")
            return False
