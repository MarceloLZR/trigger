"""
infrastructure.process_repository
-----------------------------------
Escanea recursivamente la carpeta /processes buscando subcarpetas que
contengan process.json + query.sql, y construye objetos ProcessDefinition.

Este es el corazón de la extensibilidad pedida: agregar un proceso nuevo
es únicamente crear una carpeta con estos dos archivos (+ icon.png opcional).
No requiere tocar ninguna línea de Python.
"""
from __future__ import annotations
import json
from pathlib import Path

from core.interfaces import IProcessRepository
from core.models import ProcessDefinition


class ProcessDefinitionError(Exception):
    pass


class ProcessRepository(IProcessRepository):
    def __init__(self, processes_root: Path):
        self.processes_root = Path(processes_root)
        self._cache: dict[str, ProcessDefinition] = {}

    def load_all(self) -> list[ProcessDefinition]:
        self._cache.clear()
        if not self.processes_root.exists():
            return []

        definitions: list[ProcessDefinition] = []
        for json_path in sorted(self.processes_root.rglob("process.json")):
            try:
                definition = self._load_one(json_path)
                self._cache[definition.id] = definition
                definitions.append(definition)
            except Exception as exc:
                # Un proceso mal configurado no debe tumbar toda la app.
                print(f"[ProcessRepository] Error cargando {json_path}: {exc}")
        return definitions

    def get_by_id(self, process_id: str) -> ProcessDefinition:
        if not self._cache:
            self.load_all()
        if process_id not in self._cache:
            raise KeyError(f"Proceso no encontrado: {process_id}")
        return self._cache[process_id]

    def _load_one(self, json_path: Path) -> ProcessDefinition:
        folder = json_path.parent
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sql_path = folder / data.get("sql_file", "query.sql")
        if not sql_path.exists():
            raise ProcessDefinitionError(f"No se encontró {sql_path.name} junto a {json_path}")

        icon_path = folder / "icon.png"
        icon_path = icon_path if icon_path.exists() else None

        process_id = str(folder.relative_to(self.processes_root)).replace("\\", "/")

        return ProcessDefinition.from_dict(
            data=data,
            process_id=process_id,
            sql_path=sql_path,
            icon_path=icon_path,
            folder=folder,
        )
