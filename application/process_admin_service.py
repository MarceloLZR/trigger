"""
application.process_admin_service
------------------------------------
Servicio de administración de procesos: crear, editar, activar/desactivar
y consultar historial. Valida la estructura del JSON antes de persistir.

Uso:
    svc = ProcessAdminService(db_repo)
    ok, msg = svc.save_process(proceso_id, nombre, modulo, desc, config_json, sql_text, usuario)
    registros = svc.list_all()
    historia  = svc.get_history("CMR/Genera Base SMS PPFF")
"""
from __future__ import annotations

import json
import re
from typing import Optional


# Campos obligatorios que debe tener el JSON de configuración de un proceso
_REQUIRED_CONFIG_FIELDS = {"parameters", "final_tables"}

# Caracteres inválidos para proceso_id (solo letras, números, /, _ y espacio)
_VALID_ID_RE = re.compile(r"^[\w\s/\-\.]+$", re.UNICODE)


class ProcessAdminService:
    """
    Servicio de aplicación para administrar procesos almacenados en BD.

    Parámetros
    ----------
    db_repo : DbProcessRepository
        Repositorio de procesos en SQL Server.
    """

    def __init__(self, db_repo):
        self._repo = db_repo

    # ------------------------------------------------------------------
    # Guardar (crear o actualizar)
    # ------------------------------------------------------------------
    def save_process(
        self,
        proceso_id: str,
        nombre: str,
        modulo: str,
        descripcion: str,
        config_json: str,
        sql_text: str,
        usuario: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Valida y guarda un proceso en la BD.

        Retorna (True, "") si todo fue bien, o (False, "mensaje de error") si no.
        """
        # --- Validaciones ---
        proceso_id = proceso_id.strip()
        nombre = nombre.strip()
        modulo = modulo.strip()

        if not proceso_id:
            return False, "El ID del proceso no puede estar vacío."
        if not _VALID_ID_RE.match(proceso_id):
            return False, "El ID del proceso solo puede contener letras, números, '/', '-', '_' y espacios."
        if not nombre:
            return False, "El nombre del proceso no puede estar vacío."
        if not modulo:
            return False, "El módulo no puede estar vacío."
        if not sql_text.strip():
            return False, "El SQL del proceso no puede estar vacío."

        # Validar que config_json sea JSON válido
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as exc:
            return False, f"El JSON de configuración no es válido: {exc}"

        # Verificar campos obligatorios
        missing = _REQUIRED_CONFIG_FIELDS - set(config.keys())
        if missing:
            return False, (
                f"El JSON de configuración debe incluir: {', '.join(sorted(missing))}.\n"
                "Consulta un proceso existente como referencia."
            )

        # Garantizar que name/module en el JSON coincidan con los campos del formulario
        config["name"] = nombre
        config["module"] = modulo
        config["description"] = descripcion
        config_json_final = json.dumps(config, ensure_ascii=False, indent=2)

        try:
            self._repo.save(
                proceso_id=proceso_id,
                nombre=nombre,
                modulo=modulo,
                descripcion=descripcion,
                config_json=config_json_final,
                sql_text=sql_text,
                usuario=usuario,
            )
            return True, ""
        except Exception as exc:
            return False, f"Error al guardar en la base de datos: {exc}"

    # ------------------------------------------------------------------
    # Activar / desactivar
    # ------------------------------------------------------------------
    def set_active(self, proceso_id: str, activo: bool, usuario: Optional[str] = None) -> tuple[bool, str]:
        try:
            self._repo.set_active(proceso_id, activo, usuario)
            estado = "activado" if activo else "desactivado"
            return True, f"Proceso {estado} correctamente."
        except Exception as exc:
            return False, f"Error al cambiar estado: {exc}"

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def list_all(self) -> list[dict]:
        """Lista todos los procesos (activos e inactivos) con metadata de auditoría."""
        return self._repo.get_all_with_status()

    def get_raw(self, proceso_id: str) -> Optional[dict]:
        """Devuelve el registro completo de un proceso para edición."""
        return self._repo.get_raw(proceso_id)

    def get_history(self, proceso_id: str) -> list[dict]:
        """Devuelve el historial de versiones de un proceso."""
        return self._repo.get_history(proceso_id)

    # ------------------------------------------------------------------
    # Migración desde archivos
    # ------------------------------------------------------------------
    def migrate_from_files(self, processes_root, usuario: str = "migracion") -> tuple[int, list[str]]:
        """
        Importa procesos desde /processes a la BD si la BD está vacía.
        Retorna (n_importados, lista_de_errores).
        """
        if not self._repo.is_empty():
            return 0, []
        return self._repo.migrate_from_files(processes_root, usuario=usuario)
