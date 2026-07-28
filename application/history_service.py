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

        self._save_last_state(record.process_id, record.parameters_used, record.export_options)

    def get_history(self, limit: int = 200) -> list[dict]:
        if not HISTORY_FILE.exists():
            return []
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = [json.loads(line) for line in lines[-limit:]]
        return list(reversed(records))

    def _save_last_state(self, process_id: str, params: dict[str, Any], export_options: dict[str, Any]):
        all_states = {}
        if LAST_PARAMS_FILE.exists():
            with open(LAST_PARAMS_FILE, "r", encoding="utf-8") as f:
                try:
                    all_states = json.load(f)
                except Exception:
                    pass
                    
        all_states[process_id] = {
            "parameters": params,
            "export_options": export_options
        }
        with open(LAST_PARAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_states, f, indent=2, ensure_ascii=False, default=str)

    def get_last_state(self, process_id: str) -> dict[str, Any]:
        if not LAST_PARAMS_FILE.exists():
            return {"parameters": {}, "export_options": {}}
        with open(LAST_PARAMS_FILE, "r", encoding="utf-8") as f:
            try:
                all_states = json.load(f)
            except Exception:
                return {"parameters": {}, "export_options": {}}
                
        state = all_states.get(process_id, {})
        # Backward compatibility check for old format which was just dict of params
        if state and "parameters" not in state and "export_options" not in state:
            return {"parameters": state, "export_options": {}}
            
        return {
            "parameters": state.get("parameters", {}),
            "export_options": state.get("export_options", {})
        }
