"""
infrastructure.sql_template_engine
------------------------------------
Reemplaza variables tipo {{NOMBRE}} dentro de un script SQL por los
valores capturados en el formulario de parámetros.

Reglas:
- {{COD_MES}}                 -> reemplazo simple de texto/número
- Fechas se formatean como YYYYMMDD (formato típico para BETWEEN en SQL Server)
- Si una variable requerida no fue provista, se lanza MissingParameterError
  ANTES de tocar la base de datos (fail fast).
"""
from __future__ import annotations
import re
from datetime import date, datetime
from typing import Any

from core.interfaces import ISqlTemplateEngine

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


class MissingParameterError(Exception):
    pass


class SqlTemplateEngine(ISqlTemplateEngine):
    def render(self, sql_text: str, params: dict[str, Any]) -> str:
        missing: list[str] = []

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name not in params or params[var_name] in (None, ""):
                missing.append(var_name)
                return match.group(0)
            return self._format_value(params[var_name])

        rendered = VARIABLE_PATTERN.sub(_replace, sql_text)

        if missing:
            raise MissingParameterError(
                f"Faltan valores para las variables: {', '.join(sorted(set(missing)))}"
            )
        return rendered

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y%m%d")
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, str):
            # Si ya viene como fecha ISO (YYYY-MM-DD) desde el QDateEdit, la normalizamos
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return value.replace("-", "")
            return value
        return str(value)
