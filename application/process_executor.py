"""
application.process_executor
------------------------------
Caso de uso: "Ejecutar un proceso SQL con parámetros dados".

Corre en un QThread propio (ProcessWorker) para no congelar la UI.
Emite señales que la UI escucha (patrón Observer nativo de Qt):

log(str) -> línea para la consola de ejecución
progress(int) -> 0-100 (aproximado, por etapas)
finished(DataFrame, ExecutionRecord)
failed(str, ExecutionRecord)

Etapas de progreso:
10 leer SQL
25 renderizar variables
40 ejecutar en SQL Server
80 convertir a DataFrame
100 listo
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from PySide6.QtCore import QThread, Signal

from core.models import ProcessDefinition, ExecutionRecord, ExecutionStatus
from core.interfaces import IConnectionProvider, ISqlTemplateEngine, IExcelExporter, ICsvExporter, IEmailSender
from infrastructure.sql_template_engine import MissingParameterError
import os

class ProcessWorker(QThread):
    log = Signal(str)
    progress = Signal(int)
    finished_ok = Signal(object, object)  # (list[{label, df}], ExecutionRecord)
    failed = Signal(str, object)  # (mensaje_error, ExecutionRecord)

    def __init__(
        self,
        process: ProcessDefinition,
        params: dict[str, Any],
        connection_provider: IConnectionProvider,
        template_engine: ISqlTemplateEngine,
        excel_exporter: Optional[IExcelExporter] = None,
        csv_exporter: Optional[ICsvExporter] = None,
        email_sender: Optional[IEmailSender] = None,
        export_options: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.process = process
        self.params = params
        self.connection_provider = connection_provider
        self.template_engine = template_engine
        self.excel_exporter = excel_exporter
        self.csv_exporter = csv_exporter
        self.email_sender = email_sender
        self.export_options = export_options or {}
        self._cancelled = False

    def _render_string(self, text: str, params: dict) -> str:
        if not text:
            return ""
        res = text
        for k, v in params.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res

    def cancel(self):
        self._cancelled = True
        self.requestInterruption()

    def run(self):
        record = ExecutionRecord(
            process_id=self.process.id,
            process_name=self.process.name,
            started_at=datetime.now(),
            parameters_used=dict(self.params),
        )

        try:
            self.log.emit(f"Iniciando proceso: {self.process.name}")
            self.progress.emit(10)

            with open(self.process.sql_path, "r", encoding="utf-8") as f:
                raw_sql = f.read()

            if self._cancelled:
                return self._emit_cancelled(record)

            self.progress.emit(25)
            self.log.emit("Reemplazando variables de plantilla...")

            rendered_sql = self.template_engine.render(
                raw_sql,
                self.params,
            )

            if self._cancelled:
                return self._emit_cancelled(record)

            self.progress.emit(40)
            self.log.emit("Conectando y ejecutando script en SQL Server...")

            conn = self.connection_provider.get_connection()
            cursor = conn.cursor()

            # SET NOCOUNT ON evita que cada SELECT INTO/UPDATE devuelva un
            # mensaje "(N rows affected)" que pyodbc trata como un result
            # set pendiente. Sin esto, el siguiente cursor.execute() falla
            # con "Connection is busy with results for another command".
            cursor.execute("SET NOCOUNT ON;")
            self._drain_results(cursor)

            # El script puede tener múltiples statements
            # (GO no es válido en pyodbc).
            for batch in self._split_batches(rendered_sql):

                if self._cancelled:
                    return self._emit_cancelled(record)

                if batch.strip():
                    cursor.execute(batch)

                    # Drena cualquier result set que haya quedado pendiente
                    # (rowcounts, SELECTs intermedios, etc.) antes de pasar
                    # al siguiente batch.
                    self._drain_results(cursor)

            self.progress.emit(80)

            results: list[dict] = []
            total = len(self.process.final_tables)
            for i, ft in enumerate(self.process.final_tables):
                self.log.emit(f"Leyendo tabla ({i + 1}/{total}): {ft.table}")
                df = pd.read_sql(
                    f"SELECT * FROM {ft.table}",
                    conn,
                )
                results.append({"label": ft.label, "df": df, "export_name": ft.export_name})

            total_rows = sum(r["df"].shape[0] for r in results)
            record.row_count = total_rows
            record.finished_at = datetime.now()
            record.duration_seconds = (
                record.finished_at - record.started_at
            ).total_seconds()

            record.status = ExecutionStatus.SUCCESS

            self.progress.emit(90)
            
            # --- POST PROCESSING: EXPORTS & EMAIL ---
            has_data = any(not r["df"].empty for r in results)
            exported_files = []
            
            if has_data:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                rendered_process_name = self._render_string(self.process.name, record.parameters_used)
                safe_name = rendered_process_name.replace(' ', '_')
                
                excel_folder = self.export_options.get('excel_path') or getattr(self.process, 'auto_export_folder', None)
                csv_folder = self.export_options.get('csv_path') or getattr(self.process, 'auto_export_csv_folder', None)
                attach_excel = self.export_options.get('attach_excel', True)
                attach_csv = self.export_options.get('attach_csv', True)
                
                # Excel
                if excel_folder and self.excel_exporter:
                    self.log.emit("Guardando archivos Excel...")
                    for result in results:
                        df = result["df"]
                        if df.empty:
                            continue
                        export_name_template = result.get("export_name")
                        if export_name_template:
                            filename = self._render_string(export_name_template, record.parameters_used) + ".xlsx"
                        else:
                            safe_label = self._render_string(result["label"], record.parameters_used).replace(' ', '_')
                            filename = f"{safe_name}_{safe_label}_{timestamp}.xlsx"
                        export_path = os.path.join(excel_folder, filename)
                        try:
                            self.excel_exporter.export(df, export_path, sheet_name=result["label"][:31])
                            self.log.emit(f"✅ Excel guardado: {export_path}")
                            if attach_excel:
                                exported_files.append(export_path)
                        except Exception as exc:
                            self.log.emit(f"❌ Error al guardar Excel ({result['label']}): {str(exc)}")
                
                # CSV
                if csv_folder and self.csv_exporter:
                    self.log.emit("Guardando archivos CSV...")
                    for result in results:
                        df = result["df"]
                        if df.empty:
                            continue
                        export_name_template = result.get("export_name")
                        if export_name_template:
                            filename = self._render_string(export_name_template, record.parameters_used) + ".csv"
                        else:
                            safe_label = self._render_string(result["label"], record.parameters_used).replace(' ', '_')
                            filename = f"{safe_name}_{safe_label}_{timestamp}.csv"
                        export_path = os.path.join(csv_folder, filename)
                        try:
                            self.csv_exporter.export(df, export_path)
                            self.log.emit(f"✅ CSV guardado: {export_path}")
                            if attach_csv:
                                exported_files.append(export_path)
                        except Exception as exc:
                            self.log.emit(f"❌ Error al guardar CSV ({result['label']}): {str(exc)}")
                            
            # Email
            to_addresses = self.export_options.get('email_to')
            if getattr(self.process, 'send_email', False) and to_addresses and self.email_sender:
                self.log.emit(f"Enviando correo a: {to_addresses}...")
                
                subject = getattr(self.process, 'email_subject', f"Resultados: {self.process.name}")
                if not subject:
                    subject = f"Resultados: {self.process.name}"

                total_rows = sum(r["df"].shape[0] for r in results)
                html_body = f"<p>Adjunto los resultados del proceso <b>{self.process.name}</b>.</p><p>Filas generadas: {total_rows}</p>"

                if getattr(self.process, 'email_template', None):
                    template_path = self.process.folder / self.process.email_template
                    if template_path.exists():
                        try:
                            with open(template_path, 'r', encoding='utf-8') as f:
                                html_body = f.read()
                            html_body = html_body.replace("{proceso_nombre}", self.process.name)
                            html_body = html_body.replace("{fecha}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            html_body = html_body.replace("{filas}", str(total_rows))
                            for param_name, param_value in record.parameters_used.items():
                                html_body = html_body.replace(f"{{{param_name}}}", str(param_value))
                        except Exception as exc:
                            self.log.emit(f"❌ Error leyendo plantilla de correo: {str(exc)}")

                try:
                    self.email_sender.send_email(to_addresses, subject, html_body, exported_files)
                    self.log.emit("✅ Correo enviado exitosamente.")
                except Exception as exc:
                    self.log.emit(f"❌ Error al enviar correo: {str(exc)}")

            self.progress.emit(100)

            self.log.emit(
                f"Proceso finalizado: {total_rows} registros totales en {total} tabla(s)."
            )

            self.finished_ok.emit(results, record)

        except MissingParameterError as exc:
            record.status = ExecutionStatus.ERROR
            record.error_message = str(exc)
            record.finished_at = datetime.now()

            self.log.emit(f"ERROR de parámetros: {exc}")
            self.failed.emit(str(exc), record)

        except Exception as exc:
            record.status = ExecutionStatus.ERROR
            record.error_message = str(exc)
            record.finished_at = datetime.now()

            self.log.emit(f"ERROR: {exc}")
            self.failed.emit(str(exc), record)

    def _emit_cancelled(self, record: ExecutionRecord):
        record.status = ExecutionStatus.CANCELLED
        record.finished_at = datetime.now()

        self.log.emit("Proceso cancelado por el usuario.")
        self.failed.emit("Cancelado por el usuario.", record)

    @staticmethod
    def _drain_results(cursor) -> None:
        """
        Consume todos los result sets pendientes del cursor.

        pyodbc no libera el cursor para el siguiente execute()
        hasta que se recorren (o se descartan) todos los conjuntos
        de resultados que dejó el statement anterior.
        """
        while True:
            try:
                cursor.fetchall()
            except Exception:
                pass

            if not cursor.nextset():
                break

    @staticmethod
    def _split_batches(sql_text: str) -> list[str]:
        lines = sql_text.splitlines()

        batches = []
        current = []

        for line in lines:
            if line.strip().upper() == "GO":
                batches.append("\n".join(current))
                current = []
            else:
                current.append(line)

        if current:
            batches.append("\n".join(current))

        return batches