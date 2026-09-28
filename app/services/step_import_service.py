from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from app.constants import SUPPORTED_STEP_EXTENSIONS
from app.models import ComponentDefinition, new_id


class StepImportError(RuntimeError):
    pass


class StepImportService:
    """STEP/STP is the only accepted mechanical component source in V10."""

    @staticmethod
    def import_component(source: Path, project_root: Path, display_name: str | None = None) -> ComponentDefinition:
        source = Path(source)
        if source.suffix.lower() not in SUPPORTED_STEP_EXTENSIONS:
            raise StepImportError("Only .STEP and .STP component files are accepted.")
        if not source.exists():
            raise StepImportError(f"STEP file does not exist: {source}")

        try:
            import cadquery as cq
            import vtk
        except Exception as exc:
            raise StepImportError(
                "STEP import requires CadQuery and VTK. Run: pip install -r requirements.txt"
            ) from exc

        comp_id = new_id("cmp")
        clean_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", source.stem).strip("_") or "component"
        ext = source.suffix.lower()
        component_dir = project_root / "components"
        cache_dir = project_root / "cache"
        component_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        step_target = component_dir / f"{comp_id}_{clean_stem}{ext}"
        mesh_target = cache_dir / f"{comp_id}.stl"
        shutil.copy2(source, step_target)

        with tempfile.TemporaryDirectory() as td:
            raw_stl = Path(td) / "raw.stl"
            try:
                model = cq.importers.importStep(str(step_target))
                cq.exporters.export(
                    model,
                    str(raw_stl),
                    tolerance=0.8,
                    angularTolerance=0.35,
                )
            except Exception as exc:
                step_target.unlink(missing_ok=True)
                raise StepImportError(f"Unable to convert STEP component: {exc}") from exc

            reader = vtk.vtkSTLReader()
            reader.SetFileName(str(raw_stl))
            reader.Update()
            poly = reader.GetOutput()
            if poly.GetNumberOfPoints() == 0:
                step_target.unlink(missing_ok=True)
                raise StepImportError("STEP conversion produced an empty mesh.")

            xmin, xmax, ymin, ymax, zmin, zmax = poly.GetBounds()
            center_x = (xmin + xmax) / 2.0
            center_z = (zmin + zmax) / 2.0
            # Standard V10 component origin: center X/Z and bottom Y=0.
            transform = vtk.vtkTransform()
            transform.Translate(-center_x, -ymin, -center_z)
            tf = vtk.vtkTransformPolyDataFilter()
            tf.SetInputData(poly)
            tf.SetTransform(transform)
            tf.Update()

            writer = vtk.vtkSTLWriter()
            writer.SetFileName(str(mesh_target))
            writer.SetInputData(tf.GetOutput())
            writer.SetFileTypeToBinary()
            if not writer.Write():
                step_target.unlink(missing_ok=True)
                raise StepImportError("Unable to write render mesh cache.")

            b = tf.GetOutput().GetBounds()
            dims = [b[1]-b[0], b[3]-b[2], b[5]-b[4]]

        return ComponentDefinition(
            id=comp_id,
            name=display_name or source.stem,
            step_file=str(step_target.relative_to(project_root)),
            mesh_file=str(mesh_target.relative_to(project_root)),
            source_name=source.name,
            dimensions=[round(float(v), 3) for v in dims],
        )
