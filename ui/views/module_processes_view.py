"""
ui.views.module_processes_view
----------------------------------
Muestra los procesos disponibles dentro de un módulo específico como
tarjetas. Al hacer clic en una, se navega a la vista de ejecución.
"""
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QPushButton, QHBoxLayout

from core.models import ProcessDefinition
from ui.widgets.module_card import ModuleCard


class ModuleProcessesView(QWidget):
    process_selected = Signal(str)   # process.id
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QHBoxLayout()
        back_btn = QPushButton("← Volver")
        back_btn.setObjectName("SecondaryButton")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        header.addStretch()
        layout.addLayout(header)

        self.title_label = QLabel("Módulo")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(self.title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(16)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def set_module(self, module_name: str, processes: list[ProcessDefinition]):
        self.title_label.setText(module_name)
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        module_processes = [p for p in processes if p.module == module_name]
        for i, proc in enumerate(module_processes):
            card = ModuleCard(title=proc.name, description=proc.description,
                               icon_path=str(proc.icon_path) if proc.icon_path else None)
            card.clicked.connect(lambda pid=proc.id: self.process_selected.emit(pid))
            row, col = divmod(i, 3)
            self.grid.addWidget(card, row, col)
