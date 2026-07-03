"""
ui.views.settings_view
--------------------------
Formulario de configuración de conexión a SQL Server (server, database,
driver, autenticación) + botón "Probar conexión".
"""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QCheckBox,
    QLabel, QMessageBox, QSpinBox, QComboBox
)

from infrastructure.db.connection_manager import ConnectionManager


class SettingsView(QWidget):
    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self.connection_manager = connection_manager

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Configuración de conexión")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.server_input = QLineEdit()
        self.database_input = QLineEdit()
        self.driver_combo = QComboBox()
        self.driver_combo.setEditable(True)
        self.driver_combo.addItems([
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 18 for SQL Server",
            "SQL Server",
        ])
        self.trusted_chk = QCheckBox("Autenticación de Windows (Trusted Connection)")
        self.trusted_chk.setChecked(True)
        self.trusted_chk.toggled.connect(self._toggle_credentials)
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        self.timeout_input.setValue(30)

        form.addRow("Servidor:", self.server_input)
        form.addRow("Base de datos:", self.database_input)
        form.addRow("Driver ODBC:", self.driver_combo)
        form.addRow(self.trusted_chk)
        form.addRow("Usuario:", self.username_input)
        form.addRow("Contraseña:", self.password_input)
        form.addRow("Timeout (segundos):", self.timeout_input)
        root.addLayout(form)

        self.test_btn = QPushButton("Probar conexión")
        self.test_btn.setObjectName("SecondaryButton")
        self.test_btn.clicked.connect(self._on_test_clicked)

        self.save_btn = QPushButton("Guardar configuración")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._on_save_clicked)

        root.addWidget(self.test_btn)
        root.addWidget(self.save_btn)
        root.addStretch()

        self._load_current_settings()

    def _toggle_credentials(self, checked: bool):
        self.username_input.setEnabled(not checked)
        self.password_input.setEnabled(not checked)

    def _load_current_settings(self):
        s = self.connection_manager.get_settings()
        self.server_input.setText(s.get("server", ""))
        self.database_input.setText(s.get("database", ""))
        self.driver_combo.setCurrentText(s.get("driver", "ODBC Driver 17 for SQL Server"))
        self.trusted_chk.setChecked(s.get("trusted_connection", True))
        self.username_input.setText(s.get("username", ""))
        self.password_input.setText(s.get("password", ""))
        self.timeout_input.setValue(s.get("timeout", 30))
        self._toggle_credentials(self.trusted_chk.isChecked())

    def _collect_settings(self) -> dict:
        return {
            "server": self.server_input.text().strip(),
            "database": self.database_input.text().strip(),
            "driver": self.driver_combo.currentText().strip(),
            "trusted_connection": self.trusted_chk.isChecked(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "timeout": self.timeout_input.value(),
        }

    def _on_test_clicked(self):
        previous = self.connection_manager.get_settings()
        self.connection_manager.save_settings(self._collect_settings())
        ok, message = self.connection_manager.test_connection()
        if ok:
            QMessageBox.information(self, "Conexión", message)
        else:
            QMessageBox.critical(self, "Error de conexión", message)
            self.connection_manager.save_settings(previous)

    def _on_save_clicked(self):
        self.connection_manager.save_settings(self._collect_settings())
        QMessageBox.information(self, "Configuración", "Configuración guardada correctamente.")
