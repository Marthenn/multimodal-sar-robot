import sys
import asyncio
import websockets
import cv2
import numpy as np
import json
import time
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QGridLayout,
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal, Slot

from .radar_widget import RadarWidget
from .mqtt_client import MQTTClient
from .map_widget import MapWidget

# --- Configuration ---
# Use the URI from your WSVideoClient script
WEBSOCKET_VIDEO_URI = "ws://vlg2.local:9002"
WEBSOCKET_AUDIO_URI = "ws://vlg2.local:8765"
MQTT_BROKER_HOST = "vlg2.local"  # Update this to your Raspberry Pi's IP
MQTT_BROKER_PORT = 1883
MQTT_SOUND_TOPIC = "sar-robot/sound"
MQTT_MOVEMENT_TOPIC = "sar-robot/movement"
MQTT_POSITION_TOPIC = "sar-robot/position"
RADAR_RESET_TIMEOUT = 5000  # 5 seconds in milliseconds

class AudioWebSocketClientThread(QThread):
    connection_status = Signal(str)
    log_message = Signal(str)

    def __init__(self, uri, sample_rate=16000, channels=1):
        super().__init__()
        self.uri = uri
        self.running = True
        self.websocket = None
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_stream = None

    def run(self):
        asyncio.run(self._run_ws())

    async def _run_ws(self):
        try:
            self.connection_status.emit("Connecting to audio...")
            async with websockets.connect(self.uri, max_size=None) as ws:
                self.websocket = ws
                self.connection_status.emit("Audio Connected")
                self.log_message.emit("Audio WebSocket connection established.")

                # Initialize sounddevice for audio output
                try:
                    import sounddevice as sd

                    device_info = sd.query_devices(kind='output')
                    self.log_message.emit(f"Using audio device: {device_info['name']}")
                    device_rate = int(device_info['default_samplerate'])
                    self.log_message.emit(f"Default sample rate: {device_rate}")

                    # Create output stream
                    self.audio_stream = sd.OutputStream(
                        samplerate=device_rate,
                        channels=self.channels,
                        dtype='float32'
                    )
                    self.audio_stream.start()

                    import resampy
                    need_resample = device_rate != self.sample_rate

                except ImportError:
                    self.log_message.emit("Sounddevice or resampy not installed. Run: pip install sounddevice resampy")
                    return
                except Exception as e:
                    self.log_message.emit(f"Error initializing audio: {e}")
                    return

                while self.running:
                    try:
                        data = await ws.recv()
                        # Process audio data
                        audio_data = np.frombuffer(data, dtype=np.float32)

                        if need_resample:
                            audio_data = resampy.resample(
                                audio_data,
                                self.sample_rate,
                                device_rate
                            )

                        # Play audio
                        try:
                            # Write directly to stream for lower latency
                            self.audio_stream.write(audio_data)
                        except Exception as e:
                            self.log_message.emit(f"Error playing audio: {e}")

                    except websockets.ConnectionClosed:
                        self.connection_status.emit("Audio Disconnected")
                        self.log_message.emit("Audio WebSocket connection closed.")
                        break
                    except Exception as e:
                        self.log_message.emit(f"Error processing audio data: {e}")
        except Exception as e:
            self.connection_status.emit("Audio Connection Error")
            self.log_message.emit(f"Audio WebSocket error: {e}")
        finally:
            self._cleanup_audio()

    def _cleanup_audio(self):
        """Clean up audio resources"""
        if self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
            except Exception as e:
                self.log_message.emit(f"Error closing audio stream: {e}")

    def stop(self):
        """Stop the thread and clean up resources"""
        self.running = False

# --- WebSocket Communication Thread ---
class WebSocketClientThread(QThread):
    connection_status = Signal(str)
    image_received = Signal(QPixmap)
    map_data_received = Signal(object)
    log_message = Signal(str)

    def __init__(self, uri):
        super().__init__()
        self.uri = uri
        self.running = True
        self.websocket = None

    def run(self):
        asyncio.run(self._run_ws())

    async def _run_ws(self):
        try:
            self.connection_status.emit("Connecting...")
            async with websockets.connect(self.uri, max_size=None) as ws:
                self.websocket = ws
                self.connection_status.emit("Connected")
                self.log_message.emit("WebSocket connection established.")
                while self.running:
                    try:
                        data = await ws.recv()
                        np_arr = np.frombuffer(data, np.uint8)
                        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                        if img is not None:
                            height, width, channel = img.shape
                            bytes_per_line = 3 * width
                            q_img = QImage(
                                img.data,
                                width,
                                height,
                                bytes_per_line,
                                QImage.Format.Format_BGR888,
                            )
                            pixmap = QPixmap.fromImage(q_img)
                            self.image_received.emit(pixmap)
                    except websockets.ConnectionClosed:
                        self.connection_status.emit("Disconnected")
                        self.log_message.emit("WebSocket connection closed.")
                        break
        except Exception as e:
            self.connection_status.emit("Connection Error")
            self.log_message.emit(f"WebSocket error: {e}")

    def send_command(self, command):
        async def _send():
            try:
                if self.websocket and self.websocket.open:
                    msg = {"type": "command", "value": command}
                    await self.websocket.send(json.dumps(msg))
                else:
                    self.log_message.emit("WebSocket not connected.")
            except Exception as e:
                self.log_message.emit(f"Error sending command: {e}")

        asyncio.run(_send())

    def stop(self):
        self.running = False


