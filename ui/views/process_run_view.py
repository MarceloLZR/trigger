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
    QTabWidget, QScrollArea, QFrame, QCheckBox, QComboBox
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

        # Contenedores temporales para construir secciones; no los añadimos
        # directamente al layout principal: los organizaremos en pestañas.
        self.email_container = QVBoxLayout()
        self.emblue_container = QVBoxLayout()

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
                
        while self.emblue_container.count():
            item = self.emblue_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        last_state = self.history_service.get_last_state(process.id)
        if hasattr(self.history_service, 'get_last_params') and last_state == {}:
            # Support backwards compatibility if it exists
            pass
        last_values = last_state.get("parameters", {})
        last_export_opts = last_state.get("export_options", {})

        self.param_form = ParameterFormWidget(process.parameters, initial_values=last_values)

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
            # se mantiene en self.email_container para agregarse a la pestaña
            self.email_container.addWidget(group_box)

        # Emblue settings
        self.emblue_inputs = {}
        if getattr(process, 'send_emblue', False):
            emblue_gb = QGroupBox("Configuración de Envío a Emblue SFTP")
            emblue_layout = QFormLayout()
            
            self.emblue_inputs['id_cuenta'] = QLineEdit()
            self.emblue_inputs['id_cuenta'].setText(str(last_export_opts.get('emblue_id_cuenta', process.emblue_id_cuenta or '')))
            emblue_layout.addRow("ID Cuenta:", self.emblue_inputs['id_cuenta'])
            
            self.emblue_inputs['carpeta'] = QLineEdit()
            self.emblue_inputs['carpeta'].setText(str(last_export_opts.get('emblue_carpeta', process.emblue_carpeta or '')))
            emblue_layout.addRow("Carpeta Emblue:", self.emblue_inputs['carpeta'])
            
            self.emblue_inputs['flg_dropeo'] = QCheckBox("Dropear tabla luego del envío")
            flg_dropeo = bool(last_export_opts.get('emblue_flg_dropeo', process.emblue_flg_dropeo))
            self.emblue_inputs['flg_dropeo'].setChecked(flg_dropeo)
            emblue_layout.addRow("", self.emblue_inputs['flg_dropeo'])

            self.emblue_inputs['flg_fecha_base'] = QCheckBox("Enviar con fecha base (Generar XML)")
            flg_fecha_base = bool(last_export_opts.get('emblue_flg_fecha_base', process.emblue_flg_fecha_base))
            self.emblue_inputs['flg_fecha_base'].setChecked(flg_fecha_base)
            emblue_layout.addRow("", self.emblue_inputs['flg_fecha_base'])

            emblue_gb.setLayout(emblue_layout)
            # se mantiene en self.emblue_container para agregarse a la pestaña
            self.emblue_container.addWidget(emblue_gb)

        # Configuración Global de Contraseña (Si aplica)
        self.password_input = None
        self.password_fields_list = []
        if getattr(process, 'export_password_enabled', False):
            pwd_gb = QGroupBox("Contraseña Global")
            pwd_layout = QFormLayout()
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            self.password_input.setPlaceholderText("Dejar en blanco para no proteger")
            default_pwd = last_export_opts.get('export_password', process.export_password_default or '')
            self.password_input.setText(str(default_pwd))
            pwd_layout.addRow("Contraseña:", self.password_input)
            self.password_fields_list.append(self.password_input)
            pwd_gb.setLayout(pwd_layout)
            # se mantiene en self.emblue_container para agregarse a la pestaña
            self.emblue_container.addWidget(pwd_gb)

        # Toggle Preview Option
        self.show_preview_cb = QCheckBox("Auto cargar preview al finalizar")
        self.show_preview_cb.setToolTip(
            "Desmarcar para mostrar sólo nombres de tablas y cargar el preview sólo al hacer clic."
        )
        self.show_preview_cb.setChecked(last_export_opts.get('show_preview', getattr(process, 'show_preview', False)))
        # Añadiremos el checkbox a la pestaña Global más abajo
        self.emblue_container.addWidget(self.show_preview_cb)

        # Configuración por Tabla (Overrides)
        self.table_ui_fields = {}
        if getattr(process, 'final_tables', None) and len(process.final_tables) > 0:
            tables_gb = QGroupBox("Configuración por Tabla (Overrides)")
            tables_layout = QVBoxLayout()
            
            show_pwd_cb = QCheckBox("Mostrar contraseñas")
            show_pwd_cb.stateChanged.connect(self._toggle_passwords)
            tables_layout.addWidget(show_pwd_cb)

            tables_tabs = QTabWidget()
            show_overrides_cb = QCheckBox("Mostrar sólo campos modificados")
            show_overrides_cb.setChecked(False)
            show_overrides_cb.stateChanged.connect(self._toggle_table_overrides_view)
            tables_layout.addWidget(show_overrides_cb)
            table_overrides = last_export_opts.get('table_overrides', {})

            for ft in process.final_tables:
                tab_widget = QWidget()
                tab_layout = QFormLayout()
                ft_overrides = table_overrides.get(ft.table, {})

                fields = {}

                # Mostrar solo la etiqueta legible para el usuario
                table_label_readonly = QLineEdit(ft.label)
                table_label_readonly.setReadOnly(True)
                tab_layout.addRow("Etiqueta:", table_label_readonly)
                fields['label'] = table_label_readonly

                export_name_input = QLineEdit()
                export_name_input.setPlaceholderText("Heredar nombre de exportación")
                export_name_input.setText(ft_overrides.get('export_name', ft.export_name or ''))
                tab_layout.addRow("Nombre de exportación:", export_name_input)
                fields['export_name'] = export_name_input

                # Excel Folder
                excel_input = QLineEdit()
                excel_input.setPlaceholderText("Heredar del proceso")
                excel_input.setText(ft_overrides.get('export_excel_folder', ft.export_excel_folder or ''))
                excel_layout = QHBoxLayout()
                excel_layout.addWidget(excel_input)
                browse_excel_btn = QPushButton("...")
                browse_excel_btn.setFixedWidth(30)
                browse_excel_btn.clicked.connect(lambda checked=False, inp=excel_input: self._browse_folder_for_input(inp))
                excel_layout.addWidget(browse_excel_btn)
                tab_layout.addRow("Ruta Excel:", excel_layout)
                fields['export_excel_folder'] = excel_input
                fields['export_excel_browse'] = browse_excel_btn

                # CSV Folder
                csv_input = QLineEdit()
                csv_input.setPlaceholderText("Heredar del proceso")
                csv_input.setText(ft_overrides.get('export_csv_folder', ft.export_csv_folder or ''))
                csv_layout = QHBoxLayout()
                csv_layout.addWidget(csv_input)
                browse_csv_btn = QPushButton("...")
                browse_csv_btn.setFixedWidth(30)
                browse_csv_btn.clicked.connect(lambda checked=False, inp=csv_input: self._browse_folder_for_input(inp))
                csv_layout.addWidget(browse_csv_btn)
                tab_layout.addRow("Ruta CSV:", csv_layout)
                fields['export_csv_folder'] = csv_input
                fields['export_csv_browse'] = browse_csv_btn

                # Password
                pwd_input = QLineEdit()
                pwd_input.setEchoMode(QLineEdit.Password)
                pwd_input.setPlaceholderText("Heredar (Dejar vacío = Sin contraseña)")
                pwd_input.setText(ft_overrides.get('password', ft.password or ''))
                tab_layout.addRow("Contraseña:", pwd_input)
                fields['password'] = pwd_input
                self.password_fields_list.append(pwd_input)

                # Emblue
                send_emblue_cb = QComboBox()
                send_emblue_cb.addItems(["Heredar", "Sí", "No"])
                saved_send = ft_overrides.get('send_emblue', ft.send_emblue)
                if saved_send is None:
                    send_emblue_cb.setCurrentText("Heredar")
                elif saved_send:
                    send_emblue_cb.setCurrentText("Sí")
                else:
                    send_emblue_cb.setCurrentText("No")
                tab_layout.addRow("Enviar a Emblue:", send_emblue_cb)
                fields['send_emblue'] = send_emblue_cb

                emblue_id = QLineEdit()
                emblue_id.setPlaceholderText("Heredar del proceso")
                emblue_id.setText(str(ft_overrides.get('emblue_id_cuenta', ft.emblue_id_cuenta or '')))
                tab_layout.addRow("ID Cuenta Emblue:", emblue_id)
                fields['emblue_id_cuenta'] = emblue_id

                emblue_carpeta = QLineEdit()
                emblue_carpeta.setPlaceholderText("Heredar del proceso")
                emblue_carpeta.setText(ft_overrides.get('emblue_carpeta', ft.emblue_carpeta or ''))
                tab_layout.addRow("Carpeta Emblue:", emblue_carpeta)
                fields['emblue_carpeta'] = emblue_carpeta

                emblue_dropeo_cb = QCheckBox("Dropear tabla luego del envío")
                emblue_dropeo_cb.setChecked(bool(ft_overrides.get('emblue_flg_dropeo', ft.emblue_flg_dropeo)))
                tab_layout.addRow("", emblue_dropeo_cb)
                fields['emblue_flg_dropeo'] = emblue_dropeo_cb

                emblue_fecha_cb = QCheckBox("Enviar con fecha base (Generar XML)")
                emblue_fecha_cb.setChecked(bool(ft_overrides.get('emblue_flg_fecha_base', ft.emblue_flg_fecha_base)))
                tab_layout.addRow("", emblue_fecha_cb)
                fields['emblue_flg_fecha_base'] = emblue_fecha_cb

                # Guardar valores por defecto del FinalTable para comparación estética
                fields['_ft_defaults'] = {
                    'export_excel_folder': ft.export_excel_folder or '',
                    'export_csv_folder': ft.export_csv_folder or '',
                    'password': ft.password or '',
                    'send_emblue': ft.send_emblue,
                    'emblue_id_cuenta': ft.emblue_id_cuenta or '',
                    'emblue_carpeta': ft.emblue_carpeta or '',
                    'emblue_flg_dropeo': int(ft.emblue_flg_dropeo or 0),
                    'emblue_flg_fecha_base': int(ft.emblue_flg_fecha_base or 0),
                    'export_name': ft.export_name or ''
                }

                self.table_ui_fields[ft.table] = fields
                tab_widget.setLayout(tab_layout)
                tables_tabs.addTab(tab_widget, ft.label)

            tables_layout.addWidget(tables_tabs)
            tables_gb.setLayout(tables_layout)
            self.emblue_container.addWidget(tables_gb)

        # --- Ensamblar pestañas de configuración (Parámetros / Global / Por tabla) ---
        settings_tabs = QTabWidget()

        # Pestaña Parámetros
        tab_params = QWidget()
        tp_layout = QVBoxLayout(tab_params)
        tp_layout.setContentsMargins(0, 0, 0, 0)
        tp_layout.addWidget(self.param_form)
        settings_tabs.addTab(tab_params, "Parámetros")

        # Pestaña Global: movemos widgets creados en email_container y emblue_container
        tab_global = QWidget()
        tg_layout = QVBoxLayout(tab_global)
        tg_layout.setContentsMargins(0, 0, 0, 0)

        # mover widgets desde email_container
        while self.email_container.count():
            it = self.email_container.takeAt(0)
            w = it.widget()
            if w:
                tg_layout.addWidget(w)

        # mover widgets desde emblue_container
        while self.emblue_container.count():
            it = self.emblue_container.takeAt(0)
            w = it.widget()
            if w:
                tg_layout.addWidget(w)

        tg_layout.addStretch()
        settings_tabs.addTab(tab_global, "Configuración")

        # Pestaña Por Tabla
        tab_tables = QWidget()
        tt_layout = QVBoxLayout(tab_tables)
        tt_layout.setContentsMargins(0, 0, 0, 0)
        # si existía tables_gb lo añadimos
        try:
            tt_layout.addWidget(tables_gb)
        except NameError:
            pass
        tt_layout.addStretch()
        settings_tabs.addTab(tab_tables, "Por tabla")

        # Reemplazamos el área de formulario por las pestañas
        self.form_container.addWidget(settings_tabs)

    def _toggle_passwords(self, state):
        echo_mode = QLineEdit.Normal if state else QLineEdit.Password
        for field in self.password_fields_list:
            field.setEchoMode(echo_mode)

    def _toggle_table_overrides_view(self, state: int):
        """Muestra u oculta widgets en la pestaña 'Por tabla' según si son
        distintos a los valores por defecto del FinalTable (estética solamente)."""
        show_only = (state == Qt.Checked)

        for table_name, fields in self.table_ui_fields.items():
            defaults = fields.get('_ft_defaults', {})
            for key, widget in list(fields.items()):
                if key == '_ft_defaults':
                    continue

                # Detectar tipo y valor actual
                try:
                    if isinstance(widget, QLineEdit):
                        cur = widget.text().strip()
                        default = str(defaults.get(key, '') or '')
                        diff = (cur != '' and cur != default)
                    elif isinstance(widget, QComboBox):
                        cur = widget.currentText()
                        default = defaults.get(key, None)
                        if cur == 'Heredar':
                            diff = False
                        else:
                            # 'Sí'/'No' map to bool
                            if default in (True, False):
                                diff = (cur == 'Sí') != bool(default)
                            else:
                                diff = cur != (str(default) if default is not None else '')
                    elif isinstance(widget, QCheckBox):
                        cur = widget.isChecked()
                        default = bool(defaults.get(key, 0))
                        diff = (cur != default)
                    else:
                        diff = True
                except Exception:
                    diff = True

                visible = (not show_only) or diff

                # Ocultar/mostrar widget
                try:
                    widget.setVisible(visible)
                except Exception:
                    pass

                # Si hay un botón de browse correspondiente, ocultarlo también
                browse_key = f"{key}_browse"
                if browse_key in fields:
                    try:
                        fields[browse_key].setVisible(visible)
                    except Exception:
                        pass

    def _browse_folder_for_input(self, input_widget: QLineEdit):
        current_path = input_widget.text()
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", current_path)
        if folder:
            input_widget.setText(folder)

    def _browse_folder(self, input_key: str):
        current_path = self.export_inputs[input_key].text()
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", current_path)
        if folder:
            self.export_inputs[input_key].setText(folder)

    def _render_string(self, text: str, params: dict) -> str:
        if not text:
            return ""
        res = text
        for k, v in params.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res

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
            "attach_csv": self.attach_csv_cb.isChecked() if getattr(self, 'attach_csv_cb', None) else False,
            
            "emblue_id_cuenta": self.emblue_inputs['id_cuenta'].text() if 'id_cuenta' in self.emblue_inputs else None,
            "emblue_carpeta": self.emblue_inputs['carpeta'].text() if 'carpeta' in self.emblue_inputs else None,
            "emblue_flg_dropeo": 1 if ('flg_dropeo' in self.emblue_inputs and self.emblue_inputs['flg_dropeo'].isChecked()) else 0,
            "emblue_flg_fecha_base": 1 if ('flg_fecha_base' in self.emblue_inputs and self.emblue_inputs['flg_fecha_base'].isChecked()) else 0,
            
            "export_password": self.password_input.text() if self.password_input else None,
            "show_preview": self.show_preview_cb.isChecked(),
            "table_overrides": self._collect_table_overrides()
        }

        self.worker = ProcessWorker(
            process=self.process,
            params=params,
            connection_provider=self.connection_provider,
            template_engine=self.template_engine,
            excel_exporter=self.excel_exporter,
            csv_exporter=self.csv_exporter,
            email_sender=self.email_sender,
            export_options=self.current_export_options
        )
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

        if not has_data:
            self.console.append_log("⚠️ No se generaron datos en ninguna tabla.")
        else:
            show_preview = self.current_export_options.get("show_preview", True)
            for r in results:
                df = r["df"]
                label = r["label"]

                if df.empty:
                    continue

                if show_preview:
                    preview_widget = PreviewTableWidget()
                    preview_widget.set_dataframe(df)
                    self.preview_tabs.addTab(preview_widget, label)
                else:
                    self._create_preview_tab(label, df)

            if show_preview:
                self.console.append_log("✅ Proceso finalizado. Resultados cargados en la vista previa.")
            else:
                self.console.append_log(
                    "✅ Proceso finalizado. Las pestañas muestran sólo el nombre de cada tabla; haga clic en 'Cargar preview' para ver los datos."
                )

        # Habilitar exportación manual solo si hay datos
        self.export_btn.setEnabled(self.process.export_excel and has_data)
        self.export_csv_btn.setEnabled(getattr(self.process, 'export_csv', False) and has_data)

        record.export_options = self.current_export_options
        self.history_service.record_execution(record)

    def _create_preview_tab(self, label: str, df: pd.DataFrame):
        placeholder = QWidget()
        placeholder.preview_df = df
        placeholder.preview_label = label

        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(16, 16, 16, 16)

        info = QLabel(
            f"Tabla: {label}\nFilas: {len(df):,}\n\nHaga clic en el botón para cargar la vista previa de esta tabla."
        )
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)

        load_button = QPushButton("Cargar preview")
        load_button.setObjectName("PrimaryButton")
        load_button.clicked.connect(lambda checked=False, widget=placeholder: self._load_preview_for_tab(widget))

        layout.addStretch()
        layout.addWidget(info)
        layout.addWidget(load_button, alignment=Qt.AlignHCenter)
        layout.addStretch()

        self.preview_tabs.addTab(placeholder, label)

    def _load_preview_for_tab(self, placeholder: QWidget):
        index = self.preview_tabs.indexOf(placeholder)
        if index < 0:
            return

        df = getattr(placeholder, 'preview_df', None)
        label = getattr(placeholder, 'preview_label', self.preview_tabs.tabText(index))
        if df is None:
            return

        preview_widget = PreviewTableWidget()
        preview_widget.set_dataframe(df)

        self.preview_tabs.removeTab(index)
        self.preview_tabs.insertTab(index, preview_widget, label)
        self.preview_tabs.setCurrentWidget(preview_widget)

    def _collect_table_overrides(self) -> dict[str, dict[str, object]]:
        overrides: dict[str, dict[str, object]] = {}
        for table_name, fields in self.table_ui_fields.items():
            table_data: dict[str, object] = {}

            if 'export_name' in fields:
                text = fields['export_name'].text().strip()
                if text:
                    table_data['export_name'] = text

            if 'export_excel_folder' in fields:
                text = fields['export_excel_folder'].text().strip()
                if text:
                    table_data['export_excel_folder'] = text

            if 'export_csv_folder' in fields:
                text = fields['export_csv_folder'].text().strip()
                if text:
                    table_data['export_csv_folder'] = text

            if 'password' in fields:
                text = fields['password'].text()
                if text:
                    table_data['password'] = text

            if 'send_emblue' in fields:
                send_value = fields['send_emblue'].currentText()
                if send_value == 'Sí':
                    table_data['send_emblue'] = True
                elif send_value == 'No':
                    table_data['send_emblue'] = False

            if 'emblue_id_cuenta' in fields:
                text = fields['emblue_id_cuenta'].text().strip()
                if text:
                    table_data['emblue_id_cuenta'] = text

            if 'emblue_carpeta' in fields:
                text = fields['emblue_carpeta'].text().strip()
                if text:
                    table_data['emblue_carpeta'] = text

            if 'emblue_flg_dropeo' in fields:
                table_data['emblue_flg_dropeo'] = 1 if fields['emblue_flg_dropeo'].isChecked() else 0

            if 'emblue_flg_fecha_base' in fields:
                table_data['emblue_flg_fecha_base'] = 1 if fields['emblue_flg_fecha_base'].isChecked() else 0

            if table_data:
                overrides[table_name] = table_data

        return overrides

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
        params = self.param_form.get_values()
        rendered_process_name = self._render_string(self.process.name, params)
        safe_name = rendered_process_name.replace(' ', '_')

        if len(self.current_results) == 1:
            # Comportamiento legado: diálogo de guardar archivo
            result = self.current_results[0]
            if result["df"].empty:
                return
            export_name_template = result.get("export_name")
            if export_name_template:
                default_name = self._render_string(export_name_template, params) + ".xlsx"
            else:
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
                export_name_template = result.get("export_name")
                if export_name_template:
                    filename = self._render_string(export_name_template, params) + ".xlsx"
                else:
                    safe_label = self._render_string(result["label"], params).replace(' ', '_')
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
        params = self.param_form.get_values()
        rendered_process_name = self._render_string(self.process.name, params)
        safe_name = rendered_process_name.replace(' ', '_')

        if len(self.current_results) == 1:
            result = self.current_results[0]
            if result["df"].empty:
                return
            export_name_template = result.get("export_name")
            if export_name_template:
                default_name = self._render_string(export_name_template, params) + ".csv"
            else:
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
                export_name_template = result.get("export_name")
                if export_name_template:
                    filename = self._render_string(export_name_template, params) + ".csv"
                else:
                    safe_label = self._render_string(result["label"], params).replace(' ', '_')
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