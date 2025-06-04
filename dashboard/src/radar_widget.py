from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
import math


class RadarWidget(QWidget):
    # Signal emitted when a section's confidence is reset
    section_reset = Signal(int)  # section index

    def __init__(self, parent=None, reset_timeout=5000):
        super().__init__(parent)
        self.setMinimumSize(320, 320)  # Minimum size to ensure visibility

        # Configuration
        self.num_sections = 36  # Changed from 12 to 36
        self.section_angle = 360 / self.num_sections  # Will be 10 degrees
        self.reset_timeout = reset_timeout  # milliseconds

        # State
        self.section_confidences = [0.0] * self.num_sections
        self.section_timers = [QTimer(self) for _ in range(self.num_sections)]

        # Configure timers
        for i, timer in enumerate(self.section_timers):
            timer.setSingleShot(True)
            timer.timeout.connect(lambda idx=i: self._reset_section(idx))

    def update_section(self, position_degrees, confidence):
        """Update a section with new confidence value."""
        # Calculate which section this position corresponds to
        # Ensure position_degrees is handled correctly, e.g., always positive
        normalized_degrees = position_degrees % 360
        section = int(normalized_degrees / self.section_angle)

        # Clamp section index to be within valid range, just in case of floating point issues
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
            start_angle_deg = (
                i * self.section_angle
            )  # Start angle in degrees for math calculations
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

            # Qt's drawPie uses 1/16th of a degree. Angle 0 is at 3 o'clock.
            # We want 0 degrees to be at the top (North).
            # So, map our 0 degrees (North) to Qt's 90 degrees.
            qt_start_angle = (90 - start_angle_deg) * 16
            qt_span_angle = -self.section_angle * 16  # Negative for clockwise span

            painter.drawPie(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2),
                int(qt_start_angle),
                int(qt_span_angle),
            )

            if confidence > 0:
                # Calculate midpoint of the section for text placement
                mid_angle_rad = math.radians(start_angle_deg + self.section_angle / 2)
                text_radius = radius * 0.7

                # Adjust text position so 0 degrees is at the top
                text_x = center_x + text_radius * math.sin(mid_angle_rad)
                text_y = center_y - text_radius * math.cos(mid_angle_rad)

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
