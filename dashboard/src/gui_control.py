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
WEBSOCKET_URI = "ws://vlg2.local:9002"

# --- WebSocket Communication Thread ---
class WebSocketClientThread(QThread):
    """
    Handles WebSocket communication in a separate thread.
    Connects to a server that sends raw image bytes and potentially
    sends/receives JSON messages for commands and telemetry.
    """
    connection_status = Signal(str)
    image_received = Signal(QPixmap) # Signal to send the processed image QPixmap
    map_data_received = Signal(object) # Signal for map data (e.g., coordinates)
    log_message = Signal(str) # Signal for log messages

    def __init__(self, uri):
        super().__init__()
        self.uri = uri
        self._ws = None
        self._running = False
        # Use asyncio.Queue for thread-safe communication from GUI thread to async loop
        self._send_queue = asyncio.Queue()
        self._loop = None # To hold the event loop for this thread

    async def _run_async(self):
        """ The asynchronous part of the thread's execution """
        self._running = True
        while self._running:
            try:
                self.connection_status.emit(f"Connecting to {self.uri}...")
                # Connect with increased max_size for image data, like in WSVideoClient
                async with websockets.connect(self.uri, max_size=None, ping_interval=10, ping_timeout=5) as websocket:
                    self._ws = websocket
                    self.connection_status.emit("Connected")
                    self.log_message.emit("WebSocket connection established.")

                    # Start sender and receiver tasks concurrently
                    consumer_task = asyncio.create_task(self._receive_messages())
                    producer_task = asyncio.create_task(self._send_messages())

                    # Wait for either task to complete (or be cancelled if self._running becomes False)
                    done, pending = await asyncio.wait(
                        [consumer_task, producer_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # If one task finishes, cancel the other before looping to reconnect/exit
                    for task in pending:
                        task.cancel()
                    # Wait for cancellation to be processed
                    await asyncio.gather(*pending, return_exceptions=True)

            except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError) as e:
                 self.log_message.emit(f"WebSocket connection closed: {e}")
            except (websockets.exceptions.WebSocketException, OSError, asyncio.TimeoutError) as e:
                self.connection_status.emit(f"Connection error: {type(e).__name__}")
                self.log_message.emit(f"WebSocket error: {e}. Retrying in 5s...")
                await asyncio.sleep(5) # Wait before retrying connection
            except Exception as e: # Catch unexpected errors
                 self.log_message.emit(f"Unexpected error in WebSocket loop: {e}")
                 await asyncio.sleep(5) # Wait before potentially retrying
            finally:
                self._ws = None
                if self._running:
                    # Don't emit retrying if we were asked to stop
                    self.connection_status.emit("Disconnected. Retrying...")
                else:
                    self.connection_status.emit("Disconnected.")

        self.log_message.emit("Exiting WebSocket run loop.")


    async def _receive_messages(self):
        """ Listens for incoming messages (bytes for images, str/JSON for others) """
        try:
            async for message in self._ws:
                if not self._running: break # Check running flag frequently
                try:
                    if isinstance(message, bytes):
                        # Assume raw bytes are image data based on your WSVideoClient
                        self._process_raw_image_data(message)
                    elif isinstance(message, str):
                        # Assume string messages are JSON (commands response, map data, logs)
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type")

                            if msg_type == "map":
                                coords = data.get("coords")
                                if coords is not None: # Check existence, allow empty lists/values
                                    self.map_data_received.emit(coords)
                                else:
                                    self.log_message.emit("Received map message with no 'coords' field.")
                            elif msg_type == "log":
                                log_msg = data.get("message", "No log message content.")
                                self.log_message.emit(f"Robot Log: {log_msg}")
                            elif msg_type == "status":
                                status_msg = data.get("message", "No status message content.")
                                self.log_message.emit(f"Robot Status: {status_msg}")
                            # Add handling for other expected JSON message types from the robot
                            # e.g., confirmation of commands, sensor readings
                            else:
                                self.log_message.emit(f"Received JSON with unknown type: {msg_type}")

                        except json.JSONDecodeError:
                            self.log_message.emit(f"Received non-JSON string message: {message[:100]}...")
                        except Exception as e:
                            self.log_message.emit(f"Error processing JSON message: {e}")
                    else:
                        self.log_message.emit(f"Received unexpected message type: {type(message)}")

                except Exception as e:
                    self.log_message.emit(f"Error processing received message: {e}")
                    # Decide if this error is critical and requires stopping the loop

        except websockets.exceptions.ConnectionClosed:
            self.log_message.emit("Receive loop exiting: Connection closed.")
        except asyncio.CancelledError:
             self.log_message.emit("Receive loop cancelled.")
        except Exception as e:
            self.log_message.emit(f"Critical error in receive loop: {e}")
            # This might indicate a need to stop the thread or connection attempt cycle
            # self._running = False # Optional: Stop trying on critical errors


    def _process_raw_image_data(self, img_bytes):
        """ Processes raw image bytes (like in WSVideoClient) and emits QPixmap """
        try:
            # 1. Convert bytes to OpenCV image (numpy array) - Matches WSVideoClient
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR) # Use IMREAD_COLOR or IMREAD_GRAYSCALE

            if img_cv is None:
                # Log sparingly if decoding fails repeatedly
                # Consider adding a counter/timer to avoid spamming logs
                # self.log_message.emit("Failed to decode image data.")
                return # Skip if decode failed

            # 2. Convert OpenCV image (BGR) to QImage
            height, width, channel = img_cv.shape
            bytes_per_line = channel * width # 3 for BGR/RGB, 1 for Grayscale

            # Ensure data is contiguous for QImage. Crucial!
            if not img_cv.flags['C_CONTIGUOUS']:
                 img_cv = np.ascontiguousarray(img_cv)

            # Choose the correct QImage format based on cv2.imdecode setting
            if channel == 3:
                q_format = QImage.Format.Format_BGR888 # OpenCV default is BGR
                # If you need RGB, convert first:
                # img_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                # q_format = QImage.Format.Format_RGB888
            elif channel == 1:
                 q_format = QImage.Format.Format_Grayscale8
                 bytes_per_line = width # Grayscale has 1 byte per pixel
            else:
                 self.log_message.emit(f"Unsupported image channel count: {channel}")
                 return


            q_img = QImage(img_cv.data, width, height, bytes_per_line, q_format)
            # Optional: Create a copy if the numpy array might be reused/modified elsewhere,
            # though typically cv2.imdecode creates a new array.
            # q_img = QImage(img_cv.data, width, height, bytes_per_line, q_format).copy()


            if q_img.isNull():
                self.log_message.emit("Failed to create QImage from image data.")
                return

            # 3. Convert QImage to QPixmap
            pixmap = QPixmap.fromImage(q_img)

            # 4. Emit the signal with the pixmap for the GUI thread
            self.image_received.emit(pixmap)

        except Exception as e:
            # Log the error, avoid crashing the loop if possible
            self.log_message.emit(f"Error processing image data: {e}")
            # For debugging: import traceback; self.log_message.emit(traceback.format_exc())


    async def _send_messages(self):
        """ Sends messages from the queue (likely commands as JSON strings) """
        try:
            while True:
                if not self._ws or not self._ws.open:
                    # Wait briefly if not connected, prevents busy-waiting if queue has items
                    await asyncio.sleep(0.1)
                    continue # Check connection again

                # Wait for a message to appear in the queue
                message = await self._send_queue.get()

                if message is None: # Use None as a sentinel to stop the sender gracefully
                    break

                if self._ws and self._ws.open: # Double-check connection before sending
                    try:
                        # Assuming commands are sent as JSON strings
                        await self._ws.send(message)
                        # self.log_message.emit(f"Sent: {message}") # Optional: Log sent messages
                        self._send_queue.task_done() # Mark task as done *after* successful send
                    except websockets.exceptions.ConnectionClosed:
                        self.log_message.emit("Send failed: Connection closed. Re-queueing.")
                        # Put the message back at the front of the queue to retry later
                        # Be cautious if connection never recovers
                        await self._send_queue.put(message)
                        await asyncio.sleep(1) # Wait a bit before retrying send loop
                        break # Exit sender loop, wait for outer loop to reconnect
                    except Exception as e:
                        self.log_message.emit(f"Error sending message: {e}. Discarding.")
                        # Decide whether to re-queue or discard on other errors
                        self._send_queue.task_done() # Mark as done even if failed to prevent block
                else:
                    self.log_message.emit(f"Send failed: WebSocket not connected. Re-queueing.")
                    await self._send_queue.put(message) # Re-queue
                    await asyncio.sleep(1) # Wait before retrying send loop
                    break # Exit sender loop

        except asyncio.CancelledError:
             self.log_message.emit("Send loop cancelled.")
        except Exception as e:
             self.log_message.emit(f"Critical error in send loop: {e}")
        finally:
            self.log_message.emit("Send loop finished.")


    def run(self):
        """ Entry point for the QThread """
        try:
            # Create and set a new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            # Run the main async logic until it completes
            self._loop.run_until_complete(self._run_async())
        except Exception as e:
            self.log_message.emit(f"WebSocket thread run method error: {e}")
            # import traceback; self.log_message.emit(traceback.format_exc())
        finally:
            # Clean up the loop
            if self._loop:
                 try:
                      # Cancel any remaining tasks in the loop before closing
                      for task in asyncio.all_tasks(self._loop):
                          task.cancel()
                      # Run loop briefly to allow cancellations to process
                      self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                      self._loop.run_until_complete(asyncio.sleep(0.1, loop=self._loop)) # Short sleep
                 except Exception as e:
                      self.log_message.emit(f"Error during loop shutdown: {e}")
                 finally:
                      self._loop.close()
                      self._loop = None

            self.connection_status.emit("Disconnected.") # Ensure final status
            self.log_message.emit("WebSocket client thread finished execution.")


    def send_command(self, command):
        """ Queues a command (formatted as JSON string) to be sent via the async loop """
        if not self._running:
             self.log_message.emit("Cannot send command: WebSocket client not running.")
             return

        # Format the command as JSON - adapt if robot expects different format
        message = json.dumps({"type": "command", "action": command})
        try:
            # Put the message onto the queue for the _send_messages task to pick up
            # This is thread-safe
            self._send_queue.put_nowait(message)
        except asyncio.QueueFull:
             self.log_message.emit("Send queue is full. Command dropped.")
        except Exception as e:
            self.log_message.emit(f"Failed to queue command: {e}")


    def stop(self):
        """ Signals the async loop and thread to stop gracefully """
        self.log_message.emit("Attempting to stop WebSocket client thread...")
        self._running = False # Signal loops to stop

        # Add sentinel to queue to stop sender task if it's waiting
        if self._send_queue:
             self._send_queue.put_nowait(None)

        # Optionally, try to close the connection explicitly if connected.
        # This needs to be done carefully within the thread's loop context.
        if self._ws and self._loop and self._loop.is_running():
            # Schedule the close coroutine to run in the thread's event loop
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            self.log_message.emit("Requested WebSocket connection close.")
        else:
            self.log_message.emit("WebSocket not connected or loop not running, cannot send close.")

        # The QThread.wait() call in the main GUI's closeEvent will wait for run() to finish
        
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