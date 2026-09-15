"""
infrastructure.db_process_repository
--------------------------------------
Repositorio de procesos respaldado por SQL Server (BD_NEGOCIO, schema APP).
Reemplaza el ProcessRepository basado en archivos.

Tablas que gestiona (las crea automáticamente si no existen):

  APP.PROCESOS
    proceso_id     NVARCHAR(200) PK   — ruta lógica, ej: "CMR/Genera Base SMS PPFF"
    nombre         NVARCHAR(300)
    modulo         NVARCHAR(100)
    descripcion    NVARCHAR(MAX)
    config_json    NVARCHAR(MAX)      — todo el JSON de process.json (sin sql_text)
    sql_text       NVARCHAR(MAX)      — contenido de query.sql
    activo         BIT               — 1 = visible; 0 = desactivado
    creado_por     NVARCHAR(100)
    creado_en      DATETIME2
    modificado_por NVARCHAR(100)
    modificado_en  DATETIME2

  APP.PROCESOS_HISTORIAL
    historial_id   INT IDENTITY PK
    proceso_id     NVARCHAR(200)
    config_json    NVARCHAR(MAX)
    sql_text       NVARCHAR(MAX)
    modificado_por NVARCHAR(100)
    modificado_en  DATETIME2
    accion         NVARCHAR(20)       — 'INSERT' | 'UPDATE'

Uso básico:
    repo = DbProcessRepository(connection_manager)
    all_procs = repo.load_all()
    proc = repo.get_by_id("CMR/Genera Base SMS PPFF")
    repo.save(proc_def, sql_text, usuario="marcelo")
    repo.set_active("CMR/Genera Base SMS PPFF", False)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from core.interfaces import IProcessRepository
from core.models import ProcessDefinition


# ---------------------------------------------------------------------------
# DDL — se ejecuta una sola vez cuando las tablas no existen
# ---------------------------------------------------------------------------
_DDL_SCHEMA = "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'APP') EXEC('CREATE SCHEMA APP');"

_DDL_PROCESOS = """
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'APP.PROCESOS') AND type = 'U'
)
CREATE TABLE APP.PROCESOS (
    proceso_id     NVARCHAR(200)  NOT NULL,
    nombre         NVARCHAR(300)  NOT NULL,
    modulo         NVARCHAR(100)  NOT NULL,
    descripcion    NVARCHAR(MAX)  NULL,
    config_json    NVARCHAR(MAX)  NOT NULL,
    sql_text       NVARCHAR(MAX)  NOT NULL,
    activo         BIT            NOT NULL DEFAULT 1,
    creado_por     NVARCHAR(100)  NULL,
    creado_en      DATETIME2      NOT NULL DEFAULT GETDATE(),
    modificado_por NVARCHAR(100)  NULL,
    modificado_en  DATETIME2      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT PK_PROCESOS PRIMARY KEY (proceso_id)
);
"""

_DDL_HISTORIAL = """
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'APP.PROCESOS_HISTORIAL') AND type = 'U'
)
CREATE TABLE APP.PROCESOS_HISTORIAL (
    historial_id   INT            NOT NULL IDENTITY(1,1),
    proceso_id     NVARCHAR(200)  NOT NULL,
    config_json    NVARCHAR(MAX)  NULL,
    sql_text       NVARCHAR(MAX)  NULL,
    modificado_por NVARCHAR(100)  NULL,
    modificado_en  DATETIME2      NOT NULL DEFAULT GETDATE(),
    accion         NVARCHAR(20)   NULL,
    CONSTRAINT PK_PROCESOS_HISTORIAL PRIMARY KEY (historial_id)
);
"""


# ---------------------------------------------------------------------------
class DbProcessRepository(IProcessRepository):
    """
    Repositorio de procesos almacenado en BD_NEGOCIO / schema APP.

    Parámetros
    ----------
    connection_manager : objeto con método get_connection() que devuelve
                         una conexión pyodbc activa (autocommit=True).
    current_user       : nombre del usuario actual para auditoría.
    """

    def __init__(self, connection_manager, current_user: str = "sistema"):
        self._cm = connection_manager
        self._current_user = current_user
        self._cache: dict[str, ProcessDefinition] = {}
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Inicialización del schema
    # ------------------------------------------------------------------
    def _ensure_schema(self):
        """Crea el schema APP y las tablas si no existen."""
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute(_DDL_SCHEMA)
            cursor.execute(_DDL_PROCESOS)
            cursor.execute(_DDL_HISTORIAL)
        except Exception as exc:
            print(f"[DbProcessRepository] Error creando schema: {exc}")

    # ------------------------------------------------------------------
    # IProcessRepository
    # ------------------------------------------------------------------
    def load_all(self) -> list[ProcessDefinition]:
        self._cache.clear()
        definitions: list[ProcessDefinition] = []
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT proceso_id, nombre, modulo, descripcion, config_json, sql_text "
                "FROM APP.PROCESOS WHERE activo = 1 ORDER BY modulo, nombre"
            )
            rows = cursor.fetchall()
            for row in rows:
                try:
                    proc = self._row_to_definition(row)
                    self._cache[proc.id] = proc
                    definitions.append(proc)
                except Exception as exc:
                    print(f"[DbProcessRepository] Error parseando proceso '{row[0]}': {exc}")
        except Exception as exc:
            print(f"[DbProcessRepository] Error en load_all: {exc}")
        return definitions

    def get_by_id(self, process_id: str) -> ProcessDefinition:
        if process_id in self._cache:
            return self._cache[process_id]
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT proceso_id, nombre, modulo, descripcion, config_json, sql_text "
                "FROM APP.PROCESOS WHERE proceso_id = ? AND activo = 1",
                (process_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"Proceso no encontrado: {process_id}")
            proc = self._row_to_definition(row)
            self._cache[proc.id] = proc
            return proc
        except KeyError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Error cargando proceso '{process_id}': {exc}") from exc

    # ------------------------------------------------------------------
    # Escritura (create / update)
    # ------------------------------------------------------------------
    def save(self,
             proceso_id: str,
             nombre: str,
             modulo: str,
             descripcion: str,
             config_json: str,
             sql_text: str,
             usuario: Optional[str] = None) -> None:
        """
        Inserta o actualiza un proceso en APP.PROCESOS y registra
        el cambio en APP.PROCESOS_HISTORIAL.

        config_json : string JSON con toda la metadata del proceso
                      (parameters, rules_engine, export flags, etc.)
        sql_text    : contenido SQL del proceso
        """
        usuario = usuario or self._current_user
        conn = self._cm.get_connection()
        cursor = conn.cursor()

        # ¿existe ya?
        cursor.execute("SELECT 1 FROM APP.PROCESOS WHERE proceso_id = ?", (proceso_id,))
        exists = cursor.fetchone() is not None

        if exists:
            accion = "UPDATE"
            # Guardar versión anterior en historial antes de sobrescribir
            cursor.execute(
                """
                INSERT INTO APP.PROCESOS_HISTORIAL
                    (proceso_id, config_json, sql_text, modificado_por, modificado_en, accion)
                SELECT proceso_id, config_json, sql_text, ?, GETDATE(), 'UPDATE'
                FROM   APP.PROCESOS
                WHERE  proceso_id = ?
                """,
                (usuario, proceso_id)
            )
            cursor.execute(
                """
                UPDATE APP.PROCESOS
                SET  nombre         = ?,
                     modulo         = ?,
                     descripcion    = ?,
                     config_json    = ?,
                     sql_text       = ?,
                     modificado_por = ?,
                     modificado_en  = GETDATE()
                WHERE proceso_id = ?
                """,
                (nombre, modulo, descripcion, config_json, sql_text, usuario, proceso_id)
            )
        else:
            accion = "INSERT"
            cursor.execute(
                """
                INSERT INTO APP.PROCESOS
                    (proceso_id, nombre, modulo, descripcion, config_json,
                     sql_text, activo, creado_por, creado_en, modificado_por, modificado_en)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, GETDATE(), ?, GETDATE())
                """,
                (proceso_id, nombre, modulo, descripcion,
                 config_json, sql_text, usuario, usuario)
            )
            # También registrar INSERT en historial
            cursor.execute(
                """
                INSERT INTO APP.PROCESOS_HISTORIAL
                    (proceso_id, config_json, sql_text, modificado_por, modificado_en, accion)
                VALUES (?, ?, ?, ?, GETDATE(), 'INSERT')
                """,
                (proceso_id, config_json, sql_text, usuario)
            )

        # Invalidar caché
        self._cache.pop(proceso_id, None)

    def delete(self, proceso_id: str, usuario: Optional[str] = None) -> None:
        """Desactiva lógicamente un proceso (activo=0). No elimina físicamente."""
        usuario = usuario or self._current_user
        conn = self._cm.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE APP.PROCESOS SET activo = 0, modificado_por = ?, modificado_en = GETDATE() "
            "WHERE proceso_id = ?",
            (usuario, proceso_id)
        )
        self._cache.pop(proceso_id, None)

    def set_active(self, proceso_id: str, activo: bool, usuario: Optional[str] = None) -> None:
        """Activa o desactiva un proceso."""
        usuario = usuario or self._current_user
        conn = self._cm.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE APP.PROCESOS SET activo = ?, modificado_por = ?, modificado_en = GETDATE() "
            "WHERE proceso_id = ?",
            (1 if activo else 0, usuario, proceso_id)
        )
        self._cache.pop(proceso_id, None)

    # ------------------------------------------------------------------
    # Historial / auditoría
    # ------------------------------------------------------------------
    def get_history(self, proceso_id: str) -> list[dict]:
        """
        Devuelve el historial de versiones de un proceso,
        ordenado del más reciente al más antiguo.
        """
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT historial_id, proceso_id, modificado_por,
                       modificado_en, accion, config_json, sql_text
                FROM   APP.PROCESOS_HISTORIAL
                WHERE  proceso_id = ?
                ORDER  BY historial_id DESC
                """,
                (proceso_id,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "historial_id": r[0],
                    "proceso_id": r[1],
                    "modificado_por": r[2],
                    "modificado_en": str(r[3]),
                    "accion": r[4],
                    "config_json": r[5],
                    "sql_text": r[6],
                }
                for r in rows
            ]
        except Exception as exc:
            print(f"[DbProcessRepository] Error en get_history: {exc}")
            return []

    def get_all_with_status(self) -> list[dict]:
        """
        Devuelve todos los procesos (activos e inactivos) con metadata de auditoría.
        Usado por la vista de administración.
        """
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT proceso_id, nombre, modulo, descripcion,
                       activo, creado_por, creado_en,
                       modificado_por, modificado_en
                FROM APP.PROCESOS
                ORDER BY modulo, nombre
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "proceso_id": r[0],
                    "nombre": r[1],
                    "modulo": r[2],
                    "descripcion": r[3],
                    "activo": bool(r[4]),
                    "creado_por": r[5],
                    "creado_en": str(r[6]) if r[6] else "",
                    "modificado_por": r[7],
                    "modificado_en": str(r[8]) if r[8] else "",
                }
                for r in rows
            ]
        except Exception as exc:
            print(f"[DbProcessRepository] Error en get_all_with_status: {exc}")
            return []

    def get_raw(self, proceso_id: str) -> Optional[dict]:
        """
        Devuelve el registro completo de un proceso (incluyendo sql_text y config_json)
        para edición. A diferencia de get_by_id, no construye ProcessDefinition.
        """
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT proceso_id, nombre, modulo, descripcion,
                       config_json, sql_text, activo,
                       creado_por, creado_en, modificado_por, modificado_en
                FROM APP.PROCESOS WHERE proceso_id = ?
                """,
                (proceso_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "proceso_id": row[0],
                "nombre": row[1],
                "modulo": row[2],
                "descripcion": row[3],
                "config_json": row[4],
                "sql_text": row[5],
                "activo": bool(row[6]),
                "creado_por": row[7],
                "creado_en": str(row[8]) if row[8] else "",
                "modificado_por": row[9],
                "modificado_en": str(row[10]) if row[10] else "",
            }
        except Exception as exc:
            print(f"[DbProcessRepository] Error en get_raw: {exc}")
            return None

    # ------------------------------------------------------------------
    # Migración desde archivos
    # ------------------------------------------------------------------
    def is_empty(self) -> bool:
        """Devuelve True si no hay ningún proceso en APP.PROCESOS."""
        try:
            conn = self._cm.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM APP.PROCESOS")
            count = cursor.fetchone()[0]
            return count == 0
        except Exception:
            return True

    def migrate_from_files(self, processes_root: Path, usuario: str = "migracion") -> tuple[int, list[str]]:
        """
        Importa todos los procesos encontrados en /processes a la BD.
        Retorna (cantidad_importada, lista_de_errores).
        Solo debe llamarse cuando is_empty() == True.
        """
        imported = 0
        errors: list[str] = []

        for json_path in sorted(processes_root.rglob("process.json")):
            try:
                folder = json_path.parent
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                sql_file = folder / data.get("sql_file", "query.sql")
                if not sql_file.exists():
                    errors.append(f"Sin SQL: {json_path}")
                    continue

                sql_text = sql_file.read_text(encoding="utf-8")
                proceso_id = str(folder.relative_to(processes_root)).replace("\\", "/")

                # Separar sql_text del JSON de configuración
                config = {k: v for k, v in data.items()}

                self.save(
                    proceso_id=proceso_id,
                    nombre=data.get("name", proceso_id),
                    modulo=data.get("module", "General"),
                    descripcion=data.get("description", ""),
                    config_json=json.dumps(config, ensure_ascii=False, indent=2),
                    sql_text=sql_text,
                    usuario=usuario,
                )
                imported += 1
            except Exception as exc:
                errors.append(f"{json_path}: {exc}")

        return imported, errors

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _row_to_definition(self, row) -> ProcessDefinition:
        """
        Convierte una fila de APP.PROCESOS en un ProcessDefinition.
        row = (proceso_id, nombre, modulo, descripcion, config_json, sql_text)
        """
        proceso_id, nombre, modulo, descripcion, config_json, sql_text = row

        data: dict = json.loads(config_json)

        # Garantizar que name/module/description vienen de las columnas dedicadas
        data.setdefault("name", nombre)
        data.setdefault("module", modulo)
        data.setdefault("description", descripcion or "")

        # sql_path requerido por el dataclass; usamos un Path ficticio inerte.
        # El executor leerá sql_content directamente (no usará sql_path).
        dummy_sql_path = Path("__db_sql__")

        proc = ProcessDefinition.from_dict(
            data=data,
            process_id=proceso_id,
            sql_path=dummy_sql_path,
            icon_path=None,
            folder=Path("."),
        )
        # Inyectar el contenido SQL directamente para que el executor lo use
        proc.sql_content = sql_text
        return proc
