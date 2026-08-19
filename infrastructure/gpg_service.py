"""
infrastructure.gpg_service
--------------------------
Servicio de encriptación GPG usando GnuPG / Kleopatra.

Envuelve las llamadas a gpg.exe por subprocess para:
- Listar las llaves públicas disponibles en el keyring local.
- Cifrar un archivo con una llave pública seleccionada.

Ruta del ejecutable: fija en GPG_EXE (instalación estándar de Kleopatra/GnuPG).
"""

import os
import subprocess
from typing import Optional

# Ruta fija del ejecutable GPG (Kleopatra / GnuPG for Windows)
GPG_EXE = r"C:\Program Files (x86)\GnuPG\bin\gpg.exe"


class GpgNotFoundError(Exception):
    """Se lanza cuando gpg.exe no existe en la ruta esperada."""


class GpgEncryptionError(Exception):
    """Se lanza cuando el proceso de cifrado devuelve un error."""


class GpgService:
    """Servicio de encriptación GPG usando el keyring local de Kleopatra."""

    def __init__(self, gpg_exe: str = GPG_EXE):
        self.gpg_exe = gpg_exe

    def is_available(self) -> bool:
        """Devuelve True si gpg.exe existe y es ejecutable."""
        return os.path.isfile(self.gpg_exe)

    def _run(self, args: list) -> subprocess.CompletedProcess:
        """Ejecuta gpg.exe con los argumentos indicados y devuelve el resultado."""
        if not self.is_available():
            raise GpgNotFoundError(
                f"No se encontró gpg.exe en:\n{self.gpg_exe}\n"
                "Asegúrese de tener Kleopatra / GnuPG instalado."
            )

        return subprocess.run(
            [self.gpg_exe] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

    def obtener_claves(self) -> list:
        """
        Lista las llaves públicas disponibles en el keyring local.

        Devuelve una lista de dicts con:
            - keyid      : ID corto de la llave (16 hex)
            - fingerprint: huella completa
            - uid        : nombre / e-mail del titular
            - label      : etiqueta legible para mostrar en UI
        """
        resultado = self._run([
            "--list-keys",
            "--with-colons",
            "--fingerprint",
        ])

        if resultado.returncode != 0:
            raise GpgEncryptionError(
                f"Error listando llaves GPG:\n{resultado.stderr}"
            )

        claves = []
        keyid = None
        fingerprint = None

        for linea in resultado.stdout.splitlines():
            partes = linea.split(":")

            if partes[0] == "pub":
                keyid = partes[4] if len(partes) > 4 else None
                fingerprint = None

            elif partes[0] == "fpr":
                fingerprint = partes[9] if len(partes) > 9 else None

            elif partes[0] == "uid":
                uid = partes[9] if len(partes) > 9 else "(sin nombre)"
                if keyid:
                    short_id = keyid[-8:] if len(keyid) >= 8 else keyid
                    claves.append({
                        "keyid": keyid,
                        "fingerprint": fingerprint or keyid,
                        "uid": uid,
                        # Etiqueta legible para mostrar en UI
                        "label": f"{uid}  [{short_id}]",
                    })

        return claves

    def cifrar_archivo(
        self,
        ruta_archivo: str,
        keyid: str,
        carpeta_salida: Optional[str] = None,
        eliminar_original: bool = True,
        logger=None,
    ) -> str:
        """
        Cifra un archivo con la llave pública indicada.

        Args:
            ruta_archivo    : Ruta absoluta del archivo a cifrar.
            keyid           : Key ID o fingerprint del destinatario.
            carpeta_salida  : Carpeta donde se guarda el .gpg.
                              Si es None, se usa la misma carpeta del archivo.
            eliminar_original: Si True, elimina el archivo original tras cifrar.
            logger          : Función de logging (p.ej. self.log.emit).

        Returns:
            Ruta absoluta del archivo .gpg generado.

        Raises:
            FileNotFoundError  : Si el archivo de entrada no existe.
            GpgEncryptionError : Si gpg devuelve un error.
        """
        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")

        # Determinar carpeta y nombre de salida
        if carpeta_salida:
            os.makedirs(carpeta_salida, exist_ok=True)
            nombre_base = os.path.basename(ruta_archivo) + ".gpg"
            archivo_salida = os.path.join(carpeta_salida, nombre_base)
        else:
            archivo_salida = ruta_archivo + ".gpg"

        short_id = keyid[-8:] if len(keyid) >= 8 else keyid
        if logger:
            logger(f"🔐 Cifrando con GPG (llave: {short_id})...")

        resultado = self._run([
            "--verbose",
            "--batch",
            "--yes",
            "--trust-model", "always",
            "--recipient", keyid,
            "--output", archivo_salida,
            "--encrypt", ruta_archivo,
        ])

        if resultado.returncode != 0:
            raise GpgEncryptionError(
                f"Error al cifrar '{os.path.basename(ruta_archivo)}':\n{resultado.stderr}"
            )

        if logger:
            logger(f"✅ Archivo cifrado: {archivo_salida}")

        if eliminar_original:
            try:
                os.remove(ruta_archivo)
                if logger:
                    logger(f"🗑️ Original eliminado: {os.path.basename(ruta_archivo)}")
            except Exception as exc:
                if logger:
                    logger(f"⚠️ No se pudo eliminar el original: {exc}")

        return archivo_salida
