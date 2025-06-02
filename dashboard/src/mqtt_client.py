import json
from PySide6.QtCore import QThread, Signal
import paho.mqtt.client as mqtt


class MQTTClient(QThread):
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self, broker_host="localhost", broker_port=1883, topic="sar-robot/sound"
    ):
        super().__init__()
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.client = None
        self.is_running = True

    def run(self):
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

            self.client.connect(self.broker_host, self.broker_port, 60)

            # Start the MQTT network loop
            while self.is_running:
                self.client.loop(timeout=1.0)  # Process MQTT messages with timeout

        except Exception as e:
            self.error_occurred.emit(f"MQTT Error: {str(e)}")

    def stop(self):
        """Stop the MQTT client thread."""
        self.is_running = False
        if self.client:
            self.client.disconnect()
        self.wait()

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            self.connected.emit()
            self.client.subscribe(self.topic)
        else:
            self.error_occurred.emit(f"Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        self.disconnected.emit()

    def _on_message(self, client, userdata, msg):
        """Callback when message is received."""
        try:
            payload = json.loads(msg.payload.decode())
            self.message_received.emit(payload)
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid JSON received: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"Error processing message: {str(e)}")
