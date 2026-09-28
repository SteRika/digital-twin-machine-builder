from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QToolBar, QVBoxLayout, QWidget
)

from app.constants import DEFAULT_WORKSPACE
from app.controllers import SequencePlayer
from app.models import AssemblyInstance, MachineSequence, MotionProfile, SequenceStep, new_id
from app.pages import AssemblyPage, ComponentsPage, DashboardPage, DigitalTwinPage, MotionPage, SequencePage
from app.services import MotionPathService, ProjectService, StepImportError, StepImportService, ValidationService
from app.views import MachineView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Twin Machine Builder V10.5.3 — Stable Input/Output PCB Logic")
        self.resize(1880, 1050)
        self.project_root, self.project = ProjectService.load(DEFAULT_WORKSPACE)
        self.selected_instance_id = self.project.instances[0].id if self.project.instances else ""
        self.selected_motion_id = self.project.motions[0].id if self.project.motions else ""

        self.player = SequencePlayer(self)
        self.player.stateChanged.connect(self._motion_state_changed)
        self.player.progressChanged.connect(self._progress_changed)
        self.player.statusChanged.connect(self.statusBar().showMessage)
        self.player.finished.connect(self._player_finished)

        self._build_toolbar(); self._build_ui(); self._apply_style(); self._wire_pages()
        self.player.stationStatusChanged.connect(
            self.digital.set_station_statuses
        )
        self.player.productionIndexChanged.connect(
            self.viewer.set_production_index
        )
        self._refresh_all(reset_camera=True)
        self.viewer.set_production_index(
            0,
            "PROCESS",
            0.0,
        )
        self.statusBar().showMessage("V10.5.2 ready — PCB loads only at INPUT and unloads only at OUTPUT with stable return-side visibility.")

    def _build_toolbar(self):
        tb=QToolBar("Project",self); tb.setMovable(False); self.addToolBar(tb)
        for text,fn in [("New Project",self._new_project),("Open Project",self._open_project),("Save",self._save_project),("Save As",self._save_as),("Import STEP",self._import_step)]:
            b=QPushButton(text); b.clicked.connect(fn); tb.addWidget(b)
        tb.addSeparator(); self.project_label=QLabel(); tb.addWidget(self.project_label)

    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root); outer=QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(190); sl=QVBoxLayout(sidebar); sl.setContentsMargins(10,14,10,14)
        brand=QLabel("DIGITAL TWIN\nMACHINE BUILDER"); brand.setObjectName("brand"); sl.addWidget(brand)
        self.nav=[]; names=["Dashboard","Components","Assembly","Motion Setup","Sequence","Digital Twin"]
        for i,n in enumerate(names):
            b=QPushButton(n); b.setCheckable(True); b.clicked.connect(lambda checked,idx=i:self._navigate(idx)); sl.addWidget(b); self.nav.append(b)
        sl.addStretch(); io=QPushButton("I/O  (V10.1)"); io.setEnabled(False); sl.addWidget(io); outer.addWidget(sidebar)

        self.stack=QStackedWidget(); self.stack.setFixedWidth(520)
        self.dashboard=DashboardPage(); self.components=ComponentsPage(); self.assembly=AssemblyPage(); self.motion=MotionPage(); self.sequence=SequencePage(); self.digital=DigitalTwinPage()
        for p in (self.dashboard,self.components,self.assembly,self.motion,self.sequence,self.digital):self.stack.addWidget(p)
        outer.addWidget(self.stack)

        right=QFrame(); right.setObjectName("viewerPanel"); rl=QVBoxLayout(right); rl.setContentsMargins(8,8,8,8)

        # IMPORTANT: create the VTK viewer before wiring any toolbar button
        # to self.viewer methods.
        self.viewer=MachineView()

        cam=QHBoxLayout(); title=QLabel("3D MACHINE WORKSPACE"); title.setObjectName("viewerTitle"); cam.addWidget(title); cam.addStretch()

        self.move_parts_button=QPushButton("MOVE PARTS")
        self.move_parts_button.setCheckable(True)
        self.move_parts_button.setEnabled(False)
        self.move_parts_button.toggled.connect(self._toggle_move_parts)
        cam.addWidget(self.move_parts_button)

        zoom_in_button=QPushButton("ZOOM +")
        zoom_in_button.setToolTip(
            "Zoom in. Mouse wheel also works while MOVE PARTS is enabled."
        )
        zoom_in_button.clicked.connect(
            self.viewer.zoom_in
        )
        cam.addWidget(zoom_in_button)

        zoom_out_button=QPushButton("ZOOM −")
        zoom_out_button.setToolTip(
            "Zoom out. Mouse wheel also works while MOVE PARTS is enabled."
        )
        zoom_out_button.clicked.connect(
            self.viewer.zoom_out
        )
        cam.addWidget(zoom_out_button)

        for text,fn in [("ISO",lambda:self.viewer.reset_camera()),("TOP",lambda:self.viewer.camera_top()),("FRONT",lambda:self.viewer.camera_front())]:
            b=QPushButton(text); b.clicked.connect(fn); cam.addWidget(b)

        rl.addLayout(cam); rl.addWidget(self.viewer,1); outer.addWidget(right,1)
        self._navigate(0)

    def _wire_pages(self):
        self.components.importRequested.connect(self._import_step); self.components.addRequested.connect(self._add_component_instance); self.components.removeRequested.connect(self._remove_component)
        self.assembly.selectionChanged.connect(self._select_instance); self.assembly.transformChanged.connect(self._apply_transform); self.assembly.duplicateRequested.connect(self._duplicate_instance); self.assembly.deleteRequested.connect(self._delete_instance)
        self.assembly.componentAddRequested.connect(self._add_component_instance)
        self.assembly.addMotionRequested.connect(self._new_motion_for_instance)
        self.assembly.snapChanged.connect(self.viewer.set_snap_size)

        self.viewer.instanceSelected.connect(self._select_instance)
        self.viewer.componentDropped.connect(self._drop_component_instance)
        self.viewer.instancePositionChanged.connect(self._instance_position_dragged)
        self.motion.saveRequested.connect(self._save_motion); self.motion.deleteRequested.connect(self._delete_motion); self.motion.previewRequested.connect(self._preview_motion); self.motion.testRequested.connect(self._test_motion)
        self.motion.pathPickRequested.connect(self._path_pick_requested)
        self.motion.pathStartPickRequested.connect(self._path_start_pick_requested)
        self.motion.pathPreviewChanged.connect(self._path_preview_changed)
        self.viewer.pathPointPicked.connect(self._path_point_picked)
        self.viewer.pathStartPointPicked.connect(self._path_start_point_picked)
        self.sequence.newSequenceRequested.connect(self._new_sequence); self.sequence.deleteSequenceRequested.connect(self._delete_sequence); self.sequence.addStepRequested.connect(self._add_sequence_step); self.sequence.updateStepRequested.connect(self._update_sequence_step); self.sequence.deleteStepRequested.connect(self._delete_sequence_step); self.sequence.moveStepRequested.connect(self._move_sequence_step); self.sequence.playRequested.connect(self._play_sequence); self.sequence.stopRequested.connect(self._stop_player); self.sequence.settingsChanged.connect(self._sequence_settings_changed)
        self.digital.runRequested.connect(self._run_digital_twin)
        self.digital.skipRequested.connect(self._skip_digital_twin)
        self.digital.stopRequested.connect(self._stop_player)
        self.digital.resetRequested.connect(self._reset_runtime)

    def _navigate(self,index):
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        self.stack.setCurrentIndex(index)
        assembly_page = index == 2

        if assembly_page:
            # Assembly is an editing workspace. Reset runtime motion offsets.
            self.motion.stop_path_pick()
            self.viewer.set_path_pick_mode(False)
            self.viewer.set_path_start_pick_mode(False)
            self.viewer.clear_path_preview()
            self.viewer.apply_motion_state({})
            self.viewer.set_snap_size(
                self.assembly.snap_value()
            )
            self.move_parts_button.setChecked(True)
        else:
            self.move_parts_button.setChecked(False)
            self.viewer.set_assembly_edit_mode(False)

            if index == 3:
                self.motion.show_current_path_preview()
            else:
                self.motion.stop_path_pick()
                self.viewer.set_path_pick_mode(False)
                self.viewer.set_path_start_pick_mode(False)
                self.viewer.clear_path_preview()

    def _toggle_move_parts(self, enabled):
         if self.stack.currentIndex() != 2:
            enabled = False

        self.viewer.set_assembly_edit_mode(
            enabled
        )

        if self.move_parts_button.isChecked() != enabled:
            self.move_parts_button.setChecked(enabled)

        if enabled:
            self.statusBar().showMessage(
                "MOVE PARTS — Click an assembled component and drag to move it. Drag empty 3p space to orbit the camera. Scroll mouse wheel = zoom."
            )

    # Project ---------------------------------------------------------------
    def _new_project(self):
        folder=QFileDialog.getExistingDirectory(self,"New Project Folder")
        if not folder:return
        name,ok=QInputDialog.getText(self,"Project Name","Machine name:",text="New Machine")
        if not ok:return
        self.project_root=Path(folder); self.project=ProjectService.create(self.project_root,name); self.selected_instance_id=""; self.selected_motion_id=""; self._refresh_all(True)
    def _open_project(self):
        path,_=QFileDialog.getOpenFileName(self,"Open Project","","Project (*.json)")
        if not path:return
        try:self.project_root,self.project=ProjectService.load(Path(path))
        except Exception as exc:QMessageBox.critical(self,"Open Project",str(exc));return
        self.selected_instance_id=self.project.instances[0].id if self.project.instances else ""; self.selected_motion_id=self.project.motions[0].id if self.project.motions else ""; self._refresh_all(True)
    def _save_project(self):ProjectService.save(self.project_root,self.project);self.statusBar().showMessage("Project saved.")
    def _save_as(self):
        folder=QFileDialog.getExistingDirectory(self,"Save Project As")
        if not folder:return
        new_root=Path(folder); ProjectService.clone(self.project_root,new_root,self.project); self.project_root=new_root; self._refresh_all(True)

    # STEP ---------------------------------------------------------------------
    def _import_step(self):
        path,_=QFileDialog.getOpenFileName(self,"Import STEP Component","","STEP Component (*.step *.stp)")
        if not path:return
        try:comp=StepImportService.import_component(Path(path),self.project_root); self.project.components.append(comp); self._refresh_all(False); self._navigate(1)
        except StepImportError as exc:QMessageBox.critical(self,"STEP Import",str(exc))
    def _add_component_instance(self,cid):
        comp=self.project.component(cid)
        if not comp:return
        i=1+ sum(1 for x in self.project.instances if x.component_id==cid)
        inst=AssemblyInstance(id=new_id("inst"),component_id=cid,name=f"{comp.name} #{i}"); self.project.instances.append(inst); self.selected_instance_id=inst.id; self._refresh_all(False); self._navigate(2)

    def _drop_component_instance(self, component_id, position):
        comp = self.project.component(component_id)
        if comp is None:
            return

        instance_number = 1 + sum(
            1
            for instance in self.project.instances
            if instance.component_id == component_id
        )

        instance = AssemblyInstance(
            id = new_id("inst"),
            component_id = component_id,
            name = f"{comp.name} #{instance_number}",
            position = [float(v) for v in position],
        )

        self.project.instances.append(instance)
        self.selected_instance_id = instance.id
        self._refresh_all(False)
        self._navigate(2)

        # Keep the toolbar button and the actual viewer mode in sync.
        if not self.move_parts_button.isChecked():
            self.move_parts_button.setChecked(True)
        else:
            self.viewer.set_assembly_edit_mode(True)

        self.viewer.select_instance(instance.id)

        self.statusBar().showMessage(
            f"Added {comp.name} at X={instance.position[0]:.1f}, Y={instance.position[1]:.1f}, Z={instance.position[2]:.1f} mm. Drag to fine-tune its position."
        )

    def _instance_position_dragged(self, instance_id, position, finished):
        inst = self.project.instance(instance_id)
        if inst is None:
            return

        inst.position = [float(v) for v in position]
        self.selected_instance_id = instance_id

        self.assembly.update_position_fields(
            instance_id,
            inst.position,
        )

        if finished:
            self.statusBar().showMessage(
                f"{inst.name} positioned at X={inst.position[0]:.1f}, Y={inst.position[1]:.1f}, Z={inst.position[2]:.1f} mm."
            )

    def _remove_component(self,component_id):
        if any(i.component_id==component_id for i in self.project.instances):QMessageBox.information(self,"Component In Use","Delete its assembly instances first.");return
        comp=self.project.component(component_id)
        if not comp:return
        for rel in (comp.step_file,comp.mesh_file):
            try:(self.project_root/rel).unlink(missing_ok=True)
            except Exception:pass
        self.project.components=[x for x in self.project.components if x.id!=component_id]; self._refresh_all(False)

    # Assembly ----------------------------------------------------------
    def _select_instance(self,iid):
        if not iid:return
        self.selected_instance_id=iid; self.viewer.select_instance(iid); self.assembly.select_id(iid); self.assembly.load_selected(self.project)
    def _apply_transform(self,iid,data):
        inst=self.project.instance(iid)
        if not inst:return
        inst.position=list(data["position"]); inst.rotation=list(data["rotation"]); inst.group=data["group"]; inst.visible=bool(data["visible"]); self._refresh_all(False)
    def _duplicate_instance(self,iid):
        src=self.project.instance(iid)
        if not src:return
        dup=AssemblyInstance(id=new_id("inst"),component_id=src.component_id,name=src.name+" Copy",position=[src.position[0]+50,src.position[1],src.position[2]],rotation=list(src.rotation),group=src.group,visible=src.visible,opacity=src.opacity); self.project.instances.append(dup); self.selected_instance_id=dup.id; self._refresh_all(False)
    def _delete_instance(self,iid):
        if any(m.instance_id==iid for m in self.project.motions):QMessageBox.information(self,"Instance Has Motion","Delete motion profiles referencing this instance first.");return
        self.project.instances=[x for x in self.project.instances if x.id!=iid]; self.selected_instance_id=self.project.instances[0].id if self.project.instances else ""; self._refresh_all(False)

    def _new_motion_for_instance(self, iid):
        if not iid:
            return

        instance = self.project.instance(iid)
        if instance is None:
            return

        self.selected_instance_id = iid
        self.selected_motion_id = ""

        # Move to Motion Setup and initialize a clean editor for exactly
        # the selected assembly component.
        self._navigate(3)
        self.motion.begin_new(
            self.project,
            iid,
        )

        self.viewer.select_instance(iid)

        self.statusBar().showMessage(
            f"New motion for {instance.name} — configure type, axis and travel, then click CREATE MOTION."
        )

    # Motion ------------------------------------------------------------
    def _save_motion(self,data):
        if not data["instance_id"]:
            QMessageBox.information(
                self,
                "Motion",
                "Add an assembly instance first.",
            )
            return

        if (
            data.get("motion_type")=="PATH"
            and len(data.get("path_points",[]))<2
        ):
            QMessageBox.information(
                self,
                "PATH Motion",
                "PATH motion needs at least one picked destination point after the green HOME point.",
            )
            return

        motion=self.project.motion(data["id"]) if data["id"] else None

        start_motion_id=data.get("path_start_motion_id","")
        start_mode=str(
            data.get(
                "path_start_mode",
                "HOME",
            )
        ).upper()

        if (
            data.get("motion_type")=="PATH"
            and start_mode=="CHAINED"
            and start_motion_id
        ):
            start_motion=self.project.motion(start_motion_id)

            if (
                start_motion is None
                or start_motion.motion_type!="PATH"
                or start_motion.instance_id!=data["instance_id"]
            ):
                QMessageBox.information(
                    self,
                    "PATH Start",
                    "A continued PATH must start from another PATH on the same assembly instance.",
                )
                return

            if (
                data.get("id")
                and (
                    start_motion_id==data["id"]
                    or MotionPathService.depends_on(
                        self.project,
                        start_motion_id,
                        data["id"],
                    )
                )
            ):
                QMessageBox.information(
                    self,
                    "PATH Start",
                    "This PATH start would create a circular dependency.",
                )
                return

        if motion is None:
            motion=MotionProfile(
                id=new_id("mot"),
                name=data["name"],
                instance_id=data["instance_id"],
            )
            self.project.motions.append(motion)

        for key in (
            "name",
            "instance_id",
            "motion_type",
            "coordinate",
            "axis",
            "home",
            "end",
            "duration",
            "path_points",
            "path_smooth",
            "follow_path_heading",
            "path_start_mode",
            "path_start_motion_id",
            "path_start_offset",
        ):
            setattr(motion,key,data[key])

        self.selected_motion_id=motion.id
        self._refresh_all(False)
        self._navigate(3)
        self.statusBar().showMessage(
            f"Motion saved: {motion.name}"
        )
    def _delete_motion(self,mid):
        if any(st.motion_id==mid for seq in self.project.sequences for st in seq.steps):QMessageBox.information(self,"Motion In Use","Remove sequence steps referencing this motion first.");return
        self.project.motions=[m for m in self.project.motions if m.id!=mid]; self.selected_motion_id=self.project.motions[0].id if self.project.motions else ""; self._refresh_all(False)
    def _preview_motion(self,mid,fraction):
        m=self.project.motion(mid)
        if m:self.viewer.preview_motion(m,fraction)
    def _test_motion(self,mid):
        m=self.project.motion(mid)
        if not m:return

        # Deterministic preview/test start: clear all previous runtime states.
        self.viewer.apply_motion_state(
            {
                motion.id: 0.0
                for motion in self.project.motions
            }
        )

        self.selected_motion_id=mid; self._test_value=0; self._test_direction=1
        if not hasattr(self,"_test_timer"):
            self._test_timer=QTimer(self); self._test_timer.setInterval(25); self._test_timer.timeout.connect(self._test_motion_tick)
        self._test_timer.start()
    def _test_motion_tick(self):
        m=self.project.motion(self.selected_motion_id)
        if not m:self._test_timer.stop();return
        self._test_value+=self._test_direction*0.03
        if self._test_value>=1:self._test_value=1;self._test_direction=-1
        if self._test_value<=0 and self._test_direction<0:self._test_value=0;self._test_timer.stop()
        self.viewer.preview_motion(m,self._test_value)

    def _path_start_pick_requested(
        self,
        instance_id,
        enabled,
    ):
        self.viewer.set_path_start_pick_mode(
            enabled,
            instance_id,
        )

        if enabled:
            self.statusBar().showMessage(
                "CUSTOM PATH START — click the exact 3D location where this PATH should begin."
            )
        else:
            self.statusBar().showMessage(
                "Custom PATH start picking stopped."
            )

    def _path_start_point_picked(
        self,
        instance_id,
        relative_point,
    ):
        self.motion.set_custom_start_point(
            instance_id,
            relative_point,
        )
    def _path_pick_requested(self, instance_id, anchor_offset, enabled):
        self.viewer.set_path_pick_mode(
            enabled,
            instance_id,
            anchor_offset,
        )

        if enabled:
            self.statusBar().showMessage(
                "PATH PICKING — click points along the conveyor in travel order. Mouse wheel zooms. Click STOP PICKING when finished."
            )
        else:
            self.statusBar().showMessage(
                "PATH picking stopped. Use the motion slider or TEST after saving to preview travel."
            )

    def _path_preview_changed(
        self,
        instance_id,
        anchor_offset,
        points,
        smooth,
    ):
        self.viewer.show_path_preview(
            instance_id,
            anchor_offset,
            points,
            smooth,
        )

    def _path_point_picked(
        self,
        instance_id,
        relative_point,
    ):
        self.motion.add_path_point(
            instance_id,
            relative_point,
        )
    # Sequence ----------------------------------------------------------
    def _new_sequence(self,name):
        seq=MachineSequence(id=new_id("seq"),name=name); self.project.sequences.append(seq); self._refresh_all(False); self._navigate(4)
    def _delete_sequence(self,sid):
        self.project.sequences=[s for s in self.project.sequences if s.id!=sid]; self._refresh_all(False)
    def _add_sequence_step(self,sid,data):
        seq=self.project.sequence(sid)
        if not seq:
            return

        kind=data.get("kind","MOTION")

        # INPUT and OUTPUT are unique production markers. Adding the same
        # marker again moves it to the newly selected block.
        if kind in ("INPUT","OUTPUT"):
            seq.steps=[
                step
                for step in seq.steps
                if step.kind!=kind
            ]

        seq.steps.append(
            SequenceStep(
                id=new_id("step"),
                **data,
            )
        )

        self._refresh_all(False)
        self._navigate(4)

    def _update_sequence_step(self,sid,stepid,data):
        seq=self.project.sequence(sid)
        if not seq:
            return

        step=next(
            (
                item
                for item in seq.steps
                if item.id==stepid
            ),
            None,
        )
        if step is None:
            return

        new_kind=data.get(
            "kind",
            step.kind,
        )

        # INPUT and OUTPUT must remain unique. If the selected step is
        # converted into one of those marker types, remove the other marker.
        if new_kind in ("INPUT","OUTPUT"):
            seq.steps=[
                item
                for item in seq.steps
                if (
                    item.id==stepid
                    or item.kind!=new_kind
                )
            ]
            step=next(
                (
                    item
                    for item in seq.steps
                    if item.id==stepid
                ),
                None,
            )
            if step is None:
                return

        step.block=max(
            1,
            int(data.get("block",step.block)),
        )
        step.kind=new_kind
        step.motion_id=str(
            data.get("motion_id","")
        )
        step.target=str(
            data.get("target","END")
        )
        step.duration=max(
            0.0,
            float(data.get("duration",0.0)),
        )
        step.label=str(
            data.get("label","")
        )

        if step.kind in ("INPUT","OUTPUT"):
            step.motion_id=""
            step.target="END"
            step.duration=0.0
        elif step.kind=="WAIT":
            step.motion_id=""
            step.target="END"
        elif step.kind=="MOTION":
            step.label=""

        self._refresh_all(False)
        self._navigate(4)

    def _sequence_settings_changed(self,sid,output_qty):
        seq=self.project.sequence(sid)
        if not seq:
            return

        seq.output_qty_per_cycle=max(
            1,
            int(output_qty),
        )

        self._refresh_all(False)
        self._navigate(4)
    def _delete_sequence_step(self,sid,stepid):
        seq=self.project.sequence(sid)
        if seq:seq.steps=[x for x in seq.steps if x.id!=stepid]; self._refresh_all(False); self._navigate(4)
    def _move_sequence_step(self,sid,stepid,direction):
        seq=self.project.sequence(sid)
        if not seq:return
        idx=next((i for i,x in enumerate(seq.steps) if x.id==stepid),-1); target=idx+direction
        if idx>=0 and 0<=target<len(seq.steps):seq.steps[idx],seq.steps[target]=seq.steps[target],seq.steps[idx]
        self._refresh_all(False); self._navigate(4)
    def _play_sequence(self,sid):
        seq=self.project.sequence(sid)
        if seq:
            self.viewer.apply_motion_state(
                {
                    motion.id: 0.0
                    for motion in self.project.motions
                }
            )
            self.player.play(
                self.project,
                seq,
            )
    def _run_digital_twin(self,sid,target_seconds,variance_enabled=False,ct_min=None,ct_max=None):
        seq=self.project.sequence(sid)
        if not seq:
            return

        self.viewer.apply_motion_state(
            {
                motion.id:0.0
                for motion in self.project.motions
            }
        )

        self.player.play_for(
            self.project,
            seq,
            target_seconds,
            variance_enabled=variance_enabled,
            ct_min=ct_min,
            ct_max=ct_max,
        )

    def _skip_digital_twin(self,sid,target_seconds,variance_enabled=False,ct_min=None,ct_max=None):
        seq=self.project.sequence(sid)
        if not seq:
            return

        # SKIP can be used either during an active run or directly as an
        # instant calculation without watching the animation.
        if (
            not self.player.running
            or self.player.sequence is not seq
            or abs(self.player.total-float(target_seconds))>1e-9
        ):
            self.viewer.apply_motion_state(
                {
                    motion.id:0.0
                    for motion in self.project.motions
                }
            )
            self.player.play_for(
                self.project,
                seq,
                target_seconds,
                variance_enabled=variance_enabled,
                ct_min=ct_min,
                ct_max=ct_max,
            )

        self.player.skip_to_end()

    def _stop_player(self):self.player.stop(reset=False)
    def _reset_runtime(self):
        self.player.reset(self.project)
        self.viewer.apply_motion_state({})
        self.digital.set_progress(
            0,
            self.digital.run_seconds(),
        )
        self.digital.set_station_statuses([])
        self.viewer.set_production_index(
            0,
            "PROCESS",
            0.0,
        )
    def _motion_state_changed(self,state):self.viewer.apply_motion_state(state)
    def _progress_changed(self,elapsed,total):self.digital.set_progress(elapsed,total)
    def _player_finished(self):pass

    def closeEvent(self,event):
        try:ProjectService.save(self.project_root,self.project)
        except Exception:pass
        super().closeEvent(event)

    def _apply_style(self):
        self.setStyleSheet("""
        QMainWindow,QWidget{background:#0a1018;color:#edf3f9;font-family:'Segoe UI';font-size:11px}
        QFrame#sidebar{background:#101824;border-right:1px solid #2e3c4e}
        QLabel#brand{font-size:16px;font-weight:800;color:white;padding:8px 4px 18px 4px}
        QLabel#pageTitle{font-size:19px;font-weight:800;color:white}
        QLabel#viewerTitle{font-size:13px;font-weight:700;color:white}
        QLabel#sectionTitle{font-size:12px;font-weight:700;color:#dce8f5;margin-top:4px}
        QLabel#muted{color:#95a7ba}
        QLabel#statusBox{background:#111c28;border:1px solid #33465b;border-left:4px solid #2f81f7;border-radius:6px;padding:10px;color:#dce6f0}
        QFrame#viewerPanel{background:#0c121b;border-left:1px solid #2e3c4e}
        QFrame#statCard{background:#151d28;border:1px solid #2e3c4e;border-radius:8px}
        QLabel#statTitle{color:#91a3b6} QLabel#statValue{font-size:21px;font-weight:800;color:white}
        QPushButton{min-height:32px;background:#1c2837;color:#edf3f9;border:1px solid #405168;border-radius:6px;padding:0 10px;font-weight:600}
        QPushButton:hover{background:#26384d} QPushButton:checked{background:#244f91;border-color:#4f86d9}
        QPushButton#primaryButton{background:#2563eb;border:none;color:white;min-height:36px}
        QPushButton:disabled{color:#667789;background:#141c26}
        QTableWidget,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox{background:#0e1620;color:#edf3f9;border:1px solid #334257;border-radius:4px;gridline-color:#263346;padding:3px}
        QHeaderView::section{background:#1b2635;color:#e5edf5;border:0;border-right:1px solid #344256;padding:5px}
        QTableWidget::item:selected{background:#244f91}
        QToolBar{background:#111923;border-bottom:1px solid #2e3c4e;spacing:5px;padding:5px}
        QStatusBar{background:#111923;color:#9fb0c1}
        QProgressBar{border:1px solid #344256;border-radius:5px;text-align:center;background:#0e1620} QProgressBar::chunk{background:#2563eb}
        """)
