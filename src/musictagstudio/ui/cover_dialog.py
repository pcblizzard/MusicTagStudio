from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QPushButton,QVBoxLayout,QWidget
from ..cover_management.models import CoverCandidate
class CoverSelectionDialog(QDialog):
    def __init__(self,candidates:list[CoverCandidate],parent=None):
        super().__init__(parent); self.candidates=candidates; self.selected_candidate=None
        self.setWindowTitle("Cover auswählen"); self.resize(900,600)
        layout=QVBoxLayout(self); info=QLabel("Wähle das gewünschte Master-Cover. Es wird in Originalqualität im Albumordner gespeichert, auf 1000 px für die Audiodateien und auf 400 px bei 80 % Qualität für den übergeordneten Künstlerordner abgeleitet."); info.setWordWrap(True); layout.addWidget(info)
        body=QHBoxLayout(); self.list=QListWidget(); self.preview=QLabel("Keine Vorschau"); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setFixedSize(420,420)
        for c in candidates: item=QListWidgetItem(f"{c.source_label} · {c.dimensions} · Bewertung {c.score}"); self.list.addItem(item)
        self.list.currentRowChanged.connect(self._show); body.addWidget(self.list,1); body.addWidget(self.preview,1); layout.addLayout(body)
        buttons=QDialogButtonBox(); ok=QPushButton("Cover übernehmen"); cancel=QPushButton("Abbrechen"); buttons.addButton(ok,QDialogButtonBox.ButtonRole.AcceptRole); buttons.addButton(cancel,QDialogButtonBox.ButtonRole.RejectRole); ok.clicked.connect(self._accept); cancel.clicked.connect(self.reject); layout.addWidget(buttons)
        if candidates: self.list.setCurrentRow(0)
    def _show(self,row:int):
        if row<0 or row>=len(self.candidates): return
        data=self.candidates[row].data or b""; pix=QPixmap();
        if pix.loadFromData(data): self.preview.setPixmap(pix.scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def _accept(self):
        row=self.list.currentRow()
        if row<0: return
        self.selected_candidate=self.candidates[row]; self.accept()
