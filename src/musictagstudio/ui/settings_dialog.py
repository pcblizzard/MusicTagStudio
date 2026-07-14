from __future__ import annotations
from dataclasses import replace
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup,QCheckBox,QComboBox,QDialog,QDialogButtonBox,QFormLayout,QFrame,QGroupBox,QHBoxLayout,QLabel,QRadioButton,QScrollArea,QSpinBox,QVBoxLayout,QWidget
from ..provider_catalog import PROVIDERS
from ..cover_source_catalog import COVER_SOURCES
from ..settings import AppSettings
STATUS_STYLES={"supported":"color:#2e9d50;font-weight:600;","setup_required":"color:#c28b00;font-weight:600;","unsupported":"color:#d04a4a;font-weight:600;"}
class SettingsDialog(QDialog):
    settings_saved=Signal(object)
    def __init__(self,settings:AppSettings,parent=None):
        super().__init__(parent); self.initial_settings=settings; self.provider_buttons={}; self.cover_buttons={}; self.setWindowTitle("Einstellungen"); self.resize(720,820)
        outer=QVBoxLayout(self); scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); layout=QVBoxLayout(content)
        appearance=QGroupBox("Darstellung"); form=QFormLayout(appearance); self.theme_combo=QComboBox();
        for label,data in (("Automatisch (Windows-Einstellung)","automatic"),("Hell","light"),("Dunkel","dark")): self.theme_combo.addItem(label,data)
        self._set(self.theme_combo,settings.theme); form.addRow("Theme:",self.theme_combo); layout.addWidget(appearance)
        providers=QGroupBox("Metadatenquelle"); pv=QVBoxLayout(providers); info=QLabel("Die ausgewählte Quelle besitzt Priorität. Andere unterstützte Quellen können nur fehlende Felder ergänzen."); info.setWordWrap(True); pv.addWidget(info); self.provider_group=QButtonGroup(self); self.provider_group.setExclusive(True)
        for item in PROVIDERS: self._provider_row(pv,self.provider_group,self.provider_buttons,item.provider_id,item.name,item.status,item.status_text,item.tooltip,item.selectable)
        self.provider_buttons.get(settings.selected_provider,self.provider_buttons["apple_music"]).setChecked(True); self.enrich=QCheckBox("Fehlende Felder durch andere unterstützte Quellen ergänzen"); self.enrich.setChecked(settings.enrich_missing_fields); pv.addWidget(self.enrich)
        self.country=QComboBox();
        for code,name in (("DE","Deutschland"),("AT","Österreich"),("CH","Schweiz"),("US","USA"),("GB","Großbritannien")): self.country.addItem(f"{name} ({code})",code)
        self._set(self.country,settings.apple_country); cf=QFormLayout(); cf.addRow("Apple-Store:",self.country); pv.addLayout(cf); layout.addWidget(providers)
        covers=QGroupBox("Coverquellen"); cv=QVBoxLayout(covers); ci=QLabel("Metadaten- und Coverquelle sind unabhängig. Rot bedeutet, dass die Quelle in MusicTagStudio aktuell nicht nutzbar ist."); ci.setWordWrap(True); cv.addWidget(ci); self.cover_group=QButtonGroup(self); self.cover_group.setExclusive(True)
        for item in COVER_SOURCES: self._provider_row(cv,self.cover_group,self.cover_buttons,item.source_id,item.name,item.status,item.status_text,item.tooltip,item.selectable)
        self.cover_buttons.get(settings.selected_cover_source,self.cover_buttons["apple_music"]).setChecked(True); self.cover_fallback=QCheckBox("Andere unterstützte Quelle verwenden, wenn kein geeignetes Cover gefunden wird"); self.cover_fallback.setChecked(settings.cover_fallback_enabled); cv.addWidget(self.cover_fallback)
        cform=QFormLayout(); self.minimum=QSpinBox(); self.minimum.setRange(100,10000); self.minimum.setValue(settings.minimum_cover_size); self.minimum.setSuffix(" px"); cform.addRow("Mindestauflösung:",self.minimum)
        self.levels=QSpinBox(); self.levels.setRange(1,5); self.levels.setValue(settings.artist_folder_levels_up); self.levels.setToolTip("Anzahl der Ordnerebenen, die vom Albumordner zum Zielordner des 400-px-Covers nach oben gegangen wird."); cform.addRow("Künstlerordner liegt:",self.levels); cv.addLayout(cform); layout.addWidget(covers)
        norm=QGroupBox("Normalisierung"); nf=QFormLayout(norm); self.feature=QComboBox();
        for label,data in (("Gast nur im Künstlerfeld","artist_only"),("Gast im Titel und Künstlerfeld","title_and_artist"),("Schreibweise der Quelle beibehalten","source")): self.feature.addItem(label,data)
        self._set(self.feature,settings.feature_handling); nf.addRow("Feature-Künstler:",self.feature); layout.addWidget(norm); layout.addStretch(); scroll.setWidget(content); outer.addWidget(scroll)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); box.accepted.connect(self.accept); box.rejected.connect(self.reject); outer.addWidget(box)
    def _provider_row(self,layout,group,storage,id_,name,status,status_text,tooltip,selectable):
        row=QWidget(); h=QHBoxLayout(row); h.setContentsMargins(4,3,4,3); button=QRadioButton(name); button.setEnabled(selectable); button.setToolTip(tooltip); label=QLabel(status_text); label.setStyleSheet(STATUS_STYLES[status]); label.setToolTip(tooltip); row.setToolTip(tooltip); group.addButton(button); storage[id_]=button; h.addWidget(button); h.addStretch(); h.addWidget(label); layout.addWidget(row)
    def selected_settings(self)->AppSettings:
        provider=next((k for k,v in self.provider_buttons.items() if v.isChecked()),"apple_music"); cover=next((k for k,v in self.cover_buttons.items() if v.isChecked()),"apple_music")
        return replace(self.initial_settings,theme=str(self.theme_combo.currentData()),selected_provider=provider,enrich_missing_fields=self.enrich.isChecked(),apple_country=str(self.country.currentData()),feature_handling=str(self.feature.currentData()),selected_cover_source=cover,cover_fallback_enabled=self.cover_fallback.isChecked(),minimum_cover_size=self.minimum.value(),artist_folder_levels_up=self.levels.value(),embedded_cover_size=1000,embedded_cover_quality=100,folder_cover_size=400,folder_cover_quality=80)
    @staticmethod
    def _set(combo,value):
        i=combo.findData(value)
        if i>=0: combo.setCurrentIndex(i)
