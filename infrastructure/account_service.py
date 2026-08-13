import json
from pathlib import Path
from typing import Optional


class AccountService:
    """Servicio para obtener credenciales/metadata de tablas de cuentas.

    Lee un mapeo opcional en `config/settings.json` bajo la clave
    `account_tables` y consulta la tabla correspondiente. Devuelve diccionarios
    con los nombres de columna tal como los retorna pyodbc (keys en mayúscula).
    """

    def __init__(self, connection_provider):
        self.connection_provider = connection_provider
        self._settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.json"
        self._settings = self._load_settings()

    def _load_settings(self) -> dict:
        if self._settings_path.exists():
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _table_name(self, tipo: str) -> str:
        if not tipo:
            raise ValueError("Tipo de cuenta no especificado")
        mapping = self._settings.get("account_tables", {})
        return mapping.get(tipo, f"DM.CUENTAS_{tipo.upper()}")

    def _row_to_dict(self, cursor, row) -> dict:
        if row is None:
            return {}
        cols = [c[0] for c in cursor.description]
        return {cols[i]: row[i] for i in range(len(cols))}

    def listar_cuentas(self, tipo: str) -> list[dict]:
        table = self._table_name(tipo)
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, r) for r in rows]
        finally:
            cursor.close()

    def obtener_credenciales(self, tipo: str, id_cuenta: int) -> dict:
        table = self._table_name(tipo)
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()
        try:
            # Buscamos por la columna que contenga 'ID' en su nombre, preferiblemente ID_CUENTA
            query = f"SELECT * FROM {table} WHERE ID_CUENTA = ?"
            try:
                cursor.execute(query, id_cuenta)
            except Exception:
                # Intento alternativo por si la columna tiene nombre distinto
                cursor.execute(f"SELECT * FROM {table} WHERE ID = ?", id_cuenta)

            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else {}
        finally:
            cursor.close()
