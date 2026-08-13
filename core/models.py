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
    """Representa una tabla de resultado que el proceso genera.

    Cada tabla puede configurar de forma independiente:
    - export_name     : nombre de archivo al exportar (soporta variables {param})
    - password        : contraseña para proteger el archivo (visible en JSON)
    - export_excel_folder : carpeta destino Excel de esta tabla (override del proceso)
    - export_csv_folder   : carpeta destino CSV de esta tabla (override del proceso)
    - send_emblue         : True/False/None — None hereda la config del proceso
    - emblue_id_cuenta, emblue_carpeta, emblue_flg_dropeo, emblue_flg_fecha_base
    """
    table: str
    label: str
    export_name: Optional[str] = None

    # Per-table file protection
    password: Optional[str] = None

    # Per-table routing overrides (None = usar el valor del proceso)
    export_excel_folder: Optional[str] = None
    export_csv_folder: Optional[str] = None

    # Per-table Emblue overrides
    send_emblue: Optional[bool] = None
    # Per-table generic send flag (True/False/None -> None hereda del proceso)
    send_sftp: Optional[bool] = None
    # Formato SFTP: "csv" o "excel" (default: "csv")
    sftp_format: str = "csv"
    emblue_id_cuenta: Optional[int] = None
    emblue_carpeta: Optional[str] = None
    emblue_flg_dropeo: int = 0
    emblue_flg_fecha_base: int = 0
    # Per-table generic account overrides
    account_type: Optional[str] = None
    account_id: Optional[int] = None
    account_folder: Optional[str] = None
    # Optional explicit table that contains the credentials (e.g. DM.CUENTAS_...)
    account_table: Optional[str] = None
    account_flags: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> "FinalTable":
        send_emblue = data.get("send_emblue")
        if send_emblue is not None:
            send_emblue = bool(send_emblue)
        send_sftp = data.get('send_sftp')
        if send_sftp is not None:
            send_sftp = bool(send_sftp)
        return FinalTable(
            table=data["table"],
            label=data.get("label", data["table"]),
            export_name=data.get("export_name"),
            password=data.get("password"),
            export_excel_folder=data.get("export_excel_folder"),
            export_csv_folder=data.get("export_csv_folder"),
            send_emblue=send_emblue,
            send_sftp=send_sftp,
            sftp_format=data.get("sftp_format", "csv"),
            emblue_id_cuenta=data.get("emblue_id_cuenta"),
            emblue_carpeta=data.get("emblue_carpeta"),
            emblue_flg_dropeo=data.get("emblue_flg_dropeo", 0),
            emblue_flg_fecha_base=data.get("emblue_flg_fecha_base", 0),
            account_type=data.get('account_type'),
            account_id=data.get('account_id'),
            account_table=data.get('account_table'),
            account_folder=data.get('account_folder'),
            account_flags=data.get('account_flags', {}),
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
    visible: bool = True           # Si False, no se muestra en la UI pero se usa

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
            visible=data.get("visible", True),
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
    
    # Emblue Settings
    send_emblue: bool = False
    # Generic send flag
    send_sftp: bool = False
    emblue_id_cuenta: Optional[int] = None
    emblue_carpeta: Optional[str] = None
    emblue_usuario: Optional[str] = None
    emblue_pwd: Optional[str] = None
    emblue_host: Optional[str] = None
    emblue_flg_dropeo: int = 0
    emblue_flg_fecha_base: int = 0

    # Generic account settings (nuevos campos compatibles)
    account_type: Optional[str] = None
    account_id: Optional[int] = None
    account_folder: Optional[str] = None
    account_user: Optional[str] = None
    account_pwd: Optional[str] = None
    account_host: Optional[str] = None
    account_table: Optional[str] = None
    account_flags: dict[str, Any] = field(default_factory=dict)

    # Password protection for generated files
    export_password_enabled: bool = False
    export_password_default: Optional[str] = None

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
            send_emblue=data.get("send_emblue", False),
            send_sftp=data.get("send_sftp", data.get("send_emblue", False)),
            emblue_id_cuenta=data.get("emblue_id_cuenta"),
            emblue_carpeta=data.get("emblue_carpeta"),
            emblue_usuario=data.get("emblue_usuario"),
            emblue_pwd=data.get("emblue_pwd"),
            emblue_host=data.get("emblue_host"),
            emblue_flg_dropeo=data.get("emblue_flg_dropeo", 0),
            emblue_flg_fecha_base=data.get("emblue_flg_fecha_base", 0),
            account_type=data.get('account_type'),
            account_id=data.get('account_id'),
            account_table=data.get('account_table'),
            account_folder=data.get('account_folder'),
            account_user=data.get('account_user'),
            account_pwd=data.get('account_pwd'),
            account_host=data.get('account_host'),
            account_flags=data.get('account_flags', {}),
            export_password_enabled=data.get("export_password_enabled", False),
            export_password_default=data.get("export_password_default"),
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
    export_options: dict[str, Any] = field(default_factory=dict)

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
            "export_options": self.export_options,
        }