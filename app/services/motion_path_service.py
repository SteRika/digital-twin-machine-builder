from __future__ import annotations

import math


class MotionPathService:
    """Interpolation helpers for PATH motion profiles."""

    @staticmethod
    def _distance(a, b):
        return math.sqrt(
            sum(
                (float(b[i]) - float(a[i])) ** 2
                for i in range(3)
            )
        )

    @staticmethod
    def _normalize(v):
        length = math.sqrt(
            sum(float(x) ** 2 for x in v)
        )
        if length <= 1e-12:
            return [0.0, 0.0, 1.0]
        return [
            float(x) / length
            for x in v
        ]

    @staticmethod
    def _catmull_rom(p0, p1, p2, p3, t):
        t2 = t * t
        t3 = t2 * t
        result = []
        for i in range(3):
            value = 0.5 * (
                2.0 * p1[i]
                + (-p0[i] + p2[i]) * t
                + (
                    2.0 * p0[i]
                    - 5.0 * p1[i]
                    + 4.0 * p2[i]
                    - p3[i]
                ) * t2
                + (
                    -p0[i]
                    + 3.0 * p1[i]
                    - 3.0 * p2[i]
                    + p3[i]
                ) * t3
            )
            result.append(float(value))
        return result

    @staticmethod
    def dense_points(points, smooth=True, samples_per_segment=24):
        clean = [
            [float(v) for v in point[:3]]
            for point in (points or [])
            if len(point) >= 3
        ]

        if len(clean) <= 1:
            return clean

        if not smooth or len(clean) < 3:
            return clean

        dense = []

        for i in range(len(clean) - 1):
            p0 = clean[max(0, i - 1)]
            p1 = clean[i]
            p2 = clean[i + 1]
            p3 = clean[min(len(clean) - 1, i + 2)]

            count = max(
                4,
                int(samples_per_segment),
            )

            for sample_index in range(count):
                t = sample_index / float(count)

                if i > 0 and sample_index == 0:
                    continue

                dense.append(
                    MotionPathService._catmull_rom(
                        p0,
                        p1,
                        p2,
                        p3,
                        t,
                    )
                )

        dense.append(clean[-1])
        return dense

    @staticmethod
    def sample(points, fraction, smooth=True):
        """
        Return (position, tangent) at an arc-length normalized fraction.
        """
        dense = MotionPathService.dense_points(
            points,
            smooth=smooth,
        )

        if not dense:
            return (
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
            )

        if len(dense) == 1:
            return (
                list(dense[0]),
                [0.0, 0.0, 1.0],
            )

        cumulative = [0.0]
        for i in range(1, len(dense)):
            cumulative.append(
                cumulative[-1]
                + MotionPathService._distance(
                    dense[i - 1],
                    dense[i],
                )
            )

        total = cumulative[-1]

        if total <= 1e-12:
            return (
                list(dense[0]),
                [0.0, 0.0, 1.0],
            )

        f = max(
            0.0,
            min(
                1.0,
                float(fraction),
            ),
        )
        target = total * f

        segment_index = len(dense) - 2

        for i in range(len(dense) - 1):
            if cumulative[i + 1] >= target:
                segment_index = i
                break

        a = dense[segment_index]
        b = dense[segment_index + 1]

        segment_length = (
            cumulative[segment_index + 1]
            - cumulative[segment_index]
        )

        local = (
            0.0
            if segment_length <= 1e-12
            else (
                target
                - cumulative[segment_index]
            )
            / segment_length
        )

        position = [
            a[i]
            + (b[i] - a[i]) * local
            for i in range(3)
        ]

        tangent = MotionPathService._normalize(
            [
                b[i] - a[i]
                for i in range(3)
            ]
        )

        return position, tangent

    @staticmethod
    def chained_endpoint(project, motion_id, visited=None):
        """
        Return cumulative XYZ offset at the END of a chained PATH motion.

        A PATH profile stores only its own local displacement. If Path B starts
        from Path A, Path B's anchor is the cumulative endpoint of Path A.
        """
        if not motion_id:
            return [0.0, 0.0, 0.0]

        if visited is None:
            visited = set()

        if motion_id in visited:
            return [0.0, 0.0, 0.0]

        visited = set(visited)
        visited.add(motion_id)

        motion = project.motion(motion_id) if project is not None else None

        if motion is None or getattr(motion, "motion_type", "") != "PATH":
            return [0.0, 0.0, 0.0]

        anchor = MotionPathService.chained_endpoint(
            project,
            getattr(motion, "path_start_motion_id", ""),
            visited,
        )

        endpoint, _ = MotionPathService.sample(
            getattr(motion, "path_points", []),
            1.0,
            smooth=bool(
                getattr(
                    motion,
                    "path_smooth",
                    True,
                )
            ),
        )

        return [
            float(anchor[i]) + float(endpoint[i])
            for i in range(3)
        ]

    @staticmethod
    def ancestor_motion_ids(project, motion_id):
        result = []
        visited = set()

        current = project.motion(motion_id) if project is not None else None
        current_id = (
            getattr(current, "path_start_motion_id", "")
            if current is not None
            else ""
        )

        while current_id and current_id not in visited:
            visited.add(current_id)
            motion = project.motion(current_id)

            if motion is None or getattr(motion, "motion_type", "") != "PATH":
                break

            result.append(current_id)
            current_id = getattr(
                motion,
                "path_start_motion_id",
                "",
            )

        result.reverse()
        return result

    @staticmethod
    def depends_on(project, motion_id, possible_ancestor_id):
        if not motion_id or not possible_ancestor_id:
            return False

        return possible_ancestor_id in MotionPathService.ancestor_motion_ids(
            project,
            motion_id,
        )

    @staticmethod
    def effective_anchor(project, motion, visited=None):
        if motion is None:
            return [0.0, 0.0, 0.0]

        mode = str(
            getattr(
                motion,
                "path_start_mode",
                "",
            )
            or ""
        ).upper()

        if mode not in ("HOME", "CUSTOM", "CHAINED"):
            if getattr(motion, "path_start_motion_id", ""):
                mode = "CHAINED"
            elif any(
                abs(float(v)) > 1e-9
                for v in getattr(
                    motion,
                    "path_start_offset",
                    [0.0, 0.0, 0.0],
                )
            ):
                mode = "CUSTOM"
            else:
                mode = "HOME"

        correction = [
            float(v)
            for v in getattr(
                motion,
                "path_start_offset",
                [0.0, 0.0, 0.0],
            )
        ][:3]

        while len(correction) < 3:
            correction.append(0.0)

        if mode == "CUSTOM":
            return correction

        if mode != "CHAINED":
            return [0.0, 0.0, 0.0]

        parent_id = getattr(
            motion,
            "path_start_motion_id",
            "",
        )

        if not parent_id:
            return correction

        if visited is None:
            visited = set()

        if motion.id in visited:
            return correction

        visited = set(visited)
        visited.add(motion.id)

        parent = (
            project.motion(parent_id)
            if project is not None
            else None
        )

        if parent is None:
            return correction

        parent_end = MotionPathService.absolute_pose(
            project,
            parent,
            1.0,
            visited=visited,
        )[0]

        return [
            float(parent_end[i])
            + correction[i]
            for i in range(3)
        ]

    @staticmethod
    def absolute_pose(
        project,
        motion,
        fraction,
        visited=None,
    ):
        if motion is None:
            return (
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
            )

        anchor = MotionPathService.effective_anchor(
            project,
            motion,
            visited=visited,
        )

        local_position, tangent = MotionPathService.sample(
            getattr(
                motion,
                "path_points",
                [],
            ),
            fraction,
            smooth=bool(
                getattr(
                    motion,
                    "path_smooth",
                    True,
                )
            ),
        )

        return (
            [
                anchor[i]
                + float(local_position[i])
                for i in range(3)
            ],
            tangent,
        )

    @staticmethod
    def select_runtime_path(project, motions, motion_state):
        candidates = []

        for order, motion in enumerate(motions):
            fraction = max(
                0.0,
                min(
                    1.0,
                    float(
                        motion_state.get(
                            motion.id,
                            0.0,
                        )
                    ),
                ),
            )

            if fraction <= 1e-9:
                continue

            active_rank = (
                1
                if fraction < 1.0 - 1e-9
                else 0
            )

            candidates.append(
                (
                    active_rank,
                    order,
                    motion,
                    fraction,
                )
            )

        if not candidates:
            return None, 0.0

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        _, _, motion, fraction = candidates[-1]
        return motion, fraction

    @staticmethod
    def heading_y_degrees(tangent):
        tangent = MotionPathService._normalize(
            tangent
        )
        return math.degrees(
            math.atan2(
                tangent[0],
                tangent[2],
            )
        )

    @staticmethod
    def shortest_angle_delta(current, reference):
        delta = float(current) - float(reference)
        while delta > 180.0:
            delta -= 360.0
        while delta < -180.0:
            delta += 360.0
        return delta
