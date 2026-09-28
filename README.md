# Digital Twin Machine Builder

A Python/PySide6/VTK industrial digital-twin and machine simulation platform for building machines from STEP/STP components, assembling them in 3D, defining motions and machine sequences, and evaluating production performance such as cycle time and UPH.

**Current version: V10.5.3**

## What it does

- Import STEP/STP mechanical components.
- Assemble a complete machine in a 3D workspace.
- Drag, zoom, orbit, and numerically align components.
- Define `LINEAR`, `ROTARY`, and waypoint-based `PATH` motions.
- Chain PATH motions or start them from custom 3D positions.
- Build machine sequences with `INPUT`, `OUTPUT`, `WAIT`, and `MOTION` steps.
- Execute same-block steps in parallel.
- Calculate production CT, average process/index CT, average CT per output, WIP-oriented throughput, and UPH.
- Run production simulations for a selected duration in hours/minutes/seconds.
- Add CT variance ranges and instantly calculate long runs with **SKIP TO END**.
- Display live station process status (`RUNNING` / `FINISHED`) from sequence labels.
- Simulate indexed multi-carrier conveyor behavior and PCB load/unload state.

### PCB state

The current V10.5.3 runtime models load/unload explicitly:

## Architecture

```text
main.py
app/
├── controllers/     runtime sequence player
├── models/          machine/project data models
├── pages/           Dashboard, Components, Assembly, Motion, Sequence, Digital Twin
├── services/        project, STEP import, mesh, path and validation services
├── simulation/      sequence / production metric engine
├── views/           VTK 3D machine workspace
└── widgets/         reusable Qt widgets

tests/               unit tests for project, sequence, path, CT/UPH and production logic
workspace/           sample project and generated small PCB assets
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

## CAD assets

The public repository does **not** include the large source conveyor/jig STEP files or their generated STL caches. The sample `workspace/project.json` references these paths:

```text
workspace/components/conveyor.step
workspace/components/jig_carrier.step
workspace/cache/conveyor.stl
workspace/cache/jig_carrier.stl
```

Place your own matching files there, or use **Import STEP** inside the application and build a new project. The generated dummy PCB STEP/STL files are included because they are small and are part of the simulator demo.

## Main workflow

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

## Motion types

### LINEAR
Move along a configured axis.

### ROTARY
Rotate around a configured axis.

### PATH
Pick waypoints directly in the 3D viewer. PATH supports smoothing, chaining from another PATH endpoint, and a custom 3D start point.

## Sequence execution

Steps sharing the same block number execute in parallel. A block completes when its longest timed step is complete. This matches the indexed conveyor model where all stations work simultaneously and the slowest active station controls when the next index can occur.

## Production runtime

The Digital Twin page supports:

- Hours / Minutes / Seconds run target.
- CT variance Min/Max.
- Average process/index CT.
- Average CT per output.
- Output per process.
- Projected output.
- Effective UPH.
- Live elapsed time.
- **SKIP TO END** for instant long-run calculation.
- Live station completion status generated from Sequence `WAIT` labels.

## Tests

Run the test suite with:

```bash
python -m unittest discover -s tests
```

## Version history

See [`VERSION_HISTORY.txt`](VERSION_HISTORY.txt) for the full development history from V1 through V10.5.3.

## Repository status

This is an active engineering/R&D project. The current focus is industrial digital-twin workflow, indexed conveyor simulation, real process sequencing, and production-performance analysis.

No open-source license has been selected yet.
