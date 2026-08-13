"""
ui.widgets.parameter_form
----------------------------
Construye dinámicamente el formulario de parámetros de un proceso,
a partir de su lista de Parameter (ver core.models).

Patrón Factory: ParameterWidgetFactory decide qué QWidget crear según
Parameter.type, sin que el resto del código conozca esos detalles.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any


def resolve_dynamic_value(value: Any) -> Any:
    """Resuelve valores dinámicos como 'today', 'now', etc.
    
    Soporta:
    - "today" → fecha de hoy en formato yyyyMMdd
    - "today_iso" → fecha de hoy en formato yyyy-MM-dd
    - "now" → timestamp actual (yyyyMMdd_HHmmss)
    """
    if value == "today":
        return date.today().strftime("%Y%m%d")
    if value == "today_iso":
        return date.today().strftime("%Y-%m-%d")
    if value == "now":
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    return value

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QDateEdit, QComboBox, QCheckBox,
    QSpinBox, QDoubleSpinBox, QLabel, QVBoxLayout
)

from core.models import Parameter, ParameterType


class ParameterWidgetFactory:
    """Crea el widget adecuado para cada tipo de parámetro."""

    @staticmethod
    def create(param: Parameter, initial_value: Any = None) -> QWidget:
        value = initial_value if initial_value is not None else param.default

        if param.type == ParameterType.DATE:
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd")
            widget.setDate(ParameterWidgetFactory._to_qdate(value))
            return widget

        if param.type == ParameterType.MONTH:
            widget = QComboBox()
            widget.setEditable(False)
            months = ParameterWidgetFactory._last_24_months()
            widget.addItems(months)
            target = ParameterWidgetFactory._resolve_month_default(value)
            if target in months:
                widget.setCurrentText(target)
            return widget

        if param.type == ParameterType.COMBO:
            widget = QComboBox()
            widget.addItems(param.options)
            if value in param.options:
                widget.setCurrentText(str(value))
            return widget

        if param.type == ParameterType.NUMBER:
            widget = QDoubleSpinBox()
            widget.setRange(-1_000_000_000, 1_000_000_000)
            widget.setDecimals(2)
            if value not in (None, ""):
                widget.setValue(float(value))
            return widget

        if param.type == ParameterType.CHECKBOX:
            widget = QCheckBox()
            widget.setChecked(bool(value) if value is not None else False)
            return widget

        # TEXT por defecto
        widget = QLineEdit()
        if value is not None:
            widget.setText(str(value))
        return widget

    @staticmethod
    def extract_value(param: Parameter, widget: QWidget):
        if param.type == ParameterType.DATE:
            return widget.date().toString("yyyy-MM-dd")
        if param.type == ParameterType.MONTH:
            return widget.currentText().replace("-", "")
        if param.type == ParameterType.COMBO:
            return widget.currentText()
        if param.type == ParameterType.NUMBER:
            return widget.value()
        if param.type == ParameterType.CHECKBOX:
            return widget.isChecked()
        return widget.text()

    @staticmethod
    def _to_qdate(value: Any) -> QDate:
        if isinstance(value, str) and value not in ("today", "current", ""):
            try:
                return QDate.fromString(value, "yyyy-MM-dd")
            except Exception:
                pass
        return QDate.currentDate()

    @staticmethod
    def _last_24_months() -> list[str]:
        today = date.today()
        months = []
        y, m = today.year, today.month
        for _ in range(24):
            months.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return months

    @staticmethod
    def _resolve_month_default(value: Any) -> str:
        if value in (None, "current", ""):
            today = date.today()
            return f"{today.year:04d}-{today.month:02d}"
        return str(value)


class ParameterFormWidget(QWidget):
    """Formulario completo: crea un QFormLayout con todos los parámetros
    del proceso y expone get_values() / set_values()."""

    def __init__(self, parameters: list[Parameter], initial_values: dict | None = None, parent=None):
        super().__init__(parent)
        self.parameters = parameters
        self._widgets: dict[str, QWidget] = {}
        initial_values = initial_values or {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        for param in parameters:
            # Solo mostrar parámetros visibles
            if not param.visible:
                # Aun así almacenar el valor por defecto para get_values()
                widget = ParameterWidgetFactory.create(param, initial_values.get(param.name))
                self._widgets[param.name] = widget
                continue
            
            widget = ParameterWidgetFactory.create(param, initial_values.get(param.name))
            self._widgets[param.name] = widget
            label = QLabel(param.label + (" *" if param.required else ""))
            form.addRow(label, widget)

        layout.addLayout(form)

    def get_values(self) -> dict[str, Any]:
        values = {}
        for param in self.parameters:
            extracted = ParameterWidgetFactory.extract_value(param, self._widgets[param.name])
            # Resolver valores dinámicos (today, now, etc.)
            resolved = resolve_dynamic_value(extracted)
            values[param.name] = resolved
        return values

    def validate(self) -> tuple[bool, str]:
        values = self.get_values()
        for param in self.parameters:
            if param.required and values.get(param.name) in (None, ""):
                return False, f"El campo '{param.label}' es obligatorio."
        return True, ""
