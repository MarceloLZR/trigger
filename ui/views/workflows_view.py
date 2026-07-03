"""
ui.views.workflows_view
---------------------------
Lista los workflows definidos en /workflows/*.json (por ejemplo
"Cierre Mensual") y permite ejecutarlos en secuencia con un clic.
Los parámetros de cada paso se resuelven así:
  1. overrides definidos en el propio workflow.json
  2. últimos parámetros guardados de ese proceso
"""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QProgressBar, QMessageBox
)

from core.models import Workflow, ProcessDefinition
from core.interfaces import IConnectionProvider, ISqlTemplateEngine, IProcessRepository
from application.workflow_executor import WorkflowRunner
from application.history_service import HistoryService
from ui.widgets.console_widget import ConsoleWidget


class WorkflowsView(QWidget):
    def __init__(
        self,
        connection_provider: IConnectionProvider,
        template_engine: ISqlTemplateEngine,
        process_repository: IProcessRepository,
        history_service: HistoryService,
        parent=None,
    ):
        super().__init__(parent)
        self.connection_provider = connection_provider
        self.template_engine = template_engine
        self.process_repository = process_repository
        self.history_service = history_service
        self.workflows: list[Workflow] = []
        self.runner: WorkflowRunner | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Workflows")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)
        subtitle = QLabel("Secuencias predefinidas de procesos, por ejemplo el Cierre Mensual.")
        subtitle.setObjectName("CardDesc")
        root.addWidget(subtitle)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(lambda item: self._run_workflow(item.data(256)))
        root.addWidget(self.list_widget, 1)

        action_row = QHBoxLayout()
        self.run_btn = QPushButton("▶ Ejecutar workflow seleccionado")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.clicked.connect(self._on_run_clicked)
        action_row.addWidget(self.run_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        self.overall_label = QLabel("")
        root.addWidget(self.overall_label)
        self.progress_bar = QProgressBar()
        root.addWidget(self.progress_bar)

        self.console = ConsoleWidget()
        self.console.setMaximumHeight(200)
        root.addWidget(self.console)

    def set_workflows(self, workflows: list[Workflow]):
        self.workflows = workflows
        self.list_widget.clear()
        for wf in workflows:
            steps_desc = " → ".join(s.process_id for s in wf.steps)
            item = QListWidgetItem(f"{wf.name}  ({len(wf.steps)} pasos)\n{steps_desc}")
            item.setData(256, wf.id)
            self.list_widget.addItem(item)

    def _on_run_clicked(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "Sin selección", "Selecciona un workflow de la lista.")
            return
        self._run_workflow(item.data(256))

    def _run_workflow(self, workflow_id: str):
        workflow = next((w for w in self.workflows if w.id == workflow_id), None)
        if not workflow:
            return

        steps: list[tuple[ProcessDefinition, dict]] = []
        for step in workflow.steps:
            try:
                process = self.process_repository.get_by_id(step.process_id)
            except KeyError:
                QMessageBox.critical(self, "Error", f"Proceso no encontrado: {step.process_id}")
                return
            params = dict(self.history_service.get_last_params(process.id))
            params.update(step.param_overrides)
            steps.append((process, params))

        self.run_btn.setEnabled(False)
        self.console.clear_log()
        self.console.append_log(f"Iniciando workflow: {workflow.name}")

        self.runner = WorkflowRunner(steps, self.connection_provider, self.template_engine, stop_on_error=True)
        self.runner.step_started.connect(lambda i, name: self.console.append_log(f"Paso {i+1}: {name}"))
        self.runner.step_log.connect(self.console.append_log)
        self.runner.step_progress.connect(self.progress_bar.setValue)
        self.runner.overall_progress.connect(
            lambda cur, total: self.overall_label.setText(f"Paso {cur} de {total}")
        )
        self.runner.step_finished.connect(lambda i, df, rec: self.history_service.record_execution(rec))
        self.runner.step_failed.connect(lambda i, msg, rec: self.history_service.record_execution(rec))
        self.runner.all_finished.connect(self._on_all_finished)
        self.runner.start()

    def _on_all_finished(self, records):
        self.run_btn.setEnabled(True)
        ok = sum(1 for r in records if r.status.value == "success")
        self.console.append_log(f"Workflow finalizado: {ok}/{len(records)} pasos exitosos.")
