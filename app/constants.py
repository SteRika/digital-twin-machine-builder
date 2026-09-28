from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = APP_ROOT / "workspace"
PROJECT_FILE_NAME = "project.json"
TIMER_INTERVAL_MS = 30
PROJECT_VERSION = "10.5.3"
SUPPORTED_STEP_EXTENSIONS = {".step", ".stp"}

COMPONENT_MIME_TYPE = "application/x-digital-twin-step-component"
ASSEMBLY_SNAP_DEFAULT_MM = 5.0

# Camera dolly factor used by mouse wheel / zoom toolbar buttons.
ASSEMBLY_ZOOM_FACTOR = 1.15

# Degrees of camera orbit per mouse pixel while MOVE PARTS is active.
ASSEMBLY_ORBIT_SENSITIVITY = 0.35
