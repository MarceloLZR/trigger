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
class FinalTable:
    """Representa una tabla de resultado que el proceso genera."""
    table: str    # nombre de la tabla temporal, p.ej. ##alpes
    label: str    # etiqueta legible para UI/nombre de archivo

    @staticmethod
    def from_dict(data: dict) -> "FinalTable":
        return FinalTable(
            table=data["table"],
            label=data.get("label", data["table"]),
        )


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
    """Representa un proceso SQL detectado en /processes/<Modulo>/<Proceso>/

    Soporta dos modos:
    - final_table (str): proceso de una sola tabla (legado).
    - final_tables (list[FinalTable]): proceso multi-tabla.

    El from_dict normaliza ambos casos a final_tables para que el
    executor y la UI usen siempre la misma interfaz.
    """
    id: str                        # identificador único (ruta relativa normalizada)
    name: str
    module: str
    description: str
    parameters: list[Parameter]
    final_tables: list[FinalTable]  # siempre presente (>=1 elemento)
    sql_path: Path
    icon_path: Optional[Path] = None
    show_preview: bool = True
    export_excel: bool = True
    auto_export_folder: Optional[str] = None
    export_csv: bool = False
    auto_export_csv_folder: Optional[str] = None
    send_email: bool = False
    email_template: Optional[str] = None
    email_default_to: Optional[str] = None
    email_subject: Optional[str] = None
    folder: Optional[Path] = None

    @property
    def final_table(self) -> str:
        """Compatibilidad con código antiguo que accede a final_table (str)."""
        return self.final_tables[0].table if self.final_tables else ""

    @staticmethod
    def from_dict(data: dict, process_id: str, sql_path: Path,
                   icon_path: Optional[Path], folder: Path) -> "ProcessDefinition":
        # Soporta tanto "final_tables" (lista) como "final_table" (string)
        if "final_tables" in data:
            final_tables = [FinalTable.from_dict(t) for t in data["final_tables"]]
        elif "final_table" in data:
            ft = data["final_table"]
            final_tables = [FinalTable(table=ft, label="Resultado")]
        else:
            raise KeyError("El proceso debe definir 'final_table' o 'final_tables' en process.json")

        return ProcessDefinition(
            id=process_id,
            name=data["name"],
            module=data["module"],
            description=data.get("description", ""),
            parameters=[Parameter.from_dict(p) for p in data.get("parameters", [])],
            final_tables=final_tables,
            sql_path=sql_path,
            icon_path=icon_path,
            show_preview=data.get("show_preview", True),
            export_excel=data.get("export_excel", True),
            auto_export_folder=data.get("auto_export_folder"),
            export_csv=data.get("export_csv", False),
            auto_export_csv_folder=data.get("auto_export_csv_folder"),
            send_email=data.get("send_email", False),
            email_template=data.get("email_template"),
            email_default_to=data.get("email_default_to"),
            email_subject=data.get("email_subject"),
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