"""
ui.widgets.preview_table
---------------------------
Muestra un pandas.DataFrame como tabla interactiva similar a Excel:
- Orden por columna (clic en encabezado)
- Búsqueda en vivo (filtra filas)
- Copiar celdas seleccionadas (Ctrl+C)
- Contador de registros
"""
from __future__ import annotations
import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTableView, QLabel, QAbstractItemView


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._df.index)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        value = self._df.iat[index.row(), index.column()]
        return "" if pd.isna(value) else str(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)


class PreviewTableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBar")
        self.search_box.setPlaceholderText("Buscar en resultados...")
        self.search_box.textChanged.connect(self._on_search)
        self.row_count_label = QLabel("0 registros")

        top_row.addWidget(self.search_box, 1)
        top_row.addWidget(self.row_count_label)
        layout.addLayout(top_row)

        self.model = DataFrameModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        layout.addWidget(self.table_view)

        QShortcut(QKeySequence.Copy, self.table_view, activated=self._copy_selection)

    def set_dataframe(self, df: pd.DataFrame):
        self._df = df
        self.model.set_dataframe(df)
        self.row_count_label.setText(f"{len(df):,} registros".replace(",", "."))
        self.table_view.resizeColumnsToContents()

    def _on_search(self, text: str):
        self.proxy.setFilterFixedString(text)
        visible = self.proxy.rowCount()
        self.row_count_label.setText(f"{visible:,} / {len(self._df):,} registros".replace(",", "."))

    def _copy_selection(self):
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return
        selection.sort(key=lambda idx: (idx.row(), idx.column()))
        rows: dict[int, dict[int, str]] = {}
        for idx in selection:
            rows.setdefault(idx.row(), {})[idx.column()] = self.proxy.data(idx, Qt.DisplayRole) or ""
        lines = []
        for row_idx in sorted(rows):
            cols = rows[row_idx]
            lines.append("\t".join(cols[c] for c in sorted(cols)))
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(lines))
