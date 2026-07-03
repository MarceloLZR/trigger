"""
ui.views.quick_execution_view
---------------------------------
Lista todos los procesos disponibles con checkbox. El usuario marca
varios y presiona "Ejecutar seleccionados" -> se ejecutan en secuencia
usando WorkflowRunner (mismo motor que usan los Workflows definidos).

Como cada proceso puede requerir parámetros distintos, antes de ejecutar
se abre el formulario de cada uno seleccionado (o se usan los últimos
parámetros guardados si el usuario elige "usar últimos valores").
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QProgressBar, QMessageBox, QCheckBox
)

from core.models import ProcessDefinition
from core.interfaces import IConnectionProvider, ISqlTemplateEngine
from application.workflow_executor import WorkflowRunner
from application.history_service import HistoryService
from ui.widgets.console_widget import ConsoleWidget


class QuickExecutionView(QWidget):
    def __init__(
        self,
        connection_provider: IConnectionProvider,
        template_engine: ISqlTemplateEngine,
        history_service: HistoryService,
        parent=None,
    ):
        super().__init__(parent)
        self.connection_provider = connection_provider
        self.template_engine = template_engine
        self.history_service = history_service
        self.processes: list[ProcessDefinition] = []
        self.runner: WorkflowRunner | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Ejecución rápida")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        subtitle = QLabel("Selecciona los procesos que quieres ejecutar en secuencia, usando los últimos parámetros guardados.")
        subtitle.setObjectName("CardDesc")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.list_widget = QListWidget()
        root.addWidget(self.list_widget, 1)

        self.stop_on_error_chk = QCheckBox("Detener si un proceso falla")
        self.stop_on_error_chk.setChecked(True)
        root.addWidget(self.stop_on_error_chk)

        action_row = QHBoxLayout()
        self.run_btn = QPushButton("▶ Ejecutar seleccionados")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.clicked.connect(self._on_run_clicked)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        action_row.addWidget(self.run_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        self.overall_label = QLabel("")
        root.addWidget(self.overall_label)
        self.progress_bar = QProgressBar()
        root.addWidget(self.progress_bar)

        self.console = ConsoleWidget()
        self.console.setMaximumHeight(200)
        root.addWidget(self.console)

    def set_processes(self, processes: list[ProcessDefinition]):
        self.processes = processes
        self.list_widget.clear()
        for proc in processes:
            item = QListWidgetItem(f"{proc.name}   ·   {proc.module}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, proc.id)
            self.list_widget.addItem(item)

    def _on_run_clicked(self):
        selected_ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_ids.append(item.data(Qt.UserRole))

        if not selected_ids:
            QMessageBox.information(self, "Sin selección", "Selecciona al menos un proceso.")
            return

        steps = []
        for pid in selected_ids:
            process = next(p for p in self.processes if p.id == pid)
            params = self.history_service.get_last_params(pid)
            missing = [p.label for p in process.parameters if p.required and p.name not in params]
            if missing:
                QMessageBox.warning(
                    self, "Parámetros faltantes",
                    f"'{process.name}' no tiene parámetros guardados para: {', '.join(missing)}.\n"
                    "Ejecuta ese proceso individualmente al menos una vez, o complétalo desde su módulo."
                )
                return
            steps.append((process, params))

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.console.clear_log()

        self.runner = WorkflowRunner(
            steps, self.connection_provider, self.template_engine,
            stop_on_error=self.stop_on_error_chk.isChecked(),
        )
        self.runner.step_started.connect(lambda i, name: self.console.append_log(f"Paso {i+1}: {name}"))
        self.runner.step_log.connect(self.console.append_log)
        self.runner.step_progress.connect(self.progress_bar.setValue)
        self.runner.overall_progress.connect(
            lambda cur, total: self.overall_label.setText(f"Paso {cur} de {total}")
        )
        self.runner.step_finished.connect(self._on_step_finished)
        self.runner.step_failed.connect(self._on_step_failed)
        self.runner.all_finished.connect(self._on_all_finished)
        self.runner.start()

    def _on_step_finished(self, index, df, record):
        self.history_service.record_execution(record)

    def _on_step_failed(self, index, message, record):
        self.history_service.record_execution(record)
        self.console.append_log(f"FALLÓ paso {index + 1}: {message}")

    def _on_all_finished(self, records):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        ok = sum(1 for r in records if r.status.value == "success")
        self.console.append_log(f"Ejecución en lote finalizada: {ok}/{len(records)} exitosos.")

    def _on_cancel(self):
        if self.runner:
            self.runner.cancel()
            self.cancel_btn.setEnabled(False)
