"""
ui.views.admin_processes_view
--------------------------------
Vista de administración de procesos: lista, crear, editar,
activar/desactivar y ver historial de versiones.

Flujo principal:
  AdminProcessesView
    → tabla de procesos (get_all_with_status)
    → botón [+ Nuevo] → ProcessEditorDialog
    → botón [✏ Editar] → ProcessEditorDialog (pre-rellenado)
    → botón [Activar/Desactivar] → togglea activo
    → botón [🕘 Historial] → ProcessHistoryDialog
"""
from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox,
    QSplitter, QTabWidget, QSizePolicy, QAbstractItemView,
    QFrame, QScrollArea,
)


class AdminProcessesView(QWidget):
    """
    Vista principal de administración de procesos.
    Emite `processes_changed` cuando se crea/edita/activa un proceso,
    para que MainWindow pueda recargar el listado de ejecución.
    """
    processes_changed = Signal()

    def __init__(self, admin_service, parent=None):
        super().__init__(parent)
        self._svc = admin_service
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # ---- Header ----
        header = QHBoxLayout()
        title = QLabel("🛠️  Administrar Procesos")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_btn = QPushButton("↻  Actualizar")
        self.refresh_btn.setObjectName("SecondaryButton")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        self.new_btn = QPushButton("＋  Nuevo proceso")
        self.new_btn.setObjectName("PrimaryButton")
        self.new_btn.clicked.connect(self._on_new)
        header.addWidget(self.new_btn)

        root.addLayout(header)

        # ---- Subtítulo ----
        sub = QLabel(
            "Gestiona los procesos almacenados en BD_NEGOCIO · APP.PROCESOS. "
            "Los procesos desactivados no aparecen en la lista de ejecución."
        )
        sub.setStyleSheet("color: #7A7268; font-size: 12px;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ---- Tabla ----
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID / Ruta", "Nombre", "Módulo", "Estado",
            "Modificado por", "Fecha modificación"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(300)
        root.addWidget(self.table, 1)

        # ---- Botones de acción por fila ----
        actions = QHBoxLayout()
        self.edit_btn = QPushButton("✏️  Editar seleccionado")
        self.edit_btn.setObjectName("SecondaryButton")
        self.edit_btn.clicked.connect(self._on_edit)
        actions.addWidget(self.edit_btn)

        self.toggle_btn = QPushButton("⏸  Desactivar / Activar")
        self.toggle_btn.setObjectName("SecondaryButton")
        self.toggle_btn.clicked.connect(self._on_toggle)
        actions.addWidget(self.toggle_btn)

        self.history_btn = QPushButton("🕘  Ver historial")
        self.history_btn.setObjectName("SecondaryButton")
        self.history_btn.clicked.connect(self._on_history)
        actions.addWidget(self.history_btn)

        actions.addStretch()
        root.addLayout(actions)

    # ------------------------------------------------------------------
    def refresh(self):
        rows = self._svc.list_all()
        self.table.setRowCount(0)
        for rec in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(rec["proceso_id"]))
            self.table.setItem(r, 1, QTableWidgetItem(rec["nombre"]))
            self.table.setItem(r, 2, QTableWidgetItem(rec["modulo"]))

            estado = "✅ Activo" if rec["activo"] else "⛔ Inactivo"
            estado_item = QTableWidgetItem(estado)
            estado_item.setForeground(
                Qt.darkGreen if rec["activo"] else Qt.red
            )
            self.table.setItem(r, 3, estado_item)
            self.table.setItem(r, 4, QTableWidgetItem(rec.get("modificado_por") or "—"))
            self.table.setItem(r, 5, QTableWidgetItem(
                (rec.get("modificado_en") or "")[:19].replace("T", " ")
            ))

    def _selected_id(self) -> Optional[str]:
        rows = self.table.selectedItems()
        if not rows:
            QMessageBox.information(self, "Selección", "Selecciona un proceso de la tabla primero.")
            return None
        return self.table.item(self.table.currentRow(), 0).text()

    # ------------------------------------------------------------------
    def _on_new(self):
        dlg = ProcessEditorDialog(self._svc, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()
            self.processes_changed.emit()

    def _on_edit(self):
        pid = self._selected_id()
        if pid is None:
            return
        raw = self._svc.get_raw(pid)
        if raw is None:
            QMessageBox.warning(self, "Error", f"No se encontró el proceso '{pid}'.")
            return
        dlg = ProcessEditorDialog(self._svc, raw_data=raw, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()
            self.processes_changed.emit()

    def _on_toggle(self):
        pid = self._selected_id()
        if pid is None:
            return
        # Detectar estado actual
        row = self.table.currentRow()
        estado_item = self.table.item(row, 3).text()
        activo_actual = "Activo" in estado_item
        nuevo_estado = not activo_actual
        label = "activar" if nuevo_estado else "desactivar"

        confirm = QMessageBox.question(
            self, "Confirmar",
            f"¿Deseas {label} el proceso '{pid}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        ok, msg = self._svc.set_active(pid, nuevo_estado)
        if ok:
            self.refresh()
            self.processes_changed.emit()
        else:
            QMessageBox.critical(self, "Error", msg)

    def _on_history(self):
        pid = self._selected_id()
        if pid is None:
            return
        historia = self._svc.get_history(pid)
        dlg = ProcessHistoryDialog(pid, historia, parent=self)
        dlg.exec()


# ---------------------------------------------------------------------------
class ProcessEditorDialog(QDialog):
    """
    Diálogo para crear o editar un proceso.
    Muestra tres áreas:
      - Campos básicos (ID, nombre, módulo, descripción)
      - Editor JSON de configuración (parameters, export, etc.)
      - Editor SQL
    """

    def __init__(self, admin_service, raw_data: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self._svc = admin_service
        self._raw = raw_data
        self._editing = raw_data is not None

        self.setWindowTitle("Editar proceso" if self._editing else "Nuevo proceso")
        self.resize(900, 680)
        self._build_ui()
        if self._editing:
            self._populate(raw_data)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title_text = f"{'Editar' if self._editing else 'Crear'} proceso"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(title)

        # ---- Campos básicos ----
        form = QFormLayout()
        form.setSpacing(8)

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("ej: CMR/Nuevo Proceso")
        if self._editing:
            self.id_input.setEnabled(False)  # No se puede cambiar el ID existente
        form.addRow("ID del proceso *:", self.id_input)

        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Nombre descriptivo del proceso")
        form.addRow("Nombre *:", self.nombre_input)

        self.modulo_input = QLineEdit()
        self.modulo_input.setPlaceholderText("ej: CMR, GobiernoDatos, Modelos")
        form.addRow("Módulo *:", self.modulo_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Descripción breve del proceso")
        form.addRow("Descripción:", self.desc_input)

        root.addLayout(form)

        # ---- Separador ----
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #EAE2D8;")
        root.addWidget(sep)

        # ---- Tabs: JSON + SQL ----
        tabs = QTabWidget()

        # Tab JSON
        json_tab = QWidget()
        json_layout = QVBoxLayout(json_tab)
        json_layout.setContentsMargins(8, 8, 8, 8)

        json_hint = QLabel(
            "📋  Define aquí los parámetros, tablas de resultado, opciones de exportación, etc.\n"
            "Debe ser un JSON válido. Consulta un proceso existente como referencia."
        )
        json_hint.setStyleSheet("color: #7A7268; font-size: 11px;")
        json_hint.setWordWrap(True)
        json_layout.addWidget(json_hint)

        self.json_editor = QTextEdit()
        self.json_editor.setObjectName("ConsoleWidget")
        self.json_editor.setPlaceholderText('{\n  "parameters": [],\n  "final_tables": []\n}')
        self.json_editor.setFontFamily("Consolas")
        self.json_editor.setFontPointSize(11)
        json_layout.addWidget(self.json_editor, 1)

        self.format_json_btn = QPushButton("⟳  Formatear JSON")
        self.format_json_btn.setObjectName("SecondaryButton")
        self.format_json_btn.setFixedWidth(160)
        self.format_json_btn.clicked.connect(self._format_json)
        json_layout.addWidget(self.format_json_btn)

        tabs.addTab(json_tab, "📋  Configuración (JSON)")

        # Tab SQL
        sql_tab = QWidget()
        sql_layout = QVBoxLayout(sql_tab)
        sql_layout.setContentsMargins(8, 8, 8, 8)

        sql_hint = QLabel("💾  Escribe o pega aquí el SQL del proceso. Usa {{PARAMETRO}} para variables.")
        sql_hint.setStyleSheet("color: #7A7268; font-size: 11px;")
        sql_layout.addWidget(sql_hint)

        self.sql_editor = QTextEdit()
        self.sql_editor.setObjectName("ConsoleWidget")
        self.sql_editor.setPlaceholderText("SELECT * FROM mi_tabla WHERE columna = {{PARAMETRO}}")
        self.sql_editor.setFontFamily("Consolas")
        self.sql_editor.setFontPointSize(11)
        sql_layout.addWidget(self.sql_editor, 1)

        tabs.addTab(sql_tab, "💾  SQL")

        root.addWidget(tabs, 1)

        # ---- Botones OK / Cancelar ----
        self.button_box = QDialogButtonBox()
        save_btn = self.button_box.addButton("💾  Guardar", QDialogButtonBox.AcceptRole)
        save_btn.setObjectName("PrimaryButton")
        cancel_btn = self.button_box.addButton("Cancelar", QDialogButtonBox.RejectRole)
        cancel_btn.setObjectName("SecondaryButton")
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

    def _populate(self, raw: dict):
        self.id_input.setText(raw.get("proceso_id", ""))
        self.nombre_input.setText(raw.get("nombre", ""))
        self.modulo_input.setText(raw.get("modulo", ""))
        self.desc_input.setText(raw.get("descripcion", ""))
        # Formatear JSON bonito
        try:
            parsed = json.loads(raw.get("config_json", "{}"))
            self.json_editor.setPlainText(json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception:
            self.json_editor.setPlainText(raw.get("config_json", ""))
        self.sql_editor.setPlainText(raw.get("sql_text", ""))

    def _format_json(self):
        txt = self.json_editor.toPlainText().strip()
        if not txt:
            return
        try:
            parsed = json.loads(txt)
            self.json_editor.setPlainText(json.dumps(parsed, ensure_ascii=False, indent=2))
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "JSON inválido", f"No se pudo formatear:\n{exc}")

    def _on_save(self):
        ok, msg = self._svc.save_process(
            proceso_id=self.id_input.text(),
            nombre=self.nombre_input.text(),
            modulo=self.modulo_input.text(),
            descripcion=self.desc_input.text(),
            config_json=self.json_editor.toPlainText(),
            sql_text=self.sql_editor.toPlainText(),
        )
        if ok:
            QMessageBox.information(self, "Guardado", "Proceso guardado correctamente.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error al guardar", msg)


# ---------------------------------------------------------------------------
class ProcessHistoryDialog(QDialog):
    """Muestra el historial de versiones de un proceso."""

    def __init__(self, proceso_id: str, history: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Historial — {proceso_id}")
        self.resize(860, 500)
        self._history = history
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)

        title = QLabel(f"🕘  Historial de versiones")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        root.addWidget(title)

        if not self._history:
            root.addWidget(QLabel("No hay registros de historial para este proceso."))
            close_btn = QPushButton("Cerrar")
            close_btn.setObjectName("SecondaryButton")
            close_btn.clicked.connect(self.accept)
            root.addWidget(close_btn)
            return

        splitter = QSplitter(Qt.Horizontal)

        # Lista de versiones
        self.list_table = QTableWidget(0, 4)
        self.list_table.setHorizontalHeaderLabels(["#", "Acción", "Por", "Fecha"])
        self.list_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.list_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.list_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.list_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.list_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_table.verticalHeader().setVisible(False)
        self.list_table.setMinimumWidth(280)
        self.list_table.itemSelectionChanged.connect(self._on_select)

        for rec in self._history:
            r = self.list_table.rowCount()
            self.list_table.insertRow(r)
            self.list_table.setItem(r, 0, QTableWidgetItem(str(rec["historial_id"])))
            self.list_table.setItem(r, 1, QTableWidgetItem(rec.get("accion", "")))
            self.list_table.setItem(r, 2, QTableWidgetItem(rec.get("modificado_por") or "—"))
            self.list_table.setItem(r, 3, QTableWidgetItem(
                (rec.get("modificado_en") or "")[:19].replace("T", " ")
            ))

        splitter.addWidget(self.list_table)

        # Panel derecho: detalle de la versión seleccionada
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        right_tabs = QTabWidget()
        self.hist_json_view = QTextEdit()
        self.hist_json_view.setReadOnly(True)
        self.hist_json_view.setFontFamily("Consolas")
        self.hist_json_view.setFontPointSize(10)
        self.hist_json_view.setObjectName("ConsoleWidget")

        self.hist_sql_view = QTextEdit()
        self.hist_sql_view.setReadOnly(True)
        self.hist_sql_view.setFontFamily("Consolas")
        self.hist_sql_view.setFontPointSize(10)
        self.hist_sql_view.setObjectName("ConsoleWidget")

        right_tabs.addTab(self.hist_json_view, "📋  Config JSON")
        right_tabs.addTab(self.hist_sql_view, "💾  SQL")
        right_layout.addWidget(right_tabs)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)

        root.addWidget(splitter, 1)

        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn)

        # Seleccionar primera fila automáticamente
        if self.list_table.rowCount() > 0:
            self.list_table.selectRow(0)

    def _on_select(self):
        row = self.list_table.currentRow()
        if row < 0 or row >= len(self._history):
            return
        rec = self._history[row]
        # JSON
        try:
            parsed = json.loads(rec.get("config_json") or "{}")
            self.hist_json_view.setPlainText(json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception:
            self.hist_json_view.setPlainText(rec.get("config_json") or "")
        # SQL
        self.hist_sql_view.setPlainText(rec.get("sql_text") or "")
