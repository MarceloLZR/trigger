import os
import json
import shutil
import paramiko
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class SftpService:
    """Servicio generalizado para transferencias SFTP a múltiples proveedores.
    
    Soporta obtener credenciales de diferentes tablas de cuentas (Emblue, ProvedorFeedback, etc.)
    y realizar operaciones SFTP comunes. También integra funcionalidades específicas de Emblue
    como registro en base de datos.
    """

    def __init__(self, connection_provider):
        self.connection_provider = connection_provider
        self.sftp_port = 22
        self._settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.json"
        self._settings = self._load_settings()

    def _load_settings(self) -> dict:
        """Carga configuración desde settings.json si existe."""
        if self._settings_path.exists():
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _table_name(self, tipo: str) -> str:
        """Obtiene el nombre de la tabla de cuentas basado en el tipo y la configuración."""
        if not tipo:
            raise ValueError("Tipo de cuenta no especificado")
        mapping = self._settings.get("account_tables", {})
        return mapping.get(tipo, f"DM.CUENTAS_{tipo.upper()}")

    def _row_to_dict(self, cursor, row) -> dict:
        """Convierte una fila de resultados SQL a un diccionario."""
        if row is None:
            return {}
        cols = [c[0] for c in cursor.description]
        return {cols[i]: row[i] for i in range(len(cols))}

    def obtener_credenciales(self, tipo: str, id_cuenta: int) -> dict:
        """Obtiene credenciales de una tabla de cuentas por tipo e ID.
        
        Args:
            tipo: Tipo de cuenta (ej: 'emblue', 'proveedor_feedback')
            id_cuenta: ID de la cuenta a obtener
            
        Returns:
            Diccionario con las credenciales (HOST, USUARIO, CONTRASEÑA, etc.)
        """
        table = self._table_name(tipo)
        return self.obtener_credenciales_por_tabla(table, id_cuenta)

    def obtener_credenciales_por_tabla(self, table: str, id_cuenta: int) -> dict:
        """Obtiene credenciales consultando directamente una tabla específica.
        
        Args:
            table: Nombre completo de la tabla (ej: 'DM.CUENTAS_EMBLUE')
            id_cuenta: ID de la cuenta a obtener
            
        Returns:
            Diccionario con las credenciales
        """
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()
        try:
            query = f"SELECT * FROM {table} WHERE ID_CUENTA = ?"
            try:
                cursor.execute(query, id_cuenta)
            except Exception:
                # Algunos sistemas pueden usar ID en lugar de ID_CUENTA
                cursor.execute(f"SELECT * FROM {table} WHERE ID = ?", id_cuenta)
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else {}
        finally:
            cursor.close()

    def listar_cuentas(self, tipo: str) -> list[dict]:
        """Lista todas las cuentas de un tipo.
        
        Args:
            tipo: Tipo de cuenta (ej: 'emblue', 'proveedor_feedback')
            
        Returns:
            Lista de diccionarios con las cuentas
        """
        table = self._table_name(tipo)
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, r) for r in rows]
        finally:
            cursor.close()

    def armar_carpeta(self, carpeta: Optional[str]) -> str:
        """Formatea una ruta de carpeta remota.
        
        Asegura que tenga formato Unix (/carpeta/) y maneja valores nulos.
        
        Args:
            carpeta: Ruta de carpeta (puede ser None, vacía o con separadores Windows)
            
        Returns:
            Ruta formateada (/carpeta/)
        """
        if carpeta is None:
            return "/"

        carpeta = str(carpeta).strip()

        if len(carpeta) <= 1:
            return "/"

        carpeta = carpeta.replace("\\", "/")

        if not carpeta.startswith("/"):
            carpeta = "/" + carpeta

        if not carpeta.endswith("/"):
            carpeta = carpeta + "/"

        return carpeta

    def subir_sftp(
        self,
        servidor: str,
        usuario: str,
        contrasena: str,
        archivo_local: str,
        archivo_remoto: str,
        puerto: int = 22,
        logger=None
    ):
        """Sube un archivo a un servidor SFTP.
        
        Args:
            servidor: Host del servidor SFTP
            usuario: Usuario para la conexión
            contrasena: Contraseña para la conexión
            archivo_local: Ruta local del archivo
            archivo_remoto: Ruta remota destino
            puerto: Puerto SFTP (default: 22)
            logger: Función de logging (opcional)
        """
        if not os.path.exists(archivo_local):
            raise FileNotFoundError(f"No existe el archivo local: {archivo_local}")

        if logger:
            logger(f"Conectando por SFTP a {servidor}...")

        transport = None
        sftp = None

        try:
            transport = paramiko.Transport((servidor, puerto))
            transport.connect(username=usuario, password=contrasena)
            sftp = paramiko.SFTPClient.from_transport(transport)

            if logger:
                logger(f"Subiendo {archivo_local} a {archivo_remoto}...")

            sftp.put(archivo_local, archivo_remoto)

            if logger:
                logger("Archivo subido correctamente por SFTP.")
        except Exception as e:
            if logger:
                logger(f"ERROR en carga SFTP: {str(e)}")
            raise
        finally:
            if sftp is not None:
                sftp.close()
            if transport is not None:
                transport.close()

    def registrar_y_marcar_enviado(
        self,
        nombre_campana: str,
        tabla: str,
        flg_dropeo: int,
        flg_fecha_base: int,
        id_cuenta_emblue: int,
        carpeta_emblue: str,
        id_campana: Optional[int] = None,
        logger=None
    ):
        """Registra una base en Emblue y la marca como enviada.
        
        Nota: Esta funcionalidad es específica de Emblue y requiere que
        existan los stored procedures DM.SP_REGISTRA_BASE_EMBLUE y la tabla
        DM.CABECERA_BASES_EMBLUE en la base de datos.
        
        Args:
            nombre_campana: Nombre de la campaña
            tabla: Tabla de resultados
            flg_dropeo: Flag de dropeo (0/1)
            flg_fecha_base: Flag de fecha base (0/1)
            id_cuenta_emblue: ID de la cuenta Emblue
            carpeta_emblue: Carpeta destino en Emblue
            id_campana: ID de la campaña (opcional)
            logger: Función de logging (opcional)
        """
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()

        try:
            if logger:
                logger(f"Registrando base {tabla} en Emblue...")

            # 1. Ejecutar SP de registro
            cursor.execute(
                """
                EXEC DM.SP_REGISTRA_BASE_EMBLUE
                    @NOMBRECAMPANA = ?,
                    @TABLA = ?,
                    @FLG_DROPEO = ?,
                    @FLG_FECHA_BASE = ?,
                    @ID_CUENTA_EMBLUE = ?,
                    @CARPETA_EMBLUE = ?,
                    @ID_CAMPANA = ?
                """,
                nombre_campana,
                tabla,
                flg_dropeo,
                flg_fecha_base,
                id_cuenta_emblue,
                carpeta_emblue,
                id_campana
            )

            # Drenar resultados si el SP retorna algo
            while True:
                try:
                    cursor.fetchall()
                except Exception:
                    pass
                if not cursor.nextset():
                    break

            # 2. Marcar como enviado
            cursor.execute(
                """
                UPDATE DM.CABECERA_BASES_EMBLUE
                SET FLG_ENVIADO = 1
                WHERE TABLA = ? AND NOMBRE_CAMPANA = ? AND FLG_ENVIADO = 0
                """,
                tabla,
                nombre_campana
            )

            conn.commit()

            if logger:
                logger("Base registrada y marcada como enviada correctamente en DM.CABECERA_BASES_EMBLUE.")
        except Exception as e:
            conn.rollback()
            if logger:
                logger(f"ERROR al registrar la base en Emblue: {str(e)}")
            raise
        finally:
            cursor.close()
