from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QTableWidget

from app.constants import COMPONENT_MIME_TYPE


class ComponentPaletteTable(QTableWidget):
    """Drag source for STEP component definitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)

    def startDrag(self, supported_actions):
        row = self.currentRow()
        if row < 0:
            return

        item = self.item(row, 0)
        if item is None:
            return

        component_id = item.data(Qt.UserRole)
        if not component_id:
            return

        mime = QMimeData()
        mime.setData(
            COMPONENT_MIME_TYPE,
            str(component_id).encode("utf-8"),
        )

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)
