"""
ui.widgets.console_widget
----------------------------
Consola de solo-lectura para mostrar el log de ejecución en vivo,
con timestamp por línea.
"""
from __future__ import annotations
from datetime import datetime
from PySide6.QtWidgets import QPlainTextEdit


class ConsoleWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConsoleWidget")
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)

    def append_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.appendPlainText(f"[{timestamp}] {message}")

    def clear_log(self):
        self.clear()
