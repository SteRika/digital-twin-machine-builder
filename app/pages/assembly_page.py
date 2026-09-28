from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.constants import ASSEMBLY_SNAP_DEFAULT_MM
from app.widgets.component_palette_table import ComponentPaletteTable


class AssemblyPage(QWidget):
    selectionChanged = Signal(str)
    transformChanged = Signal(str, dict)
    duplicateRequested = Signal(str)
    deleteRequested = Signal(str)
    componentAddRequested = Signal(str)
    addMotionRequested = Signal(str)
    snapChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._sync = False
        self._ids = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("MACHINE ASSEMBLY")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Drag a STEP component from the palette into the 3D workspace. "
            "Then enable MOVE PARTS and drag an existing instance to reposition it. "
            "Direct dragging controls X/Z; use the numeric fields for Y and rotation."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)

        palette_title = QLabel("AVAILABLE STEP COMPONENTS")
        palette_title.setObjectName("sectionTitle")
        layout.addWidget(palette_title)

        self.palette = ComponentPaletteTable()
        self.palette.setColumnCount(3)
        self.palette.setHorizontalHeaderLabels(
            ["Component", "Size X×Y×Z", "Used"]
        )
        self.palette.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.palette.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.palette.horizontalHeader().setStretchLastSection(True)
        self.palette.setMaximumHeight(155)
        layout.addWidget(self.palette)

        palette_row = QHBoxLayout()
        add_origin = QPushButton("ADD AT ORIGIN")
        add_origin.clicked.connect(self._add_palette_selected)
        palette_row.addWidget(add_origin)

        palette_hint = QLabel("Drag → 3D workspace")
        palette_hint.setObjectName("muted")
        palette_row.addWidget(palette_hint)
        palette_row.addStretch()

        palette_row.addWidget(QLabel("Snap"))
        self.snap = QDoubleSpinBox()
        self.snap.setRange(0.0, 1000.0)
        self.snap.setDecimals(1)
        self.snap.setSingleStep(1.0)
        self.snap.setSuffix(" mm")
        self.snap.setSpecialValueText("OFF")
        self.snap.setValue(ASSEMBLY_SNAP_DEFAULT_MM)
        self.snap.valueChanged.connect(
            lambda value: self.snapChanged.emit(float(value))
        )
        palette_row.addWidget(self.snap)
        layout.addLayout(palette_row)

        instance_title = QLabel("ASSEMBLY INSTANCES")
        instance_title.setObjectName("sectionTitle")
        layout.addWidget(instance_title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Instance", "Component", "Group"]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._selected)
        layout.addWidget(self.table, 1)

        form = QFormLayout()
        self.group = QLineEdit()
        form.addRow("Assembly Group", self.group)

        self.spins = []
        labels = [
            "X mm",
            "Y mm",
            "Z mm",
            "Rot X °",
            "Rot Y °",
            "Rot Z °",
        ]
        for label in labels:
            spin = QDoubleSpinBox()
            spin.setRange(-100000.0, 100000.0)
            spin.setDecimals(2)
            spin.setSingleStep(5.0)
            spin.setKeyboardTracking(False)
            self.spins.append(spin)
            form.addRow(label, spin)

        self.visible = QCheckBox("Visible")
        self.visible.setChecked(True)
        form.addRow("", self.visible)
        layout.addLayout(form)

        row = QHBoxLayout()

        apply_button = QPushButton("APPLY TRANSFORM")
        apply_button.setObjectName("primaryButton")

        add_motion_button = QPushButton(
            "+ ADD MOTION"
        )

        duplicate_button = QPushButton("DUPLICATE")
        delete_button = QPushButton("DELETE INSTANCE")

        row.addWidget(apply_button)
        row.addWidget(add_motion_button)
        row.addWidget(duplicate_button)
        row.addWidget(delete_button)
        layout.addLayout(row)

        apply_button.clicked.connect(self._apply)

        add_motion_button.clicked.connect(
            lambda: self.addMotionRequested.emit(
                self.selected_id()
            )
            if self.selected_id()
            else None
        )

        duplicate_button.clicked.connect(
            lambda: self.duplicateRequested.emit(self.selected_id())
            if self.selected_id()
            else None
        )
        delete_button.clicked.connect(
            lambda: self.deleteRequested.emit(self.selected_id())
            if self.selected_id()
            else None
        )

    def selected_id(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._ids):
            return self._ids[row]
        return ""

    def selected_component_id(self):
        row = self.palette.currentRow()
        if row < 0:
            return ""

        item = self.palette.item(row, 0)
        if item is None:
            return ""

        return str(item.data(Qt.UserRole) or "")

    def _add_palette_selected(self):
        component_id = self.selected_component_id()
        if component_id:
            self.componentAddRequested.emit(component_id)

    def select_id(self, instance_id):
        if instance_id in self._ids:
            self.table.selectRow(
                self._ids.index(instance_id)
            )

    def _selected(self):
        if not self._sync and self.selected_id():
            self.selectionChanged.emit(
                self.selected_id()
            )

    def _apply(self):
        instance_id = self.selected_id()
        if not instance_id:
            return

        self.transformChanged.emit(
            instance_id,
            {
                "position": [
                    self.spins[0].value(),
                    self.spins[1].value(),
                    self.spins[2].value(),
                ],
                "rotation": [
                    self.spins[3].value(),
                    self.spins[4].value(),
                    self.spins[5].value(),
                ],
                "group": self.group.text().strip() or "Machine",
                "visible": self.visible.isChecked(),
            },
        )

    def refresh(self, project, selected_id=""):
        self._sync = True

        self.palette.setRowCount(
            len(project.components)
        )
        for row, component in enumerate(project.components):
            count = sum(
                1
                for instance in project.instances
                if instance.component_id == component.id
            )

            component_item = QTableWidgetItem(
                component.name
            )
            component_item.setData(
                Qt.UserRole,
                component.id,
            )

            values = [
                component_item,
                QTableWidgetItem(
                    " × ".join(
                        f"{value:.1f}"
                        for value in component.dimensions
                    )
                ),
                QTableWidgetItem(str(count)),
            ]

            for col, item in enumerate(values):
                self.palette.setItem(
                    row,
                    col,
                    item,
                )

        if (
            project.components
            and self.palette.currentRow() < 0
        ):
            self.palette.selectRow(0)

        self._ids = [
            instance.id
            for instance in project.instances
        ]
        self.table.setRowCount(
            len(project.instances)
        )

        for row, instance in enumerate(project.instances):
            component = project.component(
                instance.component_id
            )
            values = [
                instance.name,
                component.name if component else "<missing>",
                instance.group,
            ]
            for col, value in enumerate(values):
                self.table.setItem(
                    row,
                    col,
                    QTableWidgetItem(value),
                )

        if selected_id in self._ids:
            self.table.selectRow(
                self._ids.index(selected_id)
            )
        elif self._ids:
            self.table.selectRow(0)

        self._sync = False
        self.load_selected(project)

    def load_selected(self, project):
        instance = project.instance(
            self.selected_id()
        )
        if not instance:
            return

        self.group.setText(instance.group)

        values = (
            list(instance.position)
            + list(instance.rotation)
        )
        for spin, value in zip(self.spins, values):
            spin.blockSignals(True)
            spin.setValue(float(value))
            spin.blockSignals(False)

        self.visible.setChecked(
            instance.visible
        )

    def update_position_fields(
        self,
        instance_id,
        position,
    ):
        if instance_id != self.selected_id():
            self.select_id(instance_id)

        for index, value in enumerate(position[:3]):
            self.spins[index].blockSignals(True)
            self.spins[index].setValue(float(value))
            self.spins[index].blockSignals(False)

    def snap_value(self):
        return float(self.snap.value())
