from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any
import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class ComponentDefinition:
    id: str
    name: str
    step_file: str
    mesh_file: str
    source_name: str = ""
    dimensions: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])


@dataclass
class AssemblyInstance:
    id: str
    component_id: str
    name: str
    position: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    group: str = "Machine"
    visible: bool = True
    opacity: float = 1.0
    color: list[float] = field(
        default_factory=lambda: [0.66, 0.69, 0.74]
    )


@dataclass
class MotionProfile:
    id: str
    name: str
    instance_id: str
    motion_type: str = "LINEAR"       # LINEAR / ROTARY / PATH
    coordinate: str = "LOCAL"         # LOCAL / GLOBAL
    axis: str = "Y"                   # X / Y / Z
    home: float = 0.0
    end: float = 50.0
    duration: float = 1.0
    enabled: bool = True
    path_points: list[list[float]] = field(default_factory=list)
    path_smooth: bool = True
    follow_path_heading: bool = True
    path_start_mode: str = "HOME"  # HOME / CUSTOM / CHAINED
    path_start_motion_id: str = ""
    path_start_offset: list[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )


@dataclass
class SequenceStep:
    id: str
    block: int
    kind: str = "MOTION"               # MOTION / WAIT / INPUT / OUTPUT
    motion_id: str = ""
    target: str = "END"                # END / HOME
    duration: float = 1.0
    label: str = ""


@dataclass
class MachineSequence:
    id: str
    name: str
    output_qty_per_cycle: int = 1
    steps: list[SequenceStep] = field(default_factory=list)


@dataclass
class MachineProject:
    version: str = "10.5.3"
    name: str = "New Digital Twin Project"
    units: str = "mm"
    components: list[ComponentDefinition] = field(default_factory=list)
    instances: list[AssemblyInstance] = field(default_factory=list)
    motions: list[MotionProfile] = field(default_factory=list)
    sequences: list[MachineSequence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _filtered_kwargs(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """
        Keep only fields supported by the target dataclass.

        This makes Open Project tolerant of newer project files that may
        contain extra metadata fields.
        """
        allowed = {
            item.name
            for item in fields(cls)
        }
        return {
            key: value
            for key, value in raw.items()
            if key in allowed
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MachineProject":
        project = MachineProject(
            version=str(data.get("version", "10.0")),
            name=str(data.get("name", "Digital Twin Project")),
            units=str(data.get("units", "mm")),
        )

        project.components = [
            ComponentDefinition(
                **MachineProject._filtered_kwargs(
                    ComponentDefinition,
                    item,
                )
            )
            for item in data.get("components", [])
        ]

        project.instances = [
            AssemblyInstance(
                **MachineProject._filtered_kwargs(
                    AssemblyInstance,
                    item,
                )
            )
            for item in data.get("instances", [])
        ]

        project.motions = [
            MotionProfile(
                **MachineProject._filtered_kwargs(
                    MotionProfile,
                    item,
                )
            )
            for item in data.get("motions", [])
        ]

        project.sequences = []
        for raw_sequence in data.get("sequences", []):
            sequence_kwargs = MachineProject._filtered_kwargs(
                MachineSequence,
                raw_sequence,
            )
            sequence_kwargs["output_qty_per_cycle"] = max(
                1,
                int(
                    raw_sequence.get(
                        "output_qty_per_cycle",
                        1,
                    )
                ),
            )
            sequence_kwargs["steps"] = [
                SequenceStep(
                    **MachineProject._filtered_kwargs(
                        SequenceStep,
                        raw_step,
                    )
                )
                for raw_step in raw_sequence.get("steps", [])
            ]
            project.sequences.append(
                MachineSequence(**sequence_kwargs)
            )

        return project

    def component(self, component_id: str):
        return next((x for x in self.components if x.id == component_id), None)

    def instance(self, instance_id: str):
        return next((x for x in self.instances if x.id == instance_id), None)

    def motion(self, motion_id: str):
        return next((x for x in self.motions if x.id == motion_id), None)

    def sequence(self, sequence_id: str):
        return next((x for x in self.sequences if x.id == sequence_id), None)