# --- Main GUI Window ---
class RobotControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multimodal SAR Robot Control")
        self.setGeometry(100, 100, 800, 600)  # x, y, width, height

        # --- Central Widget and Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)  # Horizontal split

        # --- Left Panel: Controls ---
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(250)  # Increase width to accommodate buttons better

        # Movement Controls Container
        movement_container = QWidget()
        movement_layout = QVBoxLayout(movement_container)
        movement_layout.setContentsMargins(0, 0, 0, 0)

        # Add title for movement controls
        movement_title = QLabel("Movement Controls:")
        movement_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        movement_layout.addWidget(movement_title)

        # Movement Buttons
        move_buttons_layout = QGridLayout()
        move_buttons_layout.setSpacing(20)  # Increase spacing further
        move_buttons_layout.setContentsMargins(10, 10, 10, 10)

        # Create buttons with consistent size and better text layout
        button_style = """
            QPushButton {
                min-width: 70px;
                max-width: 70px;
                min-height: 60px;
                max-height: 60px;
                padding: 8px;
                font-size: 11px;
                margin: 3px;
                border: 1px solid #999;
                border-radius: 4px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """

        self.btn_forward = QPushButton("Forward\n(W)")
        self.btn_left = QPushButton("Left\n(A)")
        self.btn_stop = QPushButton("Stop\n(S)")
        self.btn_right = QPushButton("Right\n(D)")
        self.btn_backward = QPushButton("Backward\n(X)")

        # Apply style to all buttons
        for btn in [
            self.btn_forward,
            self.btn_left,
            self.btn_stop,
            self.btn_right,
            self.btn_backward,
        ]:
            btn.setStyleSheet(button_style)

        # Create a container widget for the button grid to center it
        buttons_container = QWidget()
        buttons_container.setLayout(move_buttons_layout)

        # Arrange buttons with more space
        move_buttons_layout.addWidget(self.btn_forward, 0, 1)
        move_buttons_layout.addWidget(self.btn_left, 1, 0)
        move_buttons_layout.addWidget(self.btn_stop, 1, 1)
        move_buttons_layout.addWidget(self.btn_right, 1, 2)
        move_buttons_layout.addWidget(self.btn_backward, 2, 1)

        # Add the buttons container to the movement layout
        movement_layout.addWidget(buttons_container)

        # Add movement container to control layout
        control_layout.addWidget(movement_container)

        # Add expanding spacer between movement controls and log
        control_layout.addStretch(1)

        # Log section
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)

        # Log title
        log_title = QLabel("Log:")
        log_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        log_layout.addWidget(log_title)

        # Log display
        self.log_label = QLabel("Log messages will appear here.")
        self.log_label.setWordWrap(True)
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.log_label.setMinimumHeight(150)  # Set minimum height instead of fixed
        self.log_label.setStyleSheet(
            """
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 8px;
                border-radius: 4px;
            }
            """
        )
        log_layout.addWidget(self.log_label)

        # Add log container to control layout
        control_layout.addWidget(log_container)

        # --- Right Panel: Visualizations ---
        vis_panel = QWidget()  # Main container for all visualizations
        main_vis_layout = QHBoxLayout(
            vis_panel
        )  # Main layout for vis_panel will be horizontal

        # --- Left Visualization Column (Camera + Radar) ---
        left_vis_column_widget = QWidget()
        left_vis_layout = QVBoxLayout(left_vis_column_widget)
        left_vis_layout.setContentsMargins(
            0, 0, 0, 0
        )  # No margins for the inner layout

        # Video Feed Display
        self.video_label = QLabel("Video Feed")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setFrameShape(QFrame.Shape.Box)
        self.video_label.setStyleSheet("background-color: black; color: grey;")
        self.video_label.setMinimumSize(320, 240)

        # Radar Widget
        self.radar_widget = RadarWidget(reset_timeout=RADAR_RESET_TIMEOUT)
        self.radar_widget.section_reset.connect(self._on_radar_section_reset)
        self.radar_widget.setMinimumSize(320, 320)  # Match MapWidget's minimum

        left_vis_layout.addWidget(QLabel("Camera Feed:"))
        left_vis_layout.addWidget(self.video_label, stretch=1)
        left_vis_layout.addWidget(QLabel("Human Direction Radar:"))
        left_vis_layout.addWidget(self.radar_widget, stretch=1)

        # --- Right Visualization Column (Map) ---
        right_vis_column_widget = QWidget()
        right_vis_layout = QVBoxLayout(right_vis_column_widget)
        right_vis_layout.setContentsMargins(0, 0, 0, 0)

        # Map Widget
        self.map_widget = MapWidget()
        # self.map_widget.setMinimumSize(320,320) # Already set in MapWidget constructor

        right_vis_layout.addWidget(QLabel("Position Map:"))
        right_vis_layout.addWidget(self.map_widget, stretch=1)

        # Add columns to the main visualization layout
        main_vis_layout.addWidget(
            left_vis_column_widget, stretch=1
        )  # Left column takes 1 part
        main_vis_layout.addWidget(
            right_vis_column_widget, stretch=1
        )  # Right column takes 1 part

        # --- Add Panels to Main Layout ---
        main_layout.addWidget(control_panel)
        main_layout.addWidget(
            vis_panel, stretch=1
        )  # Allow vis panel to take more space

        # --- Status Bar ---
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Status: Initializing...")

        # --- WebSocket Client ---
        self.ws_client = WebSocketClientThread(WEBSOCKET_VIDEO_URI)
        self.ws_client.connection_status.connect(self.update_status_bar)
        self.ws_client.image_received.connect(self.update_video_feed)
        self.ws_client.map_data_received.connect(self.update_map)  # Connect map signal
        self.ws_client.log_message.connect(self.append_log_message)
        self.ws_client.start()  # Start the WebSocket thread

        # --- Audio WebSocket Client ---
        self.audio_client = AudioWebSocketClientThread(WEBSOCKET_AUDIO_URI)
        self.audio_client.connection_status.connect(
            lambda status: self.update_status_bar(f"Audio: {status}")
        )
        self.audio_client.log_message.connect(self.append_log_message)
        self.audio_client.start()  # Start the audio WebSocket thread

        # --- MQTT Clients ---
        # Sound direction MQTT client
        self.sound_mqtt_client = MQTTClient(
            broker_host=MQTT_BROKER_HOST,
            broker_port=MQTT_BROKER_PORT,
            topic=MQTT_SOUND_TOPIC,
        )
        self.sound_mqtt_client.connected.connect(
            lambda: self.append_log_message("Sound MQTT Connected")
        )
        self.sound_mqtt_client.disconnected.connect(
            lambda: self.append_log_message("Sound MQTT Disconnected")
        )
        self.sound_mqtt_client.error_occurred.connect(self.append_log_message)
        self.sound_mqtt_client.message_received.connect(self._on_mqtt_message)
        self.sound_mqtt_client.start()

        # Movement MQTT client
        self.movement_mqtt_client = MQTTClient(
            broker_host=MQTT_BROKER_HOST,
            broker_port=MQTT_BROKER_PORT,
            topic=MQTT_MOVEMENT_TOPIC,
        )
        self.movement_mqtt_client.connected.connect(
            lambda: self.append_log_message("Movement MQTT Connected")
        )
        self.movement_mqtt_client.disconnected.connect(
            lambda: self.append_log_message("Movement MQTT Disconnected")
        )
        self.movement_mqtt_client.error_occurred.connect(self.append_log_message)
        self.movement_mqtt_client.start()

        # Position MQTT client (New)
        self.position_mqtt_client = MQTTClient(
            broker_host=MQTT_BROKER_HOST,
            broker_port=MQTT_BROKER_PORT,
            topic=MQTT_POSITION_TOPIC,
        )
        self.position_mqtt_client.connected.connect(
            lambda: self.append_log_message("Position MQTT Connected")
        )
        self.position_mqtt_client.disconnected.connect(
            lambda: self.append_log_message("Position MQTT Disconnected")
        )
        self.position_mqtt_client.error_occurred.connect(self.append_log_message)
        self.position_mqtt_client.message_received.connect(self._on_position_message)
        self.position_mqtt_client.start()

        # --- Connect Button Signals ---
        self.btn_forward.clicked.connect(lambda: self.send_robot_command("forward"))
        self.btn_backward.clicked.connect(lambda: self.send_robot_command("backward"))
        self.btn_left.clicked.connect(lambda: self.send_robot_command("left"))
        self.btn_right.clicked.connect(lambda: self.send_robot_command("right"))
        self.btn_stop.clicked.connect(lambda: self.send_robot_command("stop"))

        # Add Keyboard Shortcuts
        self.btn_forward.setShortcut("W")
        self.btn_backward.setShortcut("X")  # Changed from S to avoid conflict
        self.btn_left.setShortcut("A")
        self.btn_right.setShortcut("D")
        self.btn_stop.setShortcut("S")  # Set 'S' for stop

        # Initial log message
        self.append_log_message("GUI Started. Initializing connections...")

    # --- Slot Methods (GUI Updates) ---
    @Slot(str)
    def update_status_bar(self, message):
        self.status_bar.showMessage(f"Status: {message}")

    @Slot(QPixmap)
    def update_video_feed(self, pixmap):
        # Scale pixmap to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled_pixmap)

    @Slot(object)
    def update_map(self, data):
        # TODO: Implement map visualization logic
        # For now, just display the received data type or simple info
        self.map_label.setText(
            f"Map Data Received:\n{data}\n(Visualization not implemented yet)"
        )
        self.append_log_message(f"Received map data: {data}")
        # Later: Use QGraphicsScene/QGraphicsView to draw points, lines, etc. based on 'data'

    @Slot(str)
    def append_log_message(self, message):
        current_text = self.log_label.text()
        # Keep log reasonably short (e.g., last 10 lines)
        lines = current_text.split("\n")
        if "Log messages will appear here." in lines[0]:
            lines = []  # Clear initial message
        lines.append(message)
        max_lines = 10
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        self.log_label.setText("\n".join(lines))
        print(f"LOG: {message}")  # Also print to console for debugging

    @Slot(dict)
    def _on_mqtt_message(self, data):
        """Handle incoming MQTT messages."""
        try:
            position = data.get("position")
            confidence = data.get("human_confidence")

            if position is not None and confidence is not None:
                self.radar_widget.update_section(position, confidence)
                self.append_log_message(
                    f"Sound detected at {position}° with confidence {confidence:.2f}"
                )
            else:
                self.append_log_message("Invalid data format received")
        except Exception as e:
            self.append_log_message(f"Error processing MQTT message: {str(e)}")

    @Slot(int)
    def _on_radar_section_reset(self, section_idx):
        """Handle radar section reset."""
        # Calculate angle based on the radar widget's current configuration
        if self.radar_widget.num_sections > 0:
            angle = section_idx * self.radar_widget.section_angle
            self.append_log_message(f"Radar section at ~{angle:.0f}° reset")
        else:
            self.append_log_message(
                f"Radar section {section_idx} reset (angle calculation error)"
            )

    @Slot(dict)
    def _on_position_message(self, data):
        """Handle incoming MQTT position messages for beacons."""
        try:
            if not isinstance(data, dict):
                self.append_log_message(
                    f"Invalid position data type: expected dict, got {type(data)}"
                )
                return

            for beacon_id, coords in data.items():
                if isinstance(coords, dict):
                    x = coords.get("x")
                    y = coords.get("y")

                    if x is not None and y is not None:
                        try:
                            pos_x = float(x)
                            pos_y = float(y)
                            self.map_widget.update_beacon_position(
                                beacon_id, pos_x, pos_y
                            )
                            self.append_log_message(
                                f"Updated {beacon_id} position: ({pos_x:.2f}, {pos_y:.2f})"
                            )
                        except ValueError:
                            self.append_log_message(
                                f"Invalid coordinate values for {beacon_id}: x={x}, y={y}"
                            )
                    else:
                        self.append_log_message(
                            f"Missing x or y for {beacon_id} in data: {coords}"
                        )
                else:
                    self.append_log_message(
                        f"Invalid coordinate structure for {beacon_id}: {coords}"
                    )

        except Exception as e:
            self.append_log_message(
                f"Error processing position message: {str(e)} - Data: {data}"
            )

    # --- Action Methods ---
    def send_robot_command(self, command):
        """Send movement command via MQTT."""
        try:
            message = {"command": command, "timestamp": time.time()}
            success = self.movement_mqtt_client.publish(
                MQTT_MOVEMENT_TOPIC, json.dumps(message)
            )
            if success:
                self.append_log_message(f"Sent movement command: {command}")
        except Exception as e:
            self.append_log_message(f"Error sending movement command: {str(e)}")

    def closeEvent(self, event):
        """Ensure all threads are stopped gracefully on GUI close."""
        self.append_log_message("GUI closing...")
        self.ws_client.stop()
        self.sound_mqtt_client.stop()
        self.movement_mqtt_client.stop()
        self.position_mqtt_client.stop()
        self.audio_client.stop()

        self.ws_client.wait(5000)
        self.sound_mqtt_client.wait(5000)
        self.movement_mqtt_client.wait(5000)
        self.position_mqtt_client.wait(5000)
        self.audio_client.wait(5000)
        super().closeEvent(event)


# --- Main Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set a font if desired
    # font = QFont("Segoe UI", 10)
    # app.setFont(font)

    window = RobotControlGUI()
    window.show()
    sys.exit(app.exec())
