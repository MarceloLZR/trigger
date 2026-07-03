"""
ui.views.process_run_view
-----------------------------
Vista de ejecución de UN proceso: formulario de parámetros (generado
dinámicamente), botón Ejecutar/Cancelar, barra de progreso, consola
de log, y tabla de preview con botón "Exportar a Excel".

Esta vista no sabe nada de pyodbc/pandas directamente: delega en
ProcessWorker (application layer) y solo escucha señales.
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QSplitter, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

import pandas as pd

from core.models import ProcessDefinition
from core.interfaces import IConnectionProvider, ISqlTemplateEngine, IExcelExporter
from application.process_executor import ProcessWorker
from application.history_service import HistoryService
from ui.widgets.parameter_form import ParameterFormWidget
from ui.widgets.preview_table import PreviewTableWidget
from ui.widgets.console_widget import ConsoleWidget


class ProcessRunView(QWidget):
    back_requested = Signal()

    def __init__(
        self,
        connection_provider: IConnectionProvider,
        template_engine: ISqlTemplateEngine,
        excel_exporter: IExcelExporter,
        history_service: HistoryService,
        parent=None,
    ):
        super().__init__(parent)
        self.connection_provider = connection_provider
        self.template_engine = template_engine
        self.excel_exporter = excel_exporter
        self.history_service = history_service

        self.process: ProcessDefinition | None = None
        self.worker: ProcessWorker | None = None
        self.current_df: pd.DataFrame | None = None
        self.param_form: ParameterFormWidget | None = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)

        header = QHBoxLayout()
        back_btn = QPushButton("← Volver")
        back_btn.setObjectName("SecondaryButton")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        header.addStretch()
        root.addLayout(header)

        self.title_label = QLabel("Proceso")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.desc_label = QLabel("")
        self.desc_label.setObjectName("CardDesc")
        root.addWidget(self.title_label)
        root.addWidget(self.desc_label)

        self.form_container = QVBoxLayout()
        root.addLayout(self.form_container)

        action_row = QHBoxLayout()
        self.run_btn = QPushButton("▶ Ejecutar")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.clicked.connect(self._on_run_clicked)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)

        self.export_btn = QPushButton("Exportar a Excel")
        self.export_btn.setObjectName("SecondaryButton")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export_clicked)

        action_row.addWidget(self.run_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addStretch()
        action_row.addWidget(self.export_btn)
        root.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

        splitter = QSplitter(Qt.Vertical)
        self.preview_table = PreviewTableWidget()
        self.console = ConsoleWidget()
        self.console.setMaximumHeight(160)
        splitter.addWidget(self.preview_table)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def set_process(self, process: ProcessDefinition):
        self.process = process
        self.title_label.setText(process.name)
        self.desc_label.setText(process.description)
        self.export_btn.setEnabled(False)
        self.current_df = None
        self.console.clear_log()
        self.progress_bar.setValue(0)

        # limpiar formulario anterior
        while self.form_container.count():
            item = self.form_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        last_values = self.history_service.get_last_params(process.id)
        self.param_form = ParameterFormWidget(process.parameters, initial_values=last_values)
        self.form_container.addWidget(self.param_form)

    def _on_run_clicked(self):
        if not self.process or not self.param_form:
            return
        valid, message = self.param_form.validate()
        if not valid:
            QMessageBox.warning(self, "Parámetros incompletos", message)
            return

        params = self.param_form.get_values()
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.console.clear_log()

        self.worker = ProcessWorker(self.process, params, self.connection_provider, self.template_engine)
        self.worker.log.connect(self.console.append_log)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished_ok.connect(self._on_finished_ok)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_cancel_clicked(self):
        if self.worker:
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_finished_ok(self, df: pd.DataFrame, record):
        self.current_df = df
        self.preview_table.set_dataframe(df)
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.export_btn.setEnabled(self.process.export_excel and not df.empty)
        self.history_service.record_execution(record)

    def _on_failed(self, message: str, record):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.history_service.record_execution(record)
        QMessageBox.critical(self, "Error en la ejecución", message)

    def _on_export_clicked(self):
        if self.current_df is None or self.current_df.empty:
            return
        default_name = f"{self.process.name.replace(' ', '_')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", default_name, "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.excel_exporter.export(self.current_df, path)
            QMessageBox.information(self, "Exportación completa", f"Archivo guardado en:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))
