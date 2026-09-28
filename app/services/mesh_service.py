from pathlib import Path
import vtk


class MeshService:
    @staticmethod
    def mapper(path: Path):
        reader = vtk.vtkSTLReader()
        reader.SetFileName(str(path))
        reader.Update()
        if reader.GetOutput().GetNumberOfPoints() == 0:
            raise RuntimeError(f"Empty or unreadable mesh: {path}")

        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(reader.GetOutputPort())
        normals.SetFeatureAngle(55.0)
        normals.ConsistencyOn()
        normals.AutoOrientNormalsOn()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        return mapper
