"""
application.history_service
------------------------------
Guarda cada ejecución (ExecutionRecord) en history/history.jsonl
(un JSON por línea, append-only -> escritura barata y robusta).
También guarda los "últimos parámetros utilizados" por proceso,
para precargar el formulario la próxima vez (pedido explícito del usuario).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from core.models import ExecutionRecord

HISTORY_DIR = Path(__file__).resolve().parents[1] / "history"
HISTORY_FILE = HISTORY_DIR / "history.jsonl"
LAST_PARAMS_FILE = HISTORY_DIR / "last_parameters.json"


class HistoryService:
    def __init__(self):
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    def record_execution(self, record: ExecutionRecord):
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        self._save_last_params(record.process_id, record.parameters_used)

    def get_history(self, limit: int = 200) -> list[dict]:
        if not HISTORY_FILE.exists():
            return []
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = [json.loads(line) for line in lines[-limit:]]
        return list(reversed(records))

    def _save_last_params(self, process_id: str, params: dict[str, Any]):
        all_params = {}
        if LAST_PARAMS_FILE.exists():
            with open(LAST_PARAMS_FILE, "r", encoding="utf-8") as f:
                all_params = json.load(f)
        all_params[process_id] = params
        with open(LAST_PARAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_params, f, indent=2, ensure_ascii=False, default=str)

    def get_last_params(self, process_id: str) -> dict[str, Any]:
        if not LAST_PARAMS_FILE.exists():
            return {}
        with open(LAST_PARAMS_FILE, "r", encoding="utf-8") as f:
            all_params = json.load(f)
        return all_params.get(process_id, {})
