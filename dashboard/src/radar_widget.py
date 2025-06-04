from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
import math

# Define the input angle that corresponds to visual North (top of the radar)
INPUT_NORTH_ANGLE_OFFSET = 150.0


class RadarWidget(QWidget):
    # Signal emitted when a section's confidence is reset
    section_reset = Signal(int)  # section index

    def __init__(self, parent=None, reset_timeout=5000):
        super().__init__(parent)
        self.setMinimumSize(320, 320)  # Minimum size to ensure visibility

        # Configuration
        self.num_sections = 36  # Changed from 12 to 36
        self.section_angle = 360.0 / self.num_sections  # Should be 10.0
        self.reset_timeout = reset_timeout  # milliseconds

        # State
        self.section_confidences = [0.0] * self.num_sections
        self.section_timers = [QTimer(self) for _ in range(self.num_sections)]

        # Configure timers
        for i, timer in enumerate(self.section_timers):
            timer.setSingleShot(True)
            timer.timeout.connect(lambda idx=i: self._reset_section(idx))

    def update_section(self, position_degrees, confidence):
        """Update a section with new confidence value, considering custom North."""
        # Normalize the input angle: 0 degrees on the radar GUI is INPUT_NORTH_ANGLE_OFFSET from input data
        # Angles increase clockwise on the input data according to the new spec.
        # visual_angle = (input_angle - offset + 360) % 360
        # Example: input 150 (North) -> (150 - 150 + 360)%360 = 0 (visual North)
        # Example: input 0 (150 deg CW from North) -> (0 - 150 + 360)%360 = 210 (visual 210 deg CW from North)
        # The user states: "0 is clockwise, direction to 300 is counterclockwise" relative to 150 being North.
        # This means input 0 degrees is visually at (0 - 150 + 360)%360 = 210 degrees on our visual radar (0 is top).
        # And input 300 degrees is visually at (300 - 150 + 360)%360 = 150 degrees on our visual radar.

        visual_angle_degrees = (
            float(position_degrees) - INPUT_NORTH_ANGLE_OFFSET + 360.0
        ) % 360.0

        # Determine the section based on the visual angle
        section = int(visual_angle_degrees / self.section_angle)

        # Clamp section index to be within valid range
        section = max(0, min(section, self.num_sections - 1))

        # Update confidence
        self.section_confidences[section] = confidence

        # Reset and start timer for this section
        self.section_timers[section].stop()
        self.section_timers[section].start(self.reset_timeout)

        # Trigger repaint
        self.update()

    def _reset_section(self, section_idx):
        """Reset a section's confidence to 0."""
        self.section_confidences[section_idx] = 0.0
        self.section_reset.emit(section_idx)
        self.update()

    def set_reset_timeout(self, milliseconds):
        """Set the timeout duration for resetting sections."""
        self.reset_timeout = milliseconds
        for timer in self.section_timers:
            if timer.isActive():
                timer.setInterval(milliseconds)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 20  # Leave margin for text

        # Draw sections
        for i in range(self.num_sections):
            # visual_start_angle_deg is the start angle for drawing the i-th section
            # on the GUI, where 0 degrees is at the top (North).
            visual_start_angle_deg = i * self.section_angle
            confidence = self.section_confidences[i]

            if confidence == 0:
                color = QColor(200, 200, 200)  # Light gray
            else:
                red_value = int(
                    255 - (confidence * 155)
                )  # 255 (light red) to 100 (darker red)
                color = QColor(255, red_value, red_value)

            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setBrush(QBrush(color))

            # Qt's 0 degrees is at 3 o'clock. We need to map our visual_start_angle_deg.
            # If visual_start_angle_deg = 0 (top), Qt angle is 90.
            # If visual_start_angle_deg = 90 (right), Qt angle is 0.
            # Formula: qt_angle = 90 - visual_angle
            qt_paint_start_angle = (90.0 - visual_start_angle_deg) * 16.0
            qt_paint_span_angle = (
                -self.section_angle * 16.0
            )  # Negative for clockwise span

            painter.drawPie(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2),
                int(qt_paint_start_angle),
                int(qt_paint_span_angle),
            )

            if confidence > 0:
                # Midpoint of the visual section for text placement
                visual_mid_angle_deg = visual_start_angle_deg + self.section_angle / 2.0
                visual_mid_angle_rad = math.radians(visual_mid_angle_deg)

                text_radius = radius * 0.7
                text_x = center_x + text_radius * math.sin(visual_mid_angle_rad)
                text_y = center_y - text_radius * math.cos(visual_mid_angle_rad)

                painter.setPen(QPen(Qt.GlobalColor.black))
                # Potentially smaller font if sections are very narrow
                font_size = 7 if self.num_sections > 24 else 8
                painter.setFont(QFont("Arial", font_size))

                # Adjust text box size if needed, though it might be tight for 10-degree sections
                text_rect_width = 30
                text_rect_height = 15
                painter.drawText(
                    int(text_x - text_rect_width / 2),
                    int(text_y - text_rect_height / 2),
                    text_rect_width,
                    text_rect_height,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{confidence:.2f}",
                )
