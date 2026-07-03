"""
ui.views.dashboard_view
---------------------------
Pantalla principal: tarjetas para los módulos (Gobierno de Datos, CMR,
Modelos, ...). Los módulos se detectan dinámicamente a partir de los
procesos cargados (no están hardcodeados), por lo que agregar un
módulo nuevo es simplemente crear una carpeta más en /processes.
"""
from __future__ import annotations
from collections import defaultdict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea

from core.models import ProcessDefinition
from ui.widgets.module_card import ModuleCard

MODULE_DESCRIPTIONS = {
    "GobiernoDatos": "Calidad de datos, auditoría y validaciones.",
    "CMR": "Resultados de campañas, reclamos y análisis de clientes.",
    "Modelos": "Riesgo, score y predicciones.",
}


class DashboardView(QWidget):
    module_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Panel principal")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        self._layout.addWidget(title)

        subtitle = QLabel("Selecciona un módulo para ver sus procesos disponibles.")
        subtitle.setObjectName("CardDesc")
        self._layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(16)
        scroll.setWidget(container)
        self._layout.addWidget(scroll, 1)

    def set_processes(self, processes: list[ProcessDefinition]):
        # limpiar grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        by_module: dict[str, int] = defaultdict(int)
        for p in processes:
            by_module[p.module] += 1

        modules = sorted(by_module.keys())
        for i, module_name in enumerate(modules):
            count = by_module[module_name]
            desc = MODULE_DESCRIPTIONS.get(module_name, f"{count} proceso(s) disponibles.")
            card = ModuleCard(
                title=module_name,
                description=f"{count} proceso(s) · {desc}",
            )
            card.clicked.connect(lambda m=module_name: self.module_selected.emit(m))
            row, col = divmod(i, 3)
            self.grid.addWidget(card, row, col)
