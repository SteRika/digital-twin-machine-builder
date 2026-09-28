from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class ComponentsPage(QWidget):
    importRequested=Signal(); addRequested=Signal(str); removeRequested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); lay=QVBoxLayout(self); lay.setContentsMargins(14,14,14,14)
        title=QLabel("COMPONENT LIBRARY"); title.setObjectName("pageTitle"); lay.addWidget(title)
        sub=QLabel("Every mechanical component in V10 must originate from a .STEP or .STP file. Render meshes are only generated caches."); sub.setWordWrap(True); sub.setObjectName("muted"); lay.addWidget(sub)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Component","STEP Source","Size X×Y×Z","Instances"]); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.horizontalHeader().setStretchLastSection(True); lay.addWidget(self.table,1)
        row=QHBoxLayout(); imp=QPushButton("+ IMPORT STEP"); imp.setObjectName("primaryButton"); add=QPushButton("ADD TO ASSEMBLY"); rem=QPushButton("REMOVE"); row.addWidget(imp); row.addWidget(add); row.addWidget(rem); lay.addLayout(row)
        imp.clicked.connect(self.importRequested); add.clicked.connect(self._add); rem.clicked.connect(self._remove)
        self._ids=[]
    def selected_id(self):
        r=self.table.currentRow(); return self._ids[r] if 0<=r<len(self._ids) else ""
    def _add(self):
        if self.selected_id(): self.addRequested.emit(self.selected_id())
    def _remove(self):
        if self.selected_id(): self.removeRequested.emit(self.selected_id())
    def refresh(self,project):
        self._ids=[c.id for c in project.components]; self.table.setRowCount(len(project.components))
        for r,c in enumerate(project.components):
            count=sum(1 for x in project.instances if x.component_id==c.id)
            vals=[c.name,c.source_name or c.step_file," × ".join(f"{v:.1f}" for v in c.dimensions),str(count)]
            for col,val in enumerate(vals): self.table.setItem(r,col,QTableWidgetItem(val))
        if self._ids and self.table.currentRow()<0: self.table.selectRow(0)
