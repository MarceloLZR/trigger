"""
application.workflow_executor
--------------------------------
Ejecuta un Workflow (o una lista arbitraria de procesos seleccionados
en "Ejecución Rápida") en SECUENCIA, uno tras otro, reutilizando
ProcessWorker para cada paso.

Patrón Command: cada paso del workflow es una unidad ejecutable e
independiente; el executor solo orquesta el orden y la cancelación.
"""
from __future__ import annotations
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from core.models import ProcessDefinition, ExecutionRecord
from core.interfaces import IConnectionProvider, ISqlTemplateEngine, IProcessRepository
from application.process_executor import ProcessWorker


class WorkflowRunner(QObject):
    step_started = Signal(int, str)             # (índice, nombre_proceso)
    step_log = Signal(str)
    step_progress = Signal(int)                  # progreso del paso actual (0-100)
    overall_progress = Signal(int, int)           # (paso_actual, total_pasos)
    step_finished = Signal(int, object, object)   # (índice, DataFrame, ExecutionRecord)
    step_failed = Signal(int, str, object)
    all_finished = Signal(list)                   # lista de ExecutionRecord

    def __init__(
        self,
        steps: list[tuple[ProcessDefinition, dict[str, Any]]],
        connection_provider: IConnectionProvider,
        template_engine: ISqlTemplateEngine,
        stop_on_error: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.steps = steps
        self.connection_provider = connection_provider
        self.template_engine = template_engine
        self.stop_on_error = stop_on_error
        self._current_index = -1
        self._current_worker: Optional[ProcessWorker] = None
        self._records: list[ExecutionRecord] = []
        self._cancelled = False

    def start(self):
        self._run_next()

    def cancel(self):
        self._cancelled = True
        if self._current_worker:
            self._current_worker.cancel()

    def _run_next(self):
        self._current_index += 1
        total = len(self.steps)

        if self._cancelled or self._current_index >= total:
            self.all_finished.emit(self._records)
            return

        process, params = self.steps[self._current_index]
        self.overall_progress.emit(self._current_index + 1, total)
        self.step_started.emit(self._current_index, process.name)

        worker = ProcessWorker(process, params, self.connection_provider, self.template_engine)
        self._current_worker = worker
        worker.log.connect(self.step_log)
        worker.progress.connect(self.step_progress)
        worker.finished_ok.connect(lambda df, rec: self._on_step_ok(df, rec))
        worker.failed.connect(lambda msg, rec: self._on_step_failed(msg, rec))
        worker.start()

    def _on_step_ok(self, df, record):
        self._records.append(record)
        self.step_finished.emit(self._current_index, df, record)
        self._run_next()

    def _on_step_failed(self, msg, record):
        self._records.append(record)
        self.step_failed.emit(self._current_index, msg, record)
        if self.stop_on_error:
            self.all_finished.emit(self._records)
        else:
            self._run_next()
