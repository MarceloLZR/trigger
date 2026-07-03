"""
ui.widgets.module_card
--------------------------
Tarjeta clicable reutilizada tanto para mostrar los 3 módulos en el
Dashboard como para mostrar cada proceso dentro de un módulo.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy


class ModuleCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, description: str = "", icon_path: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        if icon_path:
            icon_label = QLabel()
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        title_label.setWordWrap(True)

        desc_label = QLabel(description)
        desc_label.setObjectName("CardDesc")
        desc_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
