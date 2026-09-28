from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent); self.setObjectName("statCard")
        lay=QVBoxLayout(self); lay.setContentsMargins(12,10,12,10)
        t=QLabel(title); t.setObjectName("statTitle")
        self.value=QLabel("-"); self.value.setObjectName("statValue")
        lay.addWidget(t); lay.addWidget(self.value)
    def set_value(self, value): self.value.setText(str(value))
