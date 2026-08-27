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
    QSpinBox, QDoubleSpinBox, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)

from core.models import Parameter, ParameterType


class RulesTableWidget(QWidget):
    def __init__(self, default_value=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "PCT Mín", "PCT Máx", "Monto Mín", "Elección", 
            "Deciles (ej: 1,2)", "Tasa / TCEA", "Cuotas", "Plantilla Mensaje"
        ])
        
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Adjust default widths
        self.table.setColumnWidth(0, 60)   # PCT Min
        self.table.setColumnWidth(1, 60)   # PCT Max
        self.table.setColumnWidth(2, 80)   # Monto Min
        self.table.setColumnWidth(3, 80)   # Eleccion
        self.table.setColumnWidth(4, 110)  # Deciles
        self.table.setColumnWidth(5, 150)  # Tasa
        self.table.setColumnWidth(6, 60)   # Cuotas
        
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Añadir Regla")
        self.add_btn.clicked.connect(self.add_row)
        btn_layout.addWidget(self.add_btn)
        
        self.del_btn = QPushButton("- Eliminar Regla")
        self.del_btn.clicked.connect(self.del_row)
        btn_layout.addWidget(self.del_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setMinimumHeight(220)
        
        if default_value:
            self.set_value(default_value)
        else:
            self.add_row()

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(8):
            self.table.setItem(row, col, QTableWidgetItem(""))
            
    def del_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
        elif self.table.rowCount() > 0:
            self.table.removeRow(self.table.rowCount() - 1)
            
    def get_value(self) -> list[dict]:
        rows = []
        for r in range(self.table.rowCount()):
            row_data = {
                "PCT_MIN": self._get_cell_float(r, 0),
                "PCT_MAX": self._get_cell_float(r, 1),
                "LINEA_MIN": self._get_cell_float(r, 2),
                "ELECCION": self._get_cell_str(r, 3),
                "DECIL_LIST": self._get_cell_str(r, 4),
                "TASA_TEXT": self._get_cell_str(r, 5),
                "CUOTAS": self._get_cell_int(r, 6),
                "MENSAJE_TEMPLATE": self._get_cell_str(r, 7),
            }
            if row_data["MENSAJE_TEMPLATE"]:
                rows.append(row_data)
        return rows
        
    def set_value(self, val):
        self.table.setRowCount(0)
        if isinstance(val, str):
            import json
            try:
                val = json.loads(val)
            except Exception:
                val = []
        if not isinstance(val, list):
            val = []
            
        for row_data in val:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(self._str(row_data.get("PCT_MIN"))))
            self.table.setItem(row, 1, QTableWidgetItem(self._str(row_data.get("PCT_MAX"))))
            self.table.setItem(row, 2, QTableWidgetItem(self._str(row_data.get("LINEA_MIN"))))
            self.table.setItem(row, 3, QTableWidgetItem(self._str(row_data.get("ELECCION"))))
            self.table.setItem(row, 4, QTableWidgetItem(self._str(row_data.get("DECIL_LIST"))))
            self.table.setItem(row, 5, QTableWidgetItem(self._str(row_data.get("TASA_TEXT"))))
            self.table.setItem(row, 6, QTableWidgetItem(self._str(row_data.get("CUOTAS"))))
            self.table.setItem(row, 7, QTableWidgetItem(self._str(row_data.get("MENSAJE_TEMPLATE"))))
            
    def _str(self, val) -> str:
        return "" if val is None else str(val)
        
    def _get_cell_str(self, r, c) -> str:
        item = self.table.item(r, c)
        return item.text().strip() if item else ""
        
    def _get_cell_float(self, r, c) -> float | None:
        val = self._get_cell_str(r, c)
        try:
            return float(val)
        except ValueError:
            return None
            
    def _get_cell_int(self, r, c) -> int | None:
        val = self._get_cell_str(r, c)
        try:
            return int(val)
        except ValueError:
            return None


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

        if param.type == ParameterType.TABLE:
            widget = RulesTableWidget(value)
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
        if param.type == ParameterType.TABLE:
            return widget.get_value()
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
