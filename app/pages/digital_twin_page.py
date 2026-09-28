from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QVBoxLayout,
    QWidget,
)

from app.simulation import SequenceEvaluator
from app.widgets import StatCard


class DigitalTwinPage(QWidget):
    runRequested = Signal(str, float, bool, float, float)
    skipRequested = Signal(str, float, bool, float, float)
    stopRequested = Signal()
    resetRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._seq_ids = []
        self._project = None
        self._project_identity = None
        self._duration_initialized = False
        self._last_elapsed = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(7)

        title = QLabel('DIGITAL TWIN RUNTIME')
        title.setObjectName('pageTitle')
        layout.addWidget(title)

        subtitle = QLabel(
            'Choose how long the production simulation should run. '
            'Use SKIP TO END to stop animation and calculate the full result immediately.'
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName('muted')
        layout.addWidget(subtitle)

        self.check = QLabel()
        self.check.setWordWrap(True)
        self.check.setObjectName('statusBox')
        layout.addWidget(self.check)

        station_title = QLabel("LIVE STATION PROCESS STATUS")
        station_title.setObjectName("sectionTitle")
        layout.addWidget(station_title)

        self.station_table = QTableWidget(0, 4)
        self.station_table.setHorizontalHeaderLabels(
            ["Station", "Set CT", "Status", "Elapsed"]
        )
        self.station_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.station_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.station_table.horizontalHeader().setStretchLastSection(True)
        self.station_table.setMaximumHeight(215)
        layout.addWidget(self.station_table)

        layout.addWidget(QLabel('Machine Sequence'))
        self.sequence = QComboBox()
        self.sequence.currentIndexChanged.connect(self._sequence_changed)
        layout.addWidget(self.sequence)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel('Run For'))
        self.hours = QSpinBox(); self.hours.setRange(0, 999); self.hours.setSuffix(' h')
        self.minutes = QSpinBox(); self.minutes.setRange(0, 59); self.minutes.setSuffix(' min')
        self.seconds = QSpinBox(); self.seconds.setRange(0, 59); self.seconds.setSuffix(' s')
        for spin in (self.hours, self.minutes, self.seconds):
            spin.valueChanged.connect(self._duration_changed)
            duration_row.addWidget(spin)
        layout.addLayout(duration_row)

        variance_title = QLabel('PROCESS CT VARIANCE')
        variance_title.setObjectName('sectionTitle')
        layout.addWidget(variance_title)

        var_row = QHBoxLayout()
        self.variance_enabled = QCheckBox('Enable CT variance')
        self.variance_enabled.toggled.connect(self._variance_toggled)
        var_row.addWidget(self.variance_enabled)
        var_row.addWidget(QLabel('Min CT'))
        self.ct_min = QDoubleSpinBox(); self.ct_min.setRange(0.1, 9999.0); self.ct_min.setDecimals(2); self.ct_min.setSuffix(' s')
        self.ct_min.valueChanged.connect(self._duration_changed)
        var_row.addWidget(self.ct_min)
        var_row.addWidget(QLabel('Max CT'))
        self.ct_max = QDoubleSpinBox(); self.ct_max.setRange(0.1, 9999.0); self.ct_max.setDecimals(2); self.ct_max.setSuffix(' s')
        self.ct_max.valueChanged.connect(self._duration_changed)
        var_row.addWidget(self.ct_max)
        layout.addLayout(var_row)

        self.variance_note = QLabel()
        self.variance_note.setWordWrap(True)
        self.variance_note.setObjectName('muted')
        layout.addWidget(self.variance_note)

        perf_title = QLabel('AVERAGE PRODUCTION PERFORMANCE')
        perf_title.setObjectName('sectionTitle')
        layout.addWidget(perf_title)

        perf_grid = QGridLayout()
        self.process_ct_card = StatCard('Avg Process / Index CT')
        self.output_ct_card = StatCard('Avg CT / Output')
        self.uph_card = StatCard('Theoretical / Expected UPH')
        self.output_process_card = StatCard('Output / Process')
        perf_grid.addWidget(self.process_ct_card, 0, 0)
        perf_grid.addWidget(self.output_ct_card, 0, 1)
        perf_grid.addWidget(self.uph_card, 1, 0)
        perf_grid.addWidget(self.output_process_card, 1, 1)
        layout.addLayout(perf_grid)

        self.sequence_note = QLabel()
        self.sequence_note.setWordWrap(True)
        self.sequence_note.setObjectName('muted')
        layout.addWidget(self.sequence_note)

        result_title = QLabel('SIMULATION RESULT')
        result_title.setObjectName('sectionTitle')
        layout.addWidget(result_title)

        result_grid = QGridLayout()
        self.output_card = StatCard('Output Produced')
        self.process_card = StatCard('Completed Processes')
        self.effective_uph_card = StatCard('Effective UPH')
        self.elapsed_card = StatCard('Elapsed')
        result_grid.addWidget(self.output_card, 0, 0)
        result_grid.addWidget(self.process_card, 0, 1)
        result_grid.addWidget(self.effective_uph_card, 1, 0)
        result_grid.addWidget(self.elapsed_card, 1, 1)
        layout.addLayout(result_grid)

        self.forecast_note = QLabel()
        self.forecast_note.setWordWrap(True)
        self.forecast_note.setObjectName('statusBox')
        layout.addWidget(self.forecast_note)

        self.progress = QProgressBar(); self.progress.setRange(0, 1000)
        layout.addWidget(self.progress)
        self.time = QLabel('00:00:00 / 00:00:00')
        layout.addWidget(self.time)

        row = QHBoxLayout()
        run_button = QPushButton('RUN DIGITAL TWIN'); run_button.setObjectName('primaryButton')
        self.skip_button = QPushButton('SKIP TO END')
        self.skip_button.setToolTip('Stop watching the animation and calculate the selected run duration immediately.')
        stop_button = QPushButton('STOP')
        reset_button = QPushButton('RESET')
        row.addWidget(run_button); row.addWidget(self.skip_button); row.addWidget(stop_button); row.addWidget(reset_button)
        layout.addLayout(row)
        layout.addStretch()

        run_button.clicked.connect(self._run)
        self.skip_button.clicked.connect(self._skip)
        stop_button.clicked.connect(self.stopRequested)
        reset_button.clicked.connect(self.resetRequested)

        self._set_live_result(0.0)
        self._variance_toggled(False)

    def run_seconds(self):
        return float(self.hours.value() * 3600 + self.minutes.value() * 60 + self.seconds.value())

    def variance_settings(self):
        return (
            bool(self.variance_enabled.isChecked()),
            float(self.ct_min.value()),
            float(self.ct_max.value()),
        )

    def _set_duration_seconds(self, seconds):
        total = max(0, int(round(float(seconds))))
        h = total // 3600; remainder = total % 3600; m = remainder // 60; s = remainder % 60
        for spin in (self.hours, self.minutes, self.seconds):
            spin.blockSignals(True)
        self.hours.setValue(h); self.minutes.setValue(m); self.seconds.setValue(s)
        for spin in (self.hours, self.minutes, self.seconds):
            spin.blockSignals(False)

    @staticmethod
    def _format_hms(seconds):
        total = max(0, int(round(float(seconds))))
        h = total // 3600; m = (total % 3600) // 60; s = total % 60
        return f'{h:02d}:{m:02d}:{s:02d}'

    @staticmethod
    def _format_quantity(value):
        value = float(value)
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f'{value:.2f}'

    def selected_sequence_id(self):
        index = self.sequence.currentIndex()
        if 0 <= index < len(self._seq_ids):
            return self._seq_ids[index]
        return ''

    def _selected_sequence(self):
        if self._project is None:
            return None
        return self._project.sequence(self.selected_sequence_id())

    def _metrics_for(self, run_seconds):
        sequence = self._selected_sequence()
        if sequence is None:
            return None
        enabled, ct_min, ct_max = self.variance_settings()
        return SequenceEvaluator.runtime_metrics(
            sequence,
            run_seconds,
            variance_enabled=enabled,
            ct_min=ct_min,
            ct_max=ct_max,
        )

    def _sequence_changed(self):
        self._last_elapsed = 0.0
        self._apply_nominal_defaults()
        self._refresh_metrics()
        self._set_live_result(0.0)

    def _duration_changed(self):
        self._last_elapsed = 0.0
        self._refresh_metrics()
        self._set_live_result(0.0)

    def _variance_toggled(self, checked):
        self.ct_min.setEnabled(bool(checked))
        self.ct_max.setEnabled(bool(checked))
        self._refresh_metrics()
        self._set_live_result(self._last_elapsed)

    def _apply_nominal_defaults(self):
        sequence = self._selected_sequence()
        if sequence is None:
            return
        metrics = SequenceEvaluator.runtime_metrics(sequence, max(self.run_seconds(), 1.0))
        nominal = float(metrics.get('average_process_ct', 0.0))
        if nominal <= 0:
            nominal = 14.0
        for spin in (self.ct_min, self.ct_max):
            spin.blockSignals(True)
        self.ct_min.setValue(max(0.1, nominal - 1.0))
        self.ct_max.setValue(max(0.1, nominal + 1.0))
        for spin in (self.ct_min, self.ct_max):
            spin.blockSignals(False)
        self.variance_note.setText(
            f'Turn this on to simulate varying process CT, for example {max(0.1, nominal-1.0):.2f}s to {nominal+1.0:.2f}s.'
        )

    def _refresh_metrics(self):
        sequence = self._selected_sequence()
        if sequence is None:
            for card in (self.process_ct_card, self.output_ct_card, self.uph_card, self.output_process_card):
                card.set_value('-')
            self.sequence_note.setText('Select a sequence.')
            self.forecast_note.setText('Select a sequence.')
            return

        metrics = self._metrics_for(self.run_seconds())
        if metrics is None or not metrics['valid']:
            for card in (self.process_ct_card, self.output_ct_card, self.uph_card, self.output_process_card):
                card.set_value('-')
            self.sequence_note.setText('Add one INPUT and one OUTPUT marker in Sequence to calculate production metrics.')
            self.forecast_note.setText('Production metrics are not ready.')
            return

        if self.variance_enabled.isChecked():
            self.process_ct_card.set_value(f"{metrics['expected_process_ct']:.2f} s")
            self.output_ct_card.set_value(f"{metrics['expected_output_ct']:.2f} s")
            self.uph_card.set_value(f"{metrics['uph']:.1f}")
            self.output_process_card.set_value(self._format_quantity(metrics['output_per_process']))
            self.sequence_note.setText(
                f"Variance enabled: uniform random CT from {metrics['ct_min']:.2f}s to {metrics['ct_max']:.2f}s per process/index. "
                f"Movement portion stays based on the sequence motion time of {metrics['nominal_move_ct']:.2f}s."
            )
        else:
            self.process_ct_card.set_value(f"{metrics['average_process_ct']:.2f} s")
            self.output_ct_card.set_value(f"{metrics['average_output_ct']:.2f} s")
            self.uph_card.set_value(f"{metrics['uph']:.1f}")
            self.output_process_card.set_value(self._format_quantity(metrics['output_per_process']))
            self.sequence_note.setText(
                f"Full sequence/revolution: {metrics['production_ct']:.2f}s | {metrics['processes_per_window']} process/index cycles | {metrics['output_qty_per_cycle']} output units."
            )

        self._refresh_forecast()

    def _refresh_forecast(self):
        target = self.run_seconds()
        if target <= 0:
            self.forecast_note.setText('Set Hours / Minutes / Seconds greater than 0.')
            return
        metrics = self._metrics_for(target)
        if metrics is None or not metrics['valid']:
            self.forecast_note.setText('Production metrics are not ready.')
            return
        if self.variance_enabled.isChecked():
            self.forecast_note.setText(
                'SELECTED RUN FORECAST\n'
                f"Runtime: {self._format_hms(target)}\n"
                f"CT variance: {metrics['ct_min']:.2f}s to {metrics['ct_max']:.2f}s per process\n"
                f"Expected average process CT: {metrics['expected_process_ct']:.2f}s\n"
                f"Completed process/index cycles: {metrics['completed_processes']}\n"
                f"Projected output: {self._format_quantity(metrics['projected_output'])}\n"
                f"Effective UPH at this exact stop time: {metrics['effective_uph']:.1f}"
            )
        else:
            self.forecast_note.setText(
                'SELECTED RUN FORECAST\n'
                f"Runtime: {self._format_hms(target)}\n"
                f"Completed process/index cycles: {metrics['completed_processes']}\n"
                f"Projected output: {self._format_quantity(metrics['projected_output'])}\n"
                f"Effective UPH at this exact stop time: {metrics['effective_uph']:.1f}"
            )

    def _run(self):
        sequence_id = self.selected_sequence_id()
        target = self.run_seconds()
        if not sequence_id:
            return
        if target <= 0:
            self.forecast_note.setText('Runtime must be greater than 0 seconds.')
            return
        enabled, ct_min, ct_max = self.variance_settings()
        self.runRequested.emit(sequence_id, target, enabled, ct_min, ct_max)

    def _skip(self):
        sequence_id = self.selected_sequence_id()
        target = self.run_seconds()
        if not sequence_id:
            return
        if target <= 0:
            self.forecast_note.setText('Runtime must be greater than 0 seconds.')
            return
        enabled, ct_min, ct_max = self.variance_settings()
        self.skipRequested.emit(sequence_id, target, enabled, ct_min, ct_max)

    def _set_live_result(self, elapsed):
        self.elapsed_card.set_value(self._format_hms(elapsed))
        metrics = self._metrics_for(elapsed)
        if metrics is None or not metrics['valid']:
            self.output_card.set_value('-')
            self.process_card.set_value('-')
            self.effective_uph_card.set_value('-')
            return
        self.output_card.set_value(self._format_quantity(metrics['projected_output']))
        self.process_card.set_value(metrics['completed_processes'])
        self.effective_uph_card.set_value(f"{metrics['effective_uph']:.1f}")

    def set_station_statuses(self, statuses):
        statuses = list(statuses or [])
        self.station_table.setRowCount(len(statuses))

        for row, info in enumerate(statuses):
            status = str(info.get("status", "READY")).upper()
            values = [
                str(info.get("name", "Process")),
                f"{float(info.get('setpoint', 0.0)):.1f} s",
                status,
                f"{float(info.get('elapsed', 0.0)):.1f} s",
            ]

            if status == "FINISHED":
                bg = QColor(22, 101, 52)
            elif status == "RUNNING":
                bg = QColor(31, 78, 121)
            else:
                bg = QColor(38, 50, 65)

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col >= 2:
                    item.setBackground(bg)
                self.station_table.setItem(row, col, item)

        self.station_table.resizeRowsToContents()

    def refresh(self, project, issues):
        new_identity = id(project)
        if new_identity != self._project_identity:
            self._project_identity = new_identity
            self._duration_initialized = False
        self._project = project
        current = self.selected_sequence_id()
        self._seq_ids = [sequence.id for sequence in project.sequences]
        self.sequence.blockSignals(True)
        self.sequence.clear()
        self.sequence.addItems([sequence.name for sequence in project.sequences])
        if current in self._seq_ids:
            self.sequence.setCurrentIndex(self._seq_ids.index(current))
        self.sequence.blockSignals(False)
        self.check.setText('READY TO RUN' if not issues else ('CONFIGURATION REQUIRED\n\n' + '\n'.join(f'• {issue}' for issue in issues)))
        self.sequence.setEnabled(bool(project.sequences))
        sequence = self._selected_sequence()
        if not self._duration_initialized and sequence is not None:
            self._set_duration_seconds(SequenceEvaluator.total_duration(sequence))
            self._duration_initialized = True
            self._apply_nominal_defaults()
        self._refresh_metrics()
        self._set_live_result(self._last_elapsed)

    def set_progress(self, elapsed, total):
        self._last_elapsed = max(0.0, float(elapsed))
        progress = 0 if total <= 0 else min(1000, int(elapsed / total * 1000))
        self.progress.setValue(progress)
        self.time.setText(f"{self._format_hms(elapsed)} / {self._format_hms(total)}")
        self._set_live_result(self._last_elapsed)
