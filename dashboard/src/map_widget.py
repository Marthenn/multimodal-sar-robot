from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class MapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)  # Minimum size, actual size will be constrained
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.beacon_positions = {}  # Stores {beacon_id: QPointF}
        self.beacon_colors = {}
        self._default_colors = [
            Qt.GlobalColor.red,
            Qt.GlobalColor.blue,
            Qt.GlobalColor.green,
            Qt.GlobalColor.magenta,
            Qt.GlobalColor.cyan,
            QColor("#FFA500"),  # Orange
            QColor("#800080"),  # Purple
        ]
        self._color_index = 0

        self.padding = 30
        self.axis_color = Qt.GlobalColor.black
        self.grid_color = QColor(220, 220, 220)
        self.max_coord = 100  # Default max coordinate for scaling, updated dynamically

    def _get_beacon_color(self, beacon_id):
        if beacon_id not in self.beacon_colors:
            self.beacon_colors[beacon_id] = self._default_colors[
                self._color_index % len(self._default_colors)
            ]
            self._color_index += 1
        return self.beacon_colors[beacon_id]

    def update_beacon_position(self, beacon_id, x, y):
        """Add or update a beacon's position."""
        self.beacon_positions[beacon_id] = QPointF(x, y)
        self._get_beacon_color(beacon_id)  # Ensure color is assigned
        self._update_max_coord()
        self.update()

    def _update_max_coord(self):
        """Dynamically adjust max_coord based on current beacon positions."""
        if not self.beacon_positions:
            self.max_coord = 100
            return

        max_abs_val = 10.0  # Start with a small sensible minimum range, e.g. -10 to +10
        for point in self.beacon_positions.values():
            max_abs_val = max(max_abs_val, abs(point.x()), abs(point.y()))

        self.max_coord = max(10.0, max_abs_val * 1.1)  # Ensure max_coord is at least 10

    def clear_beacons(self):
        self.beacon_positions = {}
        self.beacon_colors = {}
        self._color_index = 0
        self.max_coord = 100
        self.update()

    def heightForWidth(self, width):
        return width  # Makes the widget prefer a square aspect ratio

    def hasHeightForWidth(self):
        return True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Determine square drawing area
        side = min(self.width(), self.height())
        offset_x = (self.width() - side) / 2
        offset_y = (self.height() - side) / 2

        painter.translate(offset_x, offset_y)  # Center the square drawing area

        # Define the drawable area within the square, considering padding for labels
        drawable_size = side - 2 * self.padding
        origin_x = self.padding + drawable_size / 2
        origin_y = self.padding + drawable_size / 2

        # Fill background for the square drawing area
        painter.fillRect(0, 0, side, side, Qt.GlobalColor.white)

        # Draw grid lines
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))
        num_grid_lines = 5
        for i in range(1, num_grid_lines + 1):
            pos = (drawable_size / 2) * (i / num_grid_lines)
            # Vertical
            painter.drawLine(
                int(origin_x + pos),
                self.padding,
                int(origin_x + pos),
                side - self.padding,
            )
            painter.drawLine(
                int(origin_x - pos),
                self.padding,
                int(origin_x - pos),
                side - self.padding,
            )
            # Horizontal
            painter.drawLine(
                self.padding,
                int(origin_y + pos),
                side - self.padding,
                int(origin_y + pos),
            )
            painter.drawLine(
                self.padding,
                int(origin_y - pos),
                side - self.padding,
                int(origin_y - pos),
            )

        # Draw X and Y axes
        painter.setPen(QPen(self.axis_color, 2))
        painter.drawLine(
            int(self.padding), int(origin_y), int(side - self.padding), int(origin_y)
        )  # X-axis
        painter.drawLine(
            int(origin_x), int(self.padding), int(origin_x), int(side - self.padding)
        )  # Y-axis

        # Draw labels for axes
        font = QFont("Arial", 10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        painter.drawText(side - self.padding + 5, int(origin_y + fm.height() / 2), "X+")
        painter.drawText(
            self.padding - fm.horizontalAdvance("X-") - 10,
            int(origin_y + fm.height() / 2),
            "X-",
        )
        painter.drawText(
            int(origin_x - fm.horizontalAdvance("Y+") / 2), self.padding - 5, "Y+"
        )
        painter.drawText(
            int(origin_x - fm.horizontalAdvance("Y-") / 2),
            side - self.padding + fm.height() + 5,
            "Y-",
        )

        # Scale for plotting points
        scale = drawable_size / (2 * self.max_coord) if self.max_coord != 0 else 1

        # Plot beacon points
        point_radius = 5
        for beacon_id, point in self.beacon_positions.items():
            beacon_color = self._get_beacon_color(beacon_id)
            painter.setBrush(QBrush(beacon_color))
            painter.setPen(Qt.PenStyle.NoPen)

            plot_x = origin_x + point.x() * scale
            plot_y = origin_y - point.y() * scale  # Y is inverted
            painter.drawEllipse(QPointF(plot_x, plot_y), point_radius, point_radius)

            # Optionally, draw beacon_id label next to point
            # painter.setPen(QPen(Qt.GlobalColor.black))
            # painter.drawText(int(plot_x + point_radius + 2), int(plot_y + point_radius), beacon_id)
