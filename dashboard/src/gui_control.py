import sys
import asyncio
import websockets
import cv2
import numpy as np
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QGridLayout
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal, Slot

# --- Configuration ---
# Use the URI from your WSVideoClient script
WEBSOCKET_URI = "ws://localhost:9002"

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
                            q_img = QImage(img.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
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
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        # --- Central Widget and Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget) # Horizontal split

        # --- Left Panel: Controls ---
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(200) # Adjust width as needed

        # Movement Buttons
        move_buttons_layout = QGridLayout()
        self.btn_forward = QPushButton("Forward (W)")
        self.btn_left = QPushButton("Left (A)")
        self.btn_stop = QPushButton("Stop (S)")
        self.btn_right = QPushButton("Right (D)")
        self.btn_backward = QPushButton("Backward (X)") # Changed from S

        # Arrange buttons intuitively
        move_buttons_layout.addWidget(self.btn_forward, 0, 1)
        move_buttons_layout.addWidget(self.btn_left, 1, 0)
        move_buttons_layout.addWidget(self.btn_stop, 1, 1)
        move_buttons_layout.addWidget(self.btn_right, 1, 2)
        move_buttons_layout.addWidget(self.btn_backward, 2, 1)

        # Log/Status Display (Simple Label for now)
        self.log_label = QLabel("Log messages will appear here.")
        self.log_label.setWordWrap(True)
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.log_label.setFixedHeight(150) # Adjust height
        self.log_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; padding: 5px;")


        control_layout.addWidget(QLabel("Movement Controls:"))
        control_layout.addLayout(move_buttons_layout)
        control_layout.addStretch() # Pushes logs to the bottom
        control_layout.addWidget(QLabel("Log:"))
        control_layout.addWidget(self.log_label)


        # --- Right Panel: Visualizations ---
        vis_panel = QWidget()
        vis_layout = QVBoxLayout(vis_panel)

        # Video Feed Display
        self.video_label = QLabel("Video Feed")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setFrameShape(QFrame.Shape.Box)
        self.video_label.setStyleSheet("background-color: black; color: grey;")
        self.video_label.setMinimumSize(320, 240) # Minimum size

        # Map Display Placeholder
        self.map_label = QLabel("Map Area") # Placeholder for map visualization
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map_label.setFrameShape(QFrame.Shape.Box)
        self.map_label.setStyleSheet("background-color: #e0e0e0; color: grey;")
        self.map_label.setMinimumSize(320, 240) # Minimum size

        vis_layout.addWidget(QLabel("Camera Feed:"))
        vis_layout.addWidget(self.video_label, stretch=1) # Allow video to expand
        vis_layout.addWidget(QLabel("Map Visualization:"))
        vis_layout.addWidget(self.map_label, stretch=1) # Allow map to expand

        # --- Add Panels to Main Layout ---
        main_layout.addWidget(control_panel)
        main_layout.addWidget(vis_panel, stretch=1) # Allow vis panel to take more space

        # --- Status Bar ---
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Status: Initializing...")

        # --- WebSocket Client ---
        self.ws_client = WebSocketClientThread(WEBSOCKET_URI)
        self.ws_client.connection_status.connect(self.update_status_bar)
        self.ws_client.image_received.connect(self.update_video_feed)
        self.ws_client.map_data_received.connect(self.update_map) # Connect map signal
        self.ws_client.log_message.connect(self.append_log_message)
        self.ws_client.start() # Start the WebSocket thread

        # --- Connect Button Signals ---
        # Use lambda to pass the command string easily
        self.btn_forward.clicked.connect(lambda: self.send_robot_command("forward"))
        self.btn_backward.clicked.connect(lambda: self.send_robot_command("backward"))
        self.btn_left.clicked.connect(lambda: self.send_robot_command("left"))
        self.btn_right.clicked.connect(lambda: self.send_robot_command("right"))
        self.btn_stop.clicked.connect(lambda: self.send_robot_command("stop"))

        # Add Keyboard Shortcuts
        self.btn_forward.setShortcut("W")
        self.btn_backward.setShortcut("X") # Changed from S to avoid conflict
        self.btn_left.setShortcut("A")
        self.btn_right.setShortcut("D")
        self.btn_stop.setShortcut("S") # Set 'S' for stop

        # Initial log message
        self.append_log_message("GUI Started. Attempting WebSocket connection...")

    # --- Slot Methods (GUI Updates) ---
    @Slot(str)
    def update_status_bar(self, message):
        self.status_bar.showMessage(f"Status: {message}")

    @Slot(QPixmap)
    def update_video_feed(self, pixmap):
        # Scale pixmap to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(self.video_label.size(),
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)

    @Slot(object)
    def update_map(self, data):
        # TODO: Implement map visualization logic
        # For now, just display the received data type or simple info
        self.map_label.setText(f"Map Data Received:\n{data}\n(Visualization not implemented yet)")
        self.append_log_message(f"Received map data: {data}")
        # Later: Use QGraphicsScene/QGraphicsView to draw points, lines, etc. based on 'data'

    @Slot(str)
    def append_log_message(self, message):
        current_text = self.log_label.text()
        # Keep log reasonably short (e.g., last 10 lines)
        lines = current_text.split('\n')
        if "Log messages will appear here." in lines[0]:
            lines = [] # Clear initial message
        lines.append(message)
        max_lines = 10
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        self.log_label.setText("\n".join(lines))
        print(f"LOG: {message}") # Also print to console for debugging

    # --- Action Methods ---
    def send_robot_command(self, command):
        self.append_log_message(f"Sending command: {command}")
        self.ws_client.send_command(command)

    def closeEvent(self, event):
        """ Ensure WebSocket thread is stopped gracefully on GUI close """
        self.append_log_message("GUI closing...")
        self.ws_client.stop()
        self.ws_client.wait(5000) # Wait up to 5 seconds for thread to finish
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