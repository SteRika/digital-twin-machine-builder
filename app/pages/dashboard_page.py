from PySide6.QtWidgets import QLabel, QGridLayout, QVBoxLayout, QWidget
from app.widgets import StatCard


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay=QVBoxLayout(self); lay.setContentsMargins(14,14,14,14)
        title=QLabel("DASHBOARD"); title.setObjectName("pageTitle"); lay.addWidget(title)
        sub=QLabel("Build the machine first, then define motion profiles and machine sequence before Digital Twin runtime."); sub.setWordWrap(True); sub.setObjectName("muted"); lay.addWidget(sub)
        grid=QGridLayout(); self.cards={}
        for i,(key,label) in enumerate([("components","STEP Components"),("instances","Assembly Instances"),("motions","Motion Profiles"),("sequences","Sequences")]):
            card=StatCard(label); self.cards[key]=card; grid.addWidget(card,i//2,i%2)
        lay.addLayout(grid)
        self.ready=QLabel(); self.ready.setWordWrap(True); self.ready.setObjectName("statusBox"); lay.addWidget(self.ready); lay.addStretch()

    def refresh(self, project, issues):
        self.cards["components"].set_value(len(project.components)); self.cards["instances"].set_value(len(project.instances)); self.cards["motions"].set_value(len(project.motions)); self.cards["sequences"].set_value(len(project.sequences))
        if issues:
            self.ready.setText("PROJECT NOT READY\n\n" + "\n".join(f"• {x}" for x in issues))
        else:
            self.ready.setText("PROJECT READY FOR DIGITAL TWIN\nAll required configuration is available.")
