import time

from PySide6.QtCore import QObject, QTimer, Signal

from app.constants import TIMER_INTERVAL_MS
from app.simulation import SequenceEvaluator


class SequencePlayer(QObject):
    stateChanged = Signal(dict)
    progressChanged = Signal(float, float)
    finished = Signal()
    statusChanged = Signal(str)
    stationStatusChanged = Signal(object)
    productionIndexChanged = Signal(int, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.timer = QTimer(self)
        self.timer.setInterval(TIMER_INTERVAL_MS)
        self.timer.timeout.connect(self._tick)

        self.project = None
        self.sequence = None
        self.started_at = None
        self.total = 0.0
        self.sequence_total = 0.0
        self.runtime_metrics = None

    @property
    def running(self):
        return self.timer.isActive()

    def play(self, project, sequence):
        sequence_total = SequenceEvaluator.total_duration(sequence) if sequence is not None else 0.0
        self.play_for(project, sequence, sequence_total)

    def play_for(self, project, sequence, target_seconds, variance_enabled=False, ct_min=None, ct_max=None):
        if sequence is None or not sequence.steps:
            self.statusChanged.emit('Sequence has no steps.')
            return

        self.stop(reset=False)
        self.project = project
        self.sequence = sequence
        self.sequence_total = SequenceEvaluator.total_duration(sequence)
        self.total = max(0.0, float(target_seconds))

        if self.sequence_total <= 0 or self.total <= 0:
            self.statusChanged.emit('Run duration must be greater than 0 seconds.')
            return

        self.runtime_metrics = SequenceEvaluator.runtime_metrics(
            sequence,
            self.total,
            variance_enabled=variance_enabled,
            ct_min=ct_min,
            ct_max=ct_max,
        )

        reset_state = {motion.id: 0.0 for motion in project.motions}
        self._emit_runtime_indicators(0.0)
        self.stateChanged.emit(reset_state)
        self.progressChanged.emit(0.0, self.total)
        self.started_at = time.monotonic()

        m = self.runtime_metrics
        if m['valid']:
            if variance_enabled:
                self.statusChanged.emit(
                    f"Production run started: {sequence.name} | CT variance {m['ct_min']:.2f}-{m['ct_max']:.2f}s | Avg Process CT {m['expected_process_ct']:.2f}s | Target Output {m['projected_output']:.0f}"
                )
            else:
                self.statusChanged.emit(
                    f"Production run started: {sequence.name} | Process CT {m['average_process_ct']:.2f}s | Avg Output CT {m['average_output_ct']:.2f}s | Target Output {m['projected_output']:.0f}"
                )
        else:
            self.statusChanged.emit(f'Running sequence: {sequence.name}')

        self.timer.start()
        self._tick()

    def stop(self, reset=False):
        self.timer.stop()
        if reset and self.project is not None:
            state = {motion.id: 0.0 for motion in self.project.motions}
            self.stateChanged.emit(state)
            self.progressChanged.emit(0.0, self.total)
        self.started_at = None

    def reset(self, project):
        self.project = project
        self.productionIndexChanged.emit(
            0,
            "RESET",
            0.0,
        )
        self.stop(reset=True)
        self.sequence = None
        self.total = 0.0
        self.sequence_total = 0.0
        self.runtime_metrics = None
        self.stationStatusChanged.emit([])

    def _state_at_run_time(self, run_elapsed):
        if self.project is None or self.sequence is None:
            return {}

        m = self.runtime_metrics or {}
        plan = list(m.get('cycle_plan', []))
        if not plan:
            return SequenceEvaluator.evaluate(self.project, self.sequence, 0.0)

        nominal_process_ct = float(m.get('average_process_ct', 0.0))
        nominal_wait_ct = float(m.get('nominal_wait_ct', 0.0))
        nominal_move_ct = float(m.get('nominal_move_ct', 0.0))

        elapsed = max(0.0, float(run_elapsed))
        cumulative = 0.0
        for item in plan:
            duration = float(item['duration'])
            wait = float(item['wait'])
            move = float(item['move'])
            cycle_index = int(item['cycle_index'])
            seq_base = cycle_index * nominal_process_ct

            if elapsed >= cumulative + duration - 1e-9:
                cumulative += duration
                continue

            local = max(0.0, elapsed - cumulative)
            if local <= wait or move <= 1e-9:
                if wait > 1e-9 and nominal_wait_ct > 0.0:
                    seq_elapsed = seq_base + min(nominal_wait_ct, nominal_wait_ct * (local / wait))
                else:
                    seq_elapsed = seq_base
            else:
                move_progress = min(1.0, (local - wait) / move)
                seq_elapsed = seq_base + nominal_wait_ct + move_progress * nominal_move_ct

            return SequenceEvaluator.evaluate(self.project, self.sequence, seq_elapsed)

        return SequenceEvaluator.evaluate(self.project, self.sequence, self.sequence_total)

    def _runtime_position(self, run_elapsed):
        metrics = self.runtime_metrics or {}
        plan = list(
            metrics.get(
                "cycle_plan",
                [],
            )
        )

        elapsed = max(
            0.0,
            float(run_elapsed),
        )

        if not plan:
            return {
                "completed_moves": 0,
                "cycle_index": 0,
                "phase": "PROCESS",
                "phase_progress": 0.0,
                "local": 0.0,
                "wait": 0.0,
                "move": 0.0,
            }

        cumulative = 0.0

        for absolute_index, item in enumerate(plan):
            duration = float(
                item["duration"]
            )

            if elapsed >= cumulative + duration - 1e-9:
                cumulative += duration
                continue

            local = max(
                0.0,
                elapsed - cumulative,
            )

            wait = max(
                0.0,
                float(item["wait"]),
            )
            move = max(
                0.0,
                float(item["move"]),
            )

            if local < wait - 1e-9:
                phase = "PROCESS"
                phase_progress = (
                    local / wait
                    if wait > 1e-9
                    else 1.0
                )
            else:
                phase = "MOVE"
                move_local = max(
                    0.0,
                    local - wait,
                )
                phase_progress = (
                    min(
                        1.0,
                        move_local / move,
                    )
                    if move > 1e-9
                    else 1.0
                )

            return {
                "completed_moves": absolute_index,
                "cycle_index": int(
                    item["cycle_index"]
                ),
                "phase": phase,
                "phase_progress": phase_progress,
                "local": local,
                "wait": wait,
                "move": move,
            }

        return {
            "completed_moves": len(plan),
            "cycle_index": 0,
            "phase": "COMPLETE",
            "phase_progress": 1.0,
            "local": 0.0,
            "wait": 0.0,
            "move": 0.0,
        }

    def _station_status_at_run_time(self, run_elapsed):
        if (
            self.sequence is None
            or self.runtime_metrics is None
        ):
            return []

        position = self._runtime_position(
            run_elapsed
        )

        process_blocks = (
            SequenceEvaluator._process_block_numbers(
                self.sequence
            )
        )

        if not process_blocks:
            return []

        cycle_index = (
            position["cycle_index"]
            % len(process_blocks)
        )
        target_block = process_blocks[
            cycle_index
        ]

        block_steps = []
        for block, steps in SequenceEvaluator.blocks(
            self.sequence
        ):
            if int(block) == int(target_block):
                block_steps = [
                    step
                    for step in steps
                    if step.kind == "WAIT"
                ]
                break

        nominal_wait = max(
            0.0,
            float(
                self.runtime_metrics.get(
                    "nominal_wait_ct",
                    0.0,
                )
            ),
        )

        actual_wait = max(
            0.0,
            float(
                position.get(
                    "wait",
                    nominal_wait,
                )
            ),
        )

        statuses = []

        for step in block_steps:
            setpoint = max(
                0.0,
                float(step.duration),
            )

            if nominal_wait > 1e-9:
                scaled_finish = (
                    setpoint
                    * actual_wait
                    / nominal_wait
                )
            else:
                scaled_finish = setpoint

            if position["phase"] == "MOVE":
                status = "FINISHED"
                elapsed = scaled_finish

            elif position["phase"] == "COMPLETE":
                status = "FINISHED"
                elapsed = scaled_finish

            else:
                process_elapsed = min(
                    float(position["local"]),
                    actual_wait,
                )

                if setpoint <= 1e-9:
                    status = "FINISHED"
                    elapsed = 0.0
                elif process_elapsed + 1e-9 >= scaled_finish:
                    status = "FINISHED"
                    elapsed = scaled_finish
                else:
                    status = "RUNNING"
                    elapsed = process_elapsed

            statuses.append(
                {
                    "name": (
                        step.label.strip()
                        or "Process"
                    ),
                    "setpoint": setpoint,
                    "status": status,
                    "elapsed": elapsed,
                    "cycle_index": (
                        position["completed_moves"]
                        + 1
                    ),
                    "phase": position["phase"],
                }
            )

        return statuses

    def _emit_runtime_indicators(self, run_elapsed):
        position = self._runtime_position(
            run_elapsed
        )

        self.productionIndexChanged.emit(
            int(
                position["completed_moves"]
            ),
            str(
                position["phase"]
            ),
            float(
                position["phase_progress"]
            ),
        )

        self.stationStatusChanged.emit(
            self._station_status_at_run_time(
                run_elapsed
            )
        )

    def skip_to_end(self):
        if self.project is None or self.sequence is None or self.total <= 0:
            return
        self.timer.stop()
        state = self._state_at_run_time(self.total)
        self._emit_runtime_indicators(self.total)
        self.stateChanged.emit(state)
        self.progressChanged.emit(self.total, self.total)
        self.started_at = None
        m = self.runtime_metrics or {}
        self.statusChanged.emit(
            'Time Skip complete | '
            f"Output {m.get('projected_output',0):.0f} | "
            f"Processes {m.get('completed_processes',0)} | "
            f"Effective UPH {m.get('effective_uph',0.0):.1f}"
        )
        self.finished.emit()

    def _tick(self):
        if self.started_at is None or self.project is None or self.sequence is None:
            return
        elapsed = time.monotonic() - self.started_at
        clamped_elapsed = min(elapsed, self.total)
        state = self._state_at_run_time(clamped_elapsed)
        self._emit_runtime_indicators(
            clamped_elapsed
        )
        self.stateChanged.emit(state)
        self.progressChanged.emit(clamped_elapsed, self.total)
        if elapsed >= self.total:
            self.timer.stop()
            self.started_at = None
            m = self.runtime_metrics or {}
            self.statusChanged.emit(
                f"Production run complete: {self.sequence.name} | Output {m.get('projected_output',0):.0f} | Processes {m.get('completed_processes',0)} | Effective UPH {m.get('effective_uph',0.0):.1f}"
            )
            self.finished.emit()
