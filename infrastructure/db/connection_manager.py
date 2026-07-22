"""
infrastructure.db.connection_manager
-------------------------------------
Singleton responsable de crear y reutilizar UNA sola conexión pyodbc
a SQL Server para toda la aplicación, tal como se pidió.

Uso:
    conn = ConnectionManager.instance().get_connection()

La configuración (server, database, driver) se lee de config/settings.json
y puede recargarse en caliente desde la vista de Configuración.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

import pyodbc

from core.interfaces import IConnectionProvider

SETTINGS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "settings.json"
)


class ConnectionManager(IConnectionProvider):
    _instance: Optional["ConnectionManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        if ConnectionManager._instance is not None:
            raise RuntimeError(
                "Usar ConnectionManager.instance(), no el constructor directo."
            )

        self._conn: Optional[pyodbc.Connection] = None
        self._settings = self._load_settings()

    @classmethod
    def instance(cls) -> "ConnectionManager":
        with cls._lock:
            if cls._instance is None:
                obj = cls.__new__(cls)
                obj._conn = None
                obj._settings = obj._load_settings()
                cls._instance = obj

            return cls._instance

    # -- settings -----------------------------------------------------
    def _load_settings(self) -> dict:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)

        return {
            "server": r"B200603SV01X\INS_NEGOCIO",
            "database": "BD_NEGOCIO",
            "driver": "ODBC Driver 17 for SQL Server",
            "trusted_connection": True,
            "username": "",
            "password": "",
            "timeout": 30,
        }

    def reload_settings(self):
        self._settings = self._load_settings()
        self.close()

    def save_settings(self, settings: dict):
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        self._settings = settings
        self.close()

    def get_settings(self) -> dict:
        return dict(self._settings)

    # -- connection string ---------------------------------------------
    def _build_connection_string(self) -> str:
        s = self._settings

        parts = [
            f"DRIVER={{{s['driver']}}}",
            f"SERVER={s['server']}",
            f"DATABASE={s['database']}",
        ]

        if s.get("trusted_connection", True):
            parts.append("Trusted_Connection=yes")
        else:
            parts.append(f"UID={s.get('username', '')}")
            parts.append(f"PWD={s.get('password', '')}")

        # MARS (Multiple Active Result Sets) evita el error
        # "Connection is busy with results for another command" cuando
        # un script ejecuta varios SELECT INTO / UPDATE en secuencia
        # sobre el mismo cursor.
        parts.append("MARS_Connection=yes")

        return ";".join(parts) + ";"

    # -- public API -----------------------------------------------------
    def get_connection(self) -> pyodbc.Connection:
        """
        Devuelve la conexión activa, creándola si aún no existe
        o si se perdió (autocommit, reconexión perezosa).
        """
        if self._conn is None or not self._is_alive():
            conn_str = self._build_connection_string()

            self._conn = pyodbc.connect(
                conn_str,
                timeout=self._settings.get("timeout", 30),
                autocommit=True,
            )

        return self._conn

    def _is_alive(self) -> bool:
        try:
            self._conn.cursor().execute("SELECT 1")
            return True
        except Exception:
            return False

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = pyodbc.connect(
                self._build_connection_string(),
                timeout=self._settings.get("timeout", 10),
            )

            conn.close()
            return True, "Conexión exitosa."

        except Exception as exc:
            return False, str(exc)

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass

            self._conn = None