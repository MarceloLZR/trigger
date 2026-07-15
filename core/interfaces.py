"""
core.interfaces
----------------
Contratos (puertos) que la capa de aplicación usa y que infrastructure
implementa. Esto permite, por ejemplo, sustituir pyodbc por otro driver,
o mockear la base de datos en tests, sin tocar application/ ni ui/.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
import pandas as pd

from core.models import ProcessDefinition, Workflow


class IConnectionProvider(ABC):
    @abstractmethod
    def get_connection(self):
        ...

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        ...


class IProcessRepository(ABC):
    @abstractmethod
    def load_all(self) -> list[ProcessDefinition]:
        ...

    @abstractmethod
    def get_by_id(self, process_id: str) -> ProcessDefinition:
        ...


class IWorkflowRepository(ABC):
    @abstractmethod
    def load_all(self) -> list[Workflow]:
        ...


class ISqlTemplateEngine(ABC):
    @abstractmethod
    def render(self, sql_text: str, params: dict[str, Any]) -> str:
        ...


class IExcelExporter(ABC):
    @abstractmethod
    def export(self, df: pd.DataFrame, destination_path: str, sheet_name: str = "Resultado") -> str:
        ...


class ICsvExporter(ABC):
    @abstractmethod
    def export(self, df: pd.DataFrame, destination_path: str) -> str:
        ...


class IEmailSender(ABC):
    @abstractmethod
    def send_email(self, to_addresses: str, subject: str, html_body: str, attachment_paths: list[str] = None) -> bool:
        ...
