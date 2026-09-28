# Digital Twin Machine Builder

A Python / PySide6 / VTK industrial digital-twin and production-simulation platform for building machines from STEP/STP components, assembling them in 3D, defining machine motion and process sequences, and evaluating cycle time, throughput, and production output.

**Current release: V10.5.3**

## Current DIGI production model

The bundled production logic represents a 12-carrier indexed conveyor with **2 PCB per loaded jig**.

| Station | Process time |
|---|---:|
| Input | 10.0 s |
| Pasting Tape | 10.7 s |
| NFC Init | 7.5 s |
| Gang Jig | 15.0 s |
| NG Pickup | 3.0 s |
| IDLE Station | 0.0 s |
| Output | 12.0 s |

All stations process in parallel. **Gang Jig (15.0 s)** is the bottleneck. With a **1.0 s synchronized conveyor index**, the steady-state output cycle is:

```text
15.0 s process bottleneck
+1.0 s synchronized index
=16.0 s / output cycle

2 PCB / output cycle
=450 PCB/hour steady-state
```

## V10.5.3 PCB state logic

The current runtime models the actual load/unload behavior instead of simply showing PCB on every jig.

```text
OUTPUT
PCB stays on the jig while the 12 s OUTPUT process is running.
When OUTPUT finishes and the index move begins -> PCB is removed.

RETURN SIDE
Jig remains empty.

INPUT
Jig remains empty while the 10 s INPUT process is running.
When INPUT finishes and the index move begins -> 2 new PCB are loaded.
```

This prevents PCB blinking or incorrectly reappearing on the empty return side.

## Core capabilities

- Import STEP/STP mechanical components.
- Assemble components in a 3D VTK workspace.
- Drag, zoom, orbit, and numerically align machine components.
- Define `LINEAR`, `ROTARY`, and waypoint-based `PATH` motions.
- Pick PATH waypoints directly in 3D.
- Chain PATH motions or use custom 3D PATH start positions.
- Build sequences using `INPUT`, `OUTPUT`, `WAIT`, and `MOTION` steps.
- Execute same-block operations in parallel.
- Calculate production CT, process/index CT, CT per output, projected output, and UPH.
- Configure runtime in Hours / Minutes / Seconds.
- Apply Min / Max CT variance.
- Use **SKIP TO END** for instant long-duration production calculation.
- Display live station status (`RUNNING` / `FINISHED`) from Sequence labels.
- Simulate synchronized multi-carrier indexed movement.
- Model PCB load/unload state through the production route.

## Workflow

```text
Import STEP / STP
        ↓
Component Library
        ↓
Assembly
        ↓
Motion Setup
        ↓
Machine Sequence
        ↓
Digital Twin Runtime
        ↓
CT / UPH / Production Analysis
```

## Project structure

```text
main.py
app/
├── controllers/     runtime sequence player
├── models/          project and machine data models
├── pages/           Dashboard, Components, Assembly, Motion, Sequence, Digital Twin
├── services/        project, STEP import, mesh, path and validation services
├── simulation/      sequence / production metric engine
├── views/           VTK 3D machine workspace
└── widgets/         reusable PySide6 widgets

tests/               regression tests
workspace/           project workspace / demo configuration
VERSION_HISTORY.txt  development history from V1 to V10.5.3
```

## Requirements

- Python 3.10+
- PySide6 6.7+
- VTK 9.3+
- CadQuery 2.5+

Install:

```bash
python -m pip install -r requirements.txt
```

Run:

```bash
python main.py
```

Run tests:

```bash
python -m unittest discover -s tests
```

The V10.5.3 source snapshot was regression-tested with **30 passing unit tests** before publication.

## CAD assets

The simulator is designed around STEP/STP source geometry. Large machine-specific conveyor and jig CAD files are intentionally excluded from the public repository through `.gitignore`:

```text
workspace/components/conveyor.step
workspace/components/jig_carrier.step
workspace/cache/conveyor.stl
workspace/cache/jig_carrier.stl
```

Use your own matching CAD files, or import STEP/STP components through the application. Small generated demo assets such as the dummy PCB may remain in the repository.

## Version history

See [VERSION_HISTORY.txt](VERSION_HISTORY.txt) for the complete development history from the first conveyor prototype through V10.5.3.

## Repository

https://github.com/SteRika/digital-twin-machine-builder

## Status

Active engineering / R&D project focused on industrial digital twins, indexed conveyor simulation, machine sequencing, and production-performance analysis.

No open-source license has been selected yet.
