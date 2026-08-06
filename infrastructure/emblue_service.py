import os
import shutil
import paramiko
from datetime import datetime

class EmblueService:
    def __init__(self, connection_provider):
        self.connection_provider = connection_provider
        self.sftp_port = 22

    def armar_carpeta_emblue(self, carpeta_emblue: str) -> str:
        if carpeta_emblue is None:
            return "/"

        carpeta_emblue = str(carpeta_emblue).strip()

        if len(carpeta_emblue) <= 1:
            return "/"

        carpeta_emblue = carpeta_emblue.replace("\\", "/")

        if not carpeta_emblue.startswith("/"):
            carpeta_emblue = "/" + carpeta_emblue

        if not carpeta_emblue.endswith("/"):
            carpeta_emblue = carpeta_emblue + "/"

        return carpeta_emblue

    def obtener_credenciales(self, id_cuenta: int):
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT HOST, USUARIO, CONTRASEÑA
                FROM DM.CUENTAS_EMBLUE
                WHERE ID_CUENTA = ?
                """,
                id_cuenta
            )
            row = cursor.fetchone()
            if row:
                return row[0], row[1], row[2]
            return None, None, None
        finally:
            cursor.close()

    def subir_sftp(self, servidor, usuario, contrasena, archivo_local, archivo_remoto, logger=None):
        if not os.path.exists(archivo_local):
            raise FileNotFoundError(f"No existe el archivo local: {archivo_local}")

        if logger:
            logger(f"Conectando por SFTP a {servidor}...")

        transport = None
        sftp = None

        try:
            transport = paramiko.Transport((servidor, self.sftp_port))
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

    def registrar_y_marcar_enviado(self, nombre_campana, tabla, flg_dropeo, flg_fecha_base, id_cuenta_emblue, carpeta_emblue, id_campana=None, logger=None):
        conn = self.connection_provider.get_connection()
        cursor = conn.cursor()

        try:
            if logger:
                logger(f"Registrando base {tabla} en Emblue...")

            # 1. Ejecutar SP
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
            
            # Drain results if the SP returns anything
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
