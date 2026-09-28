from app.models import MachineProject


class ValidationService:
    @staticmethod
    def validate(project: MachineProject) -> list[str]:
        issues = []
        comp_ids = {x.id for x in project.components}
        inst_ids = {x.id for x in project.instances}
        motion_ids = {x.id for x in project.motions}

        if not project.components:
            issues.append("Import at least one STEP/STP component.")
        if not project.instances:
            issues.append("Add at least one component instance to the machine assembly.")
        for inst in project.instances:
            if inst.component_id not in comp_ids:
                issues.append(f"Assembly instance '{inst.name}' references a missing component.")
        if not project.motions:
            issues.append("Create at least one motion profile.")
        for motion in project.motions:
            if motion.instance_id not in inst_ids:
                issues.append(f"Motion '{motion.name}' references a missing assembly instance.")
        runnable = [s for s in project.sequences if s.steps]
        if not runnable:
            issues.append("Create a machine sequence with at least one step.")
        for seq in project.sequences:
            for step in seq.steps:
                if (
                    step.kind == "MOTION"
                    and step.motion_id not in motion_ids
                ):
                    issues.append(
                        f"Sequence '{seq.name}' contains a missing motion reference."
                    )
        for motion in project.motions:
            if (
                motion.motion_type == "PATH"
                and len(
                    getattr(
                        motion,
                        "path_points",
                        [],
                    )
                ) < 2
            ):
                issues.append(
                    f"PATH motion '{motion.name}' needs at least 2 path points."
                )

        for motion in project.motions:
            if motion.motion_type != "PATH":
                continue

            start_mode = str(
                getattr(
                    motion,
                    "path_start_mode",
                    "",
                )
                or ""
            ).upper()

            start_id = getattr(
                motion,
                "path_start_motion_id",
                "",
            )

            # Backward compatibility.
            if start_mode not in ("HOME", "CUSTOM", "CHAINED"):
                start_mode = (
                    "CHAINED"
                    if start_id
                    else "HOME"
                )

            if start_mode != "CHAINED":
                continue

            if not start_id:
                issues.append(
                    f"PATH motion '{motion.name}' is CHAINED but has no parent PATH."
                )
                continue

            start_motion = project.motion(
                start_id
            )

            if (
                start_motion is None
                or start_motion.motion_type != "PATH"
                or start_motion.instance_id != motion.instance_id
            ):
                issues.append(
                    f"PATH motion '{motion.name}' has an invalid start PATH."
                )
                continue

            visited = {motion.id}
            current_id = start_id

            while current_id:
                if current_id in visited:
                    issues.append(
                        f"PATH motion '{motion.name}' contains a circular PATH dependency."
                    )
                    break

                visited.add(current_id)
                current = project.motion(
                    current_id
                )

                if current is None:
                    break

                current_id = getattr(
                    current,
                    "path_start_motion_id",
                    "",
                )
        return issues
