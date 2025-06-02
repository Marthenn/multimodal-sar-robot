from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, Signal, Property
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
import math


class RadarWidget(QWidget):
    # Signal emitted when a section's confidence is reset
    section_reset = Signal(int)  # section index

    def __init__(self, parent=None, reset_timeout=5000):
        super().__init__(parent)
        self.setMinimumSize(320, 320)  # Minimum size to ensure visibility

        # Configuration
        self.num_sections = 12
        self.section_angle = 360 / self.num_sections
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
        section = int((position_degrees % 360) / self.section_angle)

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
        # Update all active timers
        for timer in self.section_timers:
            if timer.isActive():
                timer.setInterval(milliseconds)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate center and radius
        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 20  # Leave margin for text

        # Draw sections
        for i in range(self.num_sections):
            start_angle = i * self.section_angle
            confidence = self.section_confidences[i]

            # Calculate color based on confidence
            if confidence == 0:
                color = QColor(200, 200, 200)  # Light gray for no detection
            else:
                # Scale from light red to dark red based on confidence
                red_value = int(255 - (confidence * 155))  # 255 to 100
                color = QColor(255, red_value, red_value)

            # Draw section
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setBrush(QBrush(color))

            # Convert angles to Qt's coordinate system (16th of degrees, clockwise from 3 o'clock)
            start_angle_qt = (90 - start_angle) * 16  # Rotate so 0° is at top
            painter.drawPie(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2),
                int(start_angle_qt),
                int(-self.section_angle * 16),  # Negative for clockwise
            )

            # Draw confidence value if > 0
            if confidence > 0:
                angle_rad = math.radians(start_angle + self.section_angle / 2)
                text_radius = radius * 0.7  # Position text at 70% of radius
                text_x = center_x + text_radius * math.sin(angle_rad)
                text_y = center_y - text_radius * math.cos(angle_rad)

                painter.setPen(QPen(Qt.GlobalColor.black))
                painter.setFont(QFont("Arial", 8))
                painter.drawText(
                    int(text_x - 20),
                    int(text_y - 10),
                    40,  # width
                    20,  # height
                    Qt.AlignmentFlag.AlignCenter,
                    f"{confidence:.2f}",
                )
