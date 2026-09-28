from __future__ import annotations

from collections import OrderedDict
import math
import random

from app.models import MachineProject, MachineSequence


class SequenceEvaluator:
    """
    Pure machine-sequence evaluator.

    Execution rules:
    - Blocks execute in ascending block number.
    - Steps with the same block number execute in parallel.
    - A block duration is the longest timed step in that block.
    - INPUT and OUTPUT are zero-time production markers.
    - WAIT is real process time.
    """

    @staticmethod
    def blocks(sequence: MachineSequence):
        grouped = OrderedDict()

        for step in sequence.steps:
            grouped.setdefault(
                int(step.block),
                [],
            ).append(step)

        return [
            (block, grouped[block])
            for block in sorted(grouped)
        ]

    @staticmethod
    def step_duration(step) -> float:
        if step.kind in ("INPUT", "OUTPUT"):
            return 0.0

        return max(
            0.0,
            float(step.duration),
        )

    @staticmethod
    def block_duration(steps) -> float:
        return max(
            (
                SequenceEvaluator.step_duration(step)
                for step in steps
            ),
            default=0.0,
        )

    @staticmethod
    def timeline(sequence: MachineSequence):
        result = []
        cursor = 0.0

        for block, steps in SequenceEvaluator.blocks(sequence):
            duration = SequenceEvaluator.block_duration(
                steps
            )

            result.append(
                {
                    "block": int(block),
                    "steps": list(steps),
                    "start": cursor,
                    "duration": duration,
                    "end": cursor + duration,
                }
            )

            cursor += duration

        return result

    @staticmethod
    def total_duration(sequence: MachineSequence) -> float:
        timeline = SequenceEvaluator.timeline(
            sequence
        )

        if not timeline:
            return 0.0

        return float(
            timeline[-1]["end"]
        )

    @staticmethod
    def production_metrics(sequence: MachineSequence) -> dict:
        timeline = SequenceEvaluator.timeline(
            sequence
        )

        inputs = []
        outputs = []

        for block_info in timeline:
            for step in block_info["steps"]:
                if step.kind == "INPUT":
                    inputs.append(
                        (step, block_info)
                    )
                elif step.kind == "OUTPUT":
                    outputs.append(
                        (step, block_info)
                    )

        result = {
            "valid": False,
            "errors": [],
            "input_block": None,
            "output_block": None,
            "input_time": None,
            "output_time": None,
            "production_ct": 0.0,
            "uph": 0.0,
            "wait_process_time": 0.0,
            "motion_other_time": 0.0,
            "total_sequence_time": SequenceEvaluator.total_duration(
                sequence
            ),
            "output_qty_per_cycle": max(
                1,
                int(
                    getattr(
                        sequence,
                        "output_qty_per_cycle",
                        1,
                    )
                ),
            ),
        }

        if len(inputs) != 1:
            result["errors"].append(
                "Add exactly one INPUT marker."
            )

        if len(outputs) != 1:
            result["errors"].append(
                "Add exactly one OUTPUT marker."
            )

        if result["errors"]:
            return result

        _, input_info = inputs[0]
        _, output_info = outputs[0]

        input_time = float(
            input_info["start"]
        )
        output_time = float(
            output_info["start"]
        )

        result["input_block"] = int(
            input_info["block"]
        )
        result["output_block"] = int(
            output_info["block"]
        )
        result["input_time"] = input_time
        result["output_time"] = output_time

        if output_time <= input_time:
            result["errors"].append(
                "OUTPUT must occur after INPUT on the sequence timeline."
            )
            return result

        production_ct = (
            output_time
            - input_time
        )

        wait_process_time = 0.0

        for block_info in timeline:
            block_start = float(
                block_info["start"]
            )

            if not (
                input_time
                <= block_start
                < output_time
            ):
                continue

            wait_duration = max(
                (
                    SequenceEvaluator.step_duration(step)
                    for step in block_info["steps"]
                    if step.kind == "WAIT"
                ),
                default=0.0,
            )

            wait_process_time += min(
                wait_duration,
                float(block_info["duration"]),
            )

        qty = result[
            "output_qty_per_cycle"
        ]

        result.update(
            {
                "valid": True,
                "production_ct": production_ct,
                "uph": (
                    3600.0
                    / production_ct
                    * qty
                ),
                "wait_process_time": wait_process_time,
                "motion_other_time": max(
                    0.0,
                    production_ct
                    - wait_process_time,
                ),
            }
        )

        return result

    @staticmethod
    def _process_block_numbers(sequence: MachineSequence, base: dict | None = None) -> list[int]:
        if base is None:
            base = SequenceEvaluator.production_metrics(sequence)

        if not base.get("valid"):
            return []

        input_time = float(base["input_time"])
        output_time = float(base["output_time"])

        process_blocks = []
        for block_info in SequenceEvaluator.timeline(sequence):
            block_start = float(block_info["start"])
            if not (input_time <= block_start < output_time):
                continue
            if any(step.kind == "WAIT" for step in block_info["steps"]):
                process_blocks.append(int(block_info["block"]))
        return process_blocks

    @staticmethod
    def runtime_metrics(
        sequence: MachineSequence,
        run_seconds: float,
        variance_enabled: bool = False,
        ct_min: float | None = None,
        ct_max: float | None = None,
        seed: int | None = None,
    ) -> dict:
        base = SequenceEvaluator.production_metrics(sequence)
        run_seconds = max(0.0, float(run_seconds))

        result = dict(base)
        result.update(
            {
                "run_seconds": run_seconds,
                "processes_per_window": 0,
                "average_process_ct": 0.0,
                "average_output_ct": 0.0,
                "output_per_process": 0.0,
                "completed_processes": 0,
                "projected_output": 0.0,
                "effective_uph": 0.0,
                "nominal_wait_ct": 0.0,
                "nominal_move_ct": 0.0,
                "variance_enabled": bool(variance_enabled),
                "ct_min": 0.0,
                "ct_max": 0.0,
                "expected_process_ct": 0.0,
                "expected_output_ct": 0.0,
                "simulated_average_process_ct": 0.0,
                "simulated_average_output_ct": 0.0,
                "cycle_plan": [],
                "random_seed": 0,
            }
        )

        if not base["valid"]:
            return result

        process_blocks = SequenceEvaluator._process_block_numbers(sequence, base)
        process_count = max(1, len(process_blocks))
        production_ct = float(base["production_ct"])
        output_qty = float(base["output_qty_per_cycle"])

        average_process_ct = production_ct / process_count
        average_output_ct = (
            production_ct / output_qty if output_qty > 0 else 0.0
        )
        output_per_process = output_qty / process_count
        nominal_move_ct = max(0.0, float(base["motion_other_time"]) / process_count)
        nominal_wait_ct = max(0.0, average_process_ct - nominal_move_ct)

        low = average_process_ct
        high = average_process_ct

        if variance_enabled:
            low = average_process_ct if ct_min is None else float(ct_min)
            high = average_process_ct if ct_max is None else float(ct_max)
            if high < low:
                low, high = high, low
            low = max(low, nominal_move_ct + 0.001)
            high = max(high, low)

        if seed is None:
            seed = int(round(run_seconds * 1000.0)) ^ int(round(low * 1000.0)) ^ (int(round(high * 1000.0)) << 1) ^ (process_count << 8) ^ int(output_qty)

        rng = random.Random(seed)
        cycle_plan = []
        cumulative = 0.0
        max_cycles = max(1000, int(run_seconds / max(low, 0.001)) + process_count + 5)

        for idx in range(max_cycles):
            duration = rng.uniform(low, high) if variance_enabled else average_process_ct
            duration = max(duration, nominal_move_ct + 0.001)
            move = min(nominal_move_ct, duration)
            wait = max(0.0, duration - move)
            cycle_plan.append(
                {
                    "cycle_index": idx % process_count,
                    "duration": duration,
                    "wait": wait,
                    "move": move,
                }
            )
            cumulative += duration
            if cumulative >= run_seconds + high + 1e-9:
                break

        completed_processes = 0
        completed_durations = []
        elapsed_sum = 0.0
        for item in cycle_plan:
            if elapsed_sum + item["duration"] <= run_seconds + 1e-9:
                elapsed_sum += item["duration"]
                completed_processes += 1
                completed_durations.append(item["duration"])
            else:
                break

        projected_output = completed_processes * output_per_process
        effective_uph = projected_output / run_seconds * 3600.0 if run_seconds > 0 else 0.0

        expected_process_ct = (low + high) / 2.0
        expected_output_ct = expected_process_ct / output_per_process if output_per_process > 0 else 0.0
        simulated_average_process_ct = sum(completed_durations) / len(completed_durations) if completed_durations else expected_process_ct
        simulated_average_output_ct = simulated_average_process_ct / output_per_process if output_per_process > 0 else 0.0

        result.update(
            {
                "processes_per_window": process_count,
                "average_process_ct": average_process_ct,
                "average_output_ct": average_output_ct,
                "output_per_process": output_per_process,
                "completed_processes": completed_processes,
                "projected_output": projected_output,
                "effective_uph": effective_uph,
                "nominal_wait_ct": nominal_wait_ct,
                "nominal_move_ct": nominal_move_ct,
                "ct_min": low,
                "ct_max": high,
                "expected_process_ct": expected_process_ct,
                "expected_output_ct": expected_output_ct,
                "simulated_average_process_ct": simulated_average_process_ct,
                "simulated_average_output_ct": simulated_average_output_ct,
                "cycle_plan": cycle_plan,
                "random_seed": seed,
            }
        )

        if variance_enabled:
            result["uph"] = 3600.0 / expected_process_ct * output_per_process if expected_process_ct > 0 else 0.0

        return result

    @staticmethod
    def evaluate(
        project: MachineProject,
        sequence: MachineSequence,
        elapsed: float,
    ) -> dict[str, float]:
        values = {
            motion.id: 0.0
            for motion in project.motions
        }

        t = max(
            0.0,
            float(elapsed),
        )
        cursor = 0.0

        for _, steps in SequenceEvaluator.blocks(sequence):
            block_duration = (
                SequenceEvaluator.block_duration(
                    steps
                )
            )

            starts = values.copy()

            if t >= cursor + block_duration:
                for step in steps:
                    if (
                        step.kind == "MOTION"
                        and step.motion_id in values
                    ):
                        values[
                            step.motion_id
                        ] = (
                            1.0
                            if step.target == "END"
                            else 0.0
                        )

                cursor += block_duration
                continue

            local = max(
                0.0,
                t - cursor,
            )

            for step in steps:
                if (
                    step.kind != "MOTION"
                    or step.motion_id not in values
                ):
                    continue

                start = starts.get(
                    step.motion_id,
                    0.0,
                )
                target = (
                    1.0
                    if step.target == "END"
                    else 0.0
                )

                duration = max(
                    0.000001,
                    float(step.duration),
                )

                progress = min(
                    1.0,
                    local / duration,
                )

                values[
                    step.motion_id
                ] = (
                    start
                    + (target - start)
                    * progress
                )

            return values

        return values
