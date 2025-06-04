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
        """Update a section based on the new coordinate system where 150 degrees is North."""
        # Convert input degrees (150=N, 0 is CCW, 300 is CW from 150N)
        # to internal degrees (0=N, positive clockwise).
        # Example: Input 150 (North) -> (150 - 150 + 360) % 360 = 0 (Internal North)
        # Example: Input 140 (10 deg CCW from North) -> (150 - 140 + 360) % 360 = 10 (Internal 10 deg CW)
        # Example: Input 0 (150 deg CCW from North) -> (150 - 0 + 360) % 360 = 150 (Internal 150 deg CW)
        internal_degrees = (150 - position_degrees + 360) % 360

        section = int(internal_degrees / self.section_angle)
        section = max(0, min(section, self.num_sections - 1))  # Clamp index

        self.section_confidences[section] = confidence
        self.section_timers[section].stop()
        self.section_timers[section].start(self.reset_timeout)
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
            # internal_start_angle_deg is 0 for North, increasing clockwise
            internal_start_angle_deg = i * self.section_angle
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

            # Qt's 0 is 3 o'clock, positive CCW. Our internal 0 (North) maps to Qt's 90.
            qt_start_angle = (90 - internal_start_angle_deg) * 16
            qt_span_angle = -self.section_angle * 16

            painter.drawPie(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2),
                int(qt_start_angle),
                int(qt_span_angle),
            )

            if confidence > 0:
                # Midpoint for text, using internal angle (0=N, positive CW)
                mid_internal_angle_rad = math.radians(
                    internal_start_angle_deg + self.section_angle / 2
                )
                text_radius = radius * 0.7

                # Text position: sin for x, cos for y, adjust for 0=N
                text_x = center_x + text_radius * math.sin(mid_internal_angle_rad)
                text_y = center_y - text_radius * math.cos(mid_internal_angle_rad)

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
