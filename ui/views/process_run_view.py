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
    QSplitter, QFileDialog, QMessageBox, QLineEdit, QFormLayout, QGroupBox,
    QTabWidget, QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Qt

import pandas as pd

from core.models import ProcessDefinition
from core.interfaces import IConnectionProvider, ISqlTemplateEngine, IExcelExporter, ICsvExporter, IEmailSender
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
        csv_exporter: ICsvExporter,
        email_sender: IEmailSender,
        history_service: HistoryService,
        parent=None,
    ):
        super().__init__(parent)
        self.connection_provider = connection_provider
        self.template_engine = template_engine
        self.excel_exporter = excel_exporter
        self.csv_exporter = csv_exporter
        self.email_sender = email_sender
        self.history_service = history_service

        self.process: ProcessDefinition | None = None
        self.worker: ProcessWorker | None = None
        # Lista de resultados: [{"label": str, "df": DataFrame}, ...]
        self.current_results: list[dict] = []
        self.param_form: ParameterFormWidget | None = None

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.scroll_content = QWidget()
        root = QVBoxLayout(self.scroll_content)
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

        self.email_container = QVBoxLayout()
        root.addLayout(self.email_container)

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

        self.export_csv_btn = QPushButton("Exportar a CSV")
        self.export_csv_btn.setObjectName("SecondaryButton")
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self._on_export_csv_clicked)

        action_row.addWidget(self.run_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addStretch()
        action_row.addWidget(self.export_csv_btn)
        action_row.addWidget(self.export_btn)
        root.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

        # --- Preview: QTabWidget para soportar múltiples tablas ---
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setObjectName("PreviewTabs")
        self.preview_tabs.setMinimumHeight(350)
        root.addWidget(self.preview_tabs, 1)

        self.console = ConsoleWidget()
        self.console.setMinimumHeight(150)
        root.addWidget(self.console)
        
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def set_process(self, process: ProcessDefinition):
        self.process = process
        self.title_label.setText(process.name)
        self.desc_label.setText(process.description)
        self.export_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)
        self.current_results = []
        self.console.clear_log()
        self.progress_bar.setValue(0)

        # Limpiar tabs de preview anteriores
        while self.preview_tabs.count():
            self.preview_tabs.removeTab(0)

        # limpiar formulario anterior
        while self.form_container.count():
            item = self.form_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        while self.email_container.count():
            item = self.email_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        last_state = self.history_service.get_last_state(process.id)
        if hasattr(self.history_service, 'get_last_params') and last_state == {}:
            # Support backwards compatibility if it exists
            pass
        last_values = last_state.get("parameters", {})
        last_export_opts = last_state.get("export_options", {})

        self.param_form = ParameterFormWidget(process.parameters, initial_values=last_values)
        self.form_container.addWidget(self.param_form)

        self.export_options = {}
        self.export_inputs = {}
        if getattr(process, 'auto_export_folder', None) or getattr(process, 'auto_export_csv_folder', None):
            export_gb = QGroupBox("Configuración de Exportación Automática")
            export_layout = QFormLayout()
            
            if getattr(process, 'auto_export_folder', None):
                self.export_inputs['excel_path'] = QLineEdit()
                self.export_inputs['excel_path'].setText(last_export_opts.get("excel_path", process.auto_export_folder))
                
                path_layout = QHBoxLayout()
                path_layout.addWidget(self.export_inputs['excel_path'])
                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(30)
                browse_btn.clicked.connect(lambda: self._browse_folder('excel_path'))
                path_layout.addWidget(browse_btn)
                
                export_layout.addRow("Ruta Excel:", path_layout)
                
            if getattr(process, 'auto_export_csv_folder', None):
                self.export_inputs['csv_path'] = QLineEdit()
                self.export_inputs['csv_path'].setText(last_export_opts.get("csv_path", process.auto_export_csv_folder))
                
                path_layout = QHBoxLayout()
                path_layout.addWidget(self.export_inputs['csv_path'])
                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(30)
                browse_btn.clicked.connect(lambda: self._browse_folder('csv_path'))
                path_layout.addWidget(browse_btn)
                
                export_layout.addRow("Ruta CSV:", path_layout)
                
            export_gb.setLayout(export_layout)
            self.email_container.addWidget(export_gb)

        self.email_input = None
        self.attach_excel_cb = None
        self.attach_csv_cb = None
        if process.send_email:
            group_box = QGroupBox("Configuración de Envío de Correo")
            layout = QFormLayout()
            self.email_input = QLineEdit()
            if process.email_default_to:
                self.email_input.setText(last_export_opts.get("email_to", process.email_default_to))
            layout.addRow("Destinatarios (separados por ;):", self.email_input)
            
            if getattr(process, 'auto_export_folder', None):
                self.attach_excel_cb = QCheckBox("Adjuntar Excel")
                self.attach_excel_cb.setChecked(last_export_opts.get("attach_excel", True))
                layout.addRow("", self.attach_excel_cb)
                
            if getattr(process, 'auto_export_csv_folder', None):
                self.attach_csv_cb = QCheckBox("Adjuntar CSV")
                self.attach_csv_cb.setChecked(last_export_opts.get("attach_csv", True))
                layout.addRow("", self.attach_csv_cb)
                
            group_box.setLayout(layout)
            self.email_container.addWidget(group_box)

    def _browse_folder(self, input_key: str):
        current_path = self.export_inputs[input_key].text()
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", current_path)
        if folder:
            self.export_inputs[input_key].setText(folder)

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
        self.export_csv_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.console.clear_log()

        self.current_export_options = {
            "excel_path": self.export_inputs['excel_path'].text() if 'excel_path' in self.export_inputs else None,
            "csv_path": self.export_inputs['csv_path'].text() if 'csv_path' in self.export_inputs else None,
            "email_to": self.email_input.text() if self.email_input else None,
            "attach_excel": self.attach_excel_cb.isChecked() if getattr(self, 'attach_excel_cb', None) else False,
            "attach_csv": self.attach_csv_cb.isChecked() if getattr(self, 'attach_csv_cb', None) else False
        }

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

    def _on_finished_ok(self, results: list, record):
        """
        results: list[{"label": str, "df": DataFrame}]
        """
        self.current_results = results
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # --- Actualizar tabs de preview ---
        while self.preview_tabs.count():
            self.preview_tabs.removeTab(0)

        has_data = any(not r["df"].empty for r in results)

        for result in results:
            table_widget = PreviewTableWidget()
            table_widget.set_dataframe(result["df"])
            self.preview_tabs.addTab(table_widget, result["label"])

        # Habilitar exportación manual solo si hay datos
        self.export_btn.setEnabled(self.process.export_excel and has_data)
        self.export_csv_btn.setEnabled(getattr(self.process, 'export_csv', False) and has_data)

        record.export_options = self.current_export_options
        self.history_service.record_execution(record)

        import os
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self.process.name.replace(' ', '_')

        exported_files = []
        excel_folder = self.current_export_options.get('excel_path') or getattr(self.process, 'auto_export_folder', None)
        csv_folder = self.current_export_options.get('csv_path') or getattr(self.process, 'auto_export_csv_folder', None)
        attach_excel = self.current_export_options.get('attach_excel', True)
        attach_csv = self.current_export_options.get('attach_csv', True)

        # --- Auto-export Excel: un archivo por tabla en la misma carpeta ---
        if excel_folder and has_data:
            for result in results:
                df = result["df"]
                if df.empty:
                    continue
                safe_label = result["label"].replace(' ', '_')
                filename = f"{safe_name}_{safe_label}_{timestamp}.xlsx"
                export_path = os.path.join(excel_folder, filename)
                try:
                    self.excel_exporter.export(df, export_path, sheet_name=result["label"][:31])
                    self.console.append_log(f"✅ Excel guardado: {export_path}")
                    if attach_excel:
                        exported_files.append(export_path)
                except Exception as exc:
                    self.console.append_log(f"❌ Error al guardar Excel ({result['label']}): {str(exc)}")

        # --- Auto-export CSV: un archivo por tabla en la misma carpeta ---
        if csv_folder and has_data:
            for result in results:
                df = result["df"]
                if df.empty:
                    continue
                safe_label = result["label"].replace(' ', '_')
                filename = f"{safe_name}_{safe_label}_{timestamp}.csv"
                export_path = os.path.join(csv_folder, filename)
                try:
                    self.csv_exporter.export(df, export_path)
                    self.console.append_log(f"✅ CSV guardado: {export_path}")
                    if attach_csv:
                        exported_files.append(export_path)
                except Exception as exc:
                    self.console.append_log(f"❌ Error al guardar CSV ({result['label']}): {str(exc)}")

        if getattr(self.process, 'send_email', False) and self.email_input:
            to_addresses = self.email_input.text().strip()
            if to_addresses:
                self.console.append_log(f"Enviando correo a: {to_addresses}...")

                subject = getattr(self.process, 'email_subject', f"Resultados: {self.process.name}")
                if not subject:
                    subject = f"Resultados: {self.process.name}"

                total_rows = sum(r["df"].shape[0] for r in results)
                html_body = f"<p>Adjunto los resultados del proceso <b>{self.process.name}</b>.</p><p>Filas generadas: {total_rows}</p>"

                if getattr(self.process, 'email_template', None):
                    template_path = self.process.folder / self.process.email_template
                    if template_path.exists():
                        try:
                            with open(template_path, 'r', encoding='utf-8') as f:
                                html_body = f.read()
                            html_body = html_body.replace("{proceso_nombre}", self.process.name)
                            html_body = html_body.replace("{fecha}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            html_body = html_body.replace("{filas}", str(total_rows))
                            for param_name, param_value in record.parameters_used.items():
                                html_body = html_body.replace(f"{{{param_name}}}", str(param_value))
                        except Exception as exc:
                            self.console.append_log(f"❌ Error leyendo plantilla de correo: {str(exc)}")

                try:
                    self.email_sender.send_email(to_addresses, subject, html_body, exported_files)
                    self.console.append_log("✅ Correo enviado exitosamente.")
                except Exception as exc:
                    self.console.append_log(f"❌ Error al enviar correo: {str(exc)}")

    def _on_failed(self, message: str, record):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.history_service.record_execution(record)
        QMessageBox.critical(self, "Error en la ejecución", message)

    def _on_export_clicked(self):
        """Exportación manual a Excel.
        - 1 tabla  : selector de archivo (comportamiento anterior).
        - N tablas : selector de carpeta, genera N archivos.
        """
        if not self.current_results:
            return

        from datetime import datetime
        import os
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self.process.name.replace(' ', '_')

        if len(self.current_results) == 1:
            # Comportamiento legado: diálogo de guardar archivo
            result = self.current_results[0]
            if result["df"].empty:
                return
            default_name = f"{safe_name}.xlsx"
            path, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", default_name, "Excel (*.xlsx)")
            if not path:
                return
            try:
                self.excel_exporter.export(result["df"], path, sheet_name=result["label"][:31])
                QMessageBox.information(self, "Exportación completa", f"Archivo guardado en:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Error al exportar", str(exc))
        else:
            # Multi-tabla: selector de carpeta
            folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
            if not folder:
                return
            saved = []
            errors = []
            for result in self.current_results:
                if result["df"].empty:
                    continue
                safe_label = result["label"].replace(' ', '_')
                filename = f"{safe_name}_{safe_label}_{timestamp}.xlsx"
                path = os.path.join(folder, filename)
                try:
                    self.excel_exporter.export(result["df"], path, sheet_name=result["label"][:31])
                    saved.append(filename)
                except Exception as exc:
                    errors.append(f"{result['label']}: {exc}")
            msg = f"{len(saved)} archivo(s) guardados en:\n{folder}"
            if errors:
                msg += "\n\nErrores:\n" + "\n".join(errors)
            QMessageBox.information(self, "Exportación completa", msg)

    def _on_export_csv_clicked(self):
        """Exportación manual a CSV.
        - 1 tabla  : selector de archivo.
        - N tablas : selector de carpeta, genera N archivos.
        """
        if not self.current_results:
            return

        from datetime import datetime
        import os
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self.process.name.replace(' ', '_')

        if len(self.current_results) == 1:
            result = self.current_results[0]
            if result["df"].empty:
                return
            default_name = f"{safe_name}.csv"
            path, _ = QFileDialog.getSaveFileName(self, "Exportar a CSV", default_name, "CSV (*.csv)")
            if not path:
                return
            try:
                self.csv_exporter.export(result["df"], path)
                QMessageBox.information(self, "Exportación completa", f"Archivo CSV guardado en:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Error al exportar a CSV", str(exc))
        else:
            folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
            if not folder:
                return
            saved = []
            errors = []
            for result in self.current_results:
                if result["df"].empty:
                    continue
                safe_label = result["label"].replace(' ', '_')
                filename = f"{safe_name}_{safe_label}_{timestamp}.csv"
                path = os.path.join(folder, filename)
                try:
                    self.csv_exporter.export(result["df"], path)
                    saved.append(filename)
                except Exception as exc:
                    errors.append(f"{result['label']}: {exc}")
            msg = f"{len(saved)} archivo(s) CSV guardados en:\n{folder}"
            if errors:
                msg += "\n\nErrores:\n" + "\n".join(errors)
            QMessageBox.information(self, "Exportación completa", msg)