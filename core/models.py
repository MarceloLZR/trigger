"""
core.models
-----------
Modelos de dominio puros. No dependen de PySide6, pyodbc ni pandas.
Representan el "qué es" un proceso, un parámetro y un workflow,
independientemente de cómo se lean, ejecuten o rendericen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pathlib import Path


class ParameterType(str, Enum):
    TEXT = "text"
    DATE = "date"
    MONTH = "month"
    NUMBER = "number"
    COMBO = "combo"
    CHECKBOX = "checkbox"


@dataclass
class Parameter:
    name: str                      # nombre de la variable en el SQL -> {{name}}
    label: str                     # etiqueta visible en el formulario
    type: ParameterType = ParameterType.TEXT
    default: Optional[Any] = None
    required: bool = True
    options: list[str] = field(default_factory=list)   # para type == combo
    help_text: str = ""

    @staticmethod
    def from_dict(data: dict) -> "Parameter":
        return Parameter(
            name=data["name"],
            label=data.get("label", data["name"]),
            type=ParameterType(data.get("type", "text")),
            default=data.get("default"),
            required=data.get("required", True),
            options=data.get("options", []),
            help_text=data.get("help_text", ""),
        )


@dataclass
class ProcessDefinition:
    """Representa un proceso SQL detectado en /processes/<Modulo>/<Proceso>/"""
    id: str                        # identificador único (ruta relativa normalizada)
    name: str
    module: str
    description: str
    parameters: list[Parameter]
    final_table: str
    sql_path: Path
    icon_path: Optional[Path] = None
    show_preview: bool = True
    export_excel: bool = True
    folder: Optional[Path] = None

    @staticmethod
    def from_dict(data: dict, process_id: str, sql_path: Path,
                   icon_path: Optional[Path], folder: Path) -> "ProcessDefinition":
        return ProcessDefinition(
            id=process_id,
            name=data["name"],
            module=data["module"],
            description=data.get("description", ""),
            parameters=[Parameter.from_dict(p) for p in data.get("parameters", [])],
            final_table=data["final_table"],
            sql_path=sql_path,
            icon_path=icon_path,
            show_preview=data.get("show_preview", True),
            export_excel=data.get("export_excel", True),
            folder=folder,
        )


@dataclass
class WorkflowStep:
    process_id: str
    param_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    id: str
    name: str
    description: str
    steps: list[WorkflowStep]

    @staticmethod
    def from_dict(data: dict, workflow_id: str) -> "Workflow":
        steps = [
            WorkflowStep(
                process_id=s["process_id"],
                param_overrides=s.get("parameters", {}),
            )
            for s in data.get("steps", [])
        ]
        return Workflow(
            id=workflow_id,
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
        )


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    RUNNING = "running"


@dataclass
class ExecutionRecord:
    process_id: str
    process_name: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    row_count: int = 0
    status: ExecutionStatus = ExecutionStatus.RUNNING
    error_message: str = ""
    parameters_used: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "process_id": self.process_id,
            "process_name": self.process_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "row_count": self.row_count,
            "status": self.status.value,
            "error_message": self.error_message,
            "parameters_used": self.parameters_used,
        }
