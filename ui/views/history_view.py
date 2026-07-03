"""
ui.views.history_view
-------------------------
Muestra el historial de ejecuciones (proceso, fecha, duración,
registros obtenidos, estado) leyendo application.HistoryService.
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout
from PySide6.QtGui import QColor

from application.history_service import HistoryService

STATUS_COLORS = {
    "success": QColor("#1F6FEB"),
    "error": QColor("#D93025"),
    "cancelled": QColor("#B08800"),
    "running": QColor("#6B7280"),
}


class HistoryView(QWidget):
    def __init__(self, history_service: HistoryService, parent=None):
        super().__init__(parent)
        self.history_service = history_service

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)

        header = QHBoxLayout()
        title = QLabel("Historial de ejecuciones")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = QPushButton("Actualizar")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Proceso", "Inicio", "Duración (s)", "Registros", "Estado", "Detalle"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

    def refresh(self):
        records = self.history_service.get_history()
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self.table.setItem(row, 0, QTableWidgetItem(rec.get("process_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(rec.get("started_at", "")[:19]))
            self.table.setItem(row, 2, QTableWidgetItem(f"{rec.get('duration_seconds', 0):.1f}"))
            self.table.setItem(row, 3, QTableWidgetItem(str(rec.get("row_count", 0))))

            status_item = QTableWidgetItem(rec.get("status", ""))
            status_item.setForeground(STATUS_COLORS.get(rec.get("status"), QColor("#000000")))
            self.table.setItem(row, 4, status_item)

            self.table.setItem(row, 5, QTableWidgetItem(rec.get("error_message", "")))
        self.table.resizeColumnsToContents()
