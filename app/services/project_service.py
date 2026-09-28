from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.constants import PROJECT_FILE_NAME
from app.models import MachineProject


class ProjectService:
    @staticmethod
    def ensure_structure(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "components").mkdir(exist_ok=True)
        (root / "cache").mkdir(exist_ok=True)

    @staticmethod
    def save(root: Path, project: MachineProject) -> Path:
        ProjectService.ensure_structure(root)
        path = root / PROJECT_FILE_NAME
        path.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")
        return path

    @staticmethod
    def load(path_or_root: Path) -> tuple[Path, MachineProject]:
        path_or_root = Path(path_or_root)
        path = path_or_root / PROJECT_FILE_NAME if path_or_root.is_dir() else path_or_root
        data = json.loads(path.read_text(encoding="utf-8"))
        return path.parent, MachineProject.from_dict(data)

    @staticmethod
    def create(root: Path, name: str) -> MachineProject:
        ProjectService.ensure_structure(root)
        project = MachineProject(name=name)
        ProjectService.save(root, project)
        return project

    @staticmethod
    def clone(old_root: Path, new_root: Path, project: MachineProject) -> None:
        ProjectService.ensure_structure(new_root)
        for folder in ("components", "cache"):
            src = old_root / folder
            dst = new_root / folder
            if src.exists():
                shutil.copytree(src, dst, dirs_exist_ok=True)
        ProjectService.save(new_root, project)
