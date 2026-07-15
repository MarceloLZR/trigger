"""
infrastructure.csv_exporter
--------------------------------
Exporta un DataFrame a .csv usando pandas.
"""
from __future__ import annotations
import pandas as pd

from core.interfaces import ICsvExporter


class CsvExporter(ICsvExporter):
    def export(self, df: pd.DataFrame, destination_path: str) -> str:
        # Export with UTF-8 encoding, handling commas safely
        df.to_csv(destination_path, index=False, encoding="utf-8-sig", sep=";")
        return destination_path
