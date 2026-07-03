# SQL Automation Suite

Aplicación de escritorio (Python + PySide6) para automatizar la ejecución de
scripts SQL Server que hoy se ejecutan manualmente en SSMS: cambio de fechas,
mes, proveedor, exportación a Excel, etc.

## 1. Arquitectura

Clean Architecture por capas, con las dependencias apuntando siempre hacia adentro:

```
┌───────────────────────────────────────────────────────────┐
│  ui/                (PySide6: ventanas, vistas, widgets)    │
│      depende de ↓                                            │
├───────────────────────────────────────────────────────────┤
│  application/        (casos de uso: ejecutar proceso,        │
│                        ejecutar workflow, historial)         │
│      depende de ↓                                            │
├───────────────────────────────────────────────────────────┤
│  core/               (modelos + interfaces, sin dependencias │
│                        externas: es el dominio puro)         │
│      implementado por ↑                                       │
├───────────────────────────────────────────────────────────┤
│  infrastructure/     (pyodbc, filesystem, pandas, openpyxl)  │
└───────────────────────────────────────────────────────────┘
```

`core/` no importa PySide6 ni pyodbc: solo define **qué** es un proceso, un
parámetro, un workflow, y **qué contratos** debe cumplir quien los ejecute
(`IConnectionProvider`, `IProcessRepository`, etc.). `infrastructure/`
implementa esos contratos. `application/` orquesta el caso de uso ("ejecutar
este proceso con estos parámetros") sin saber nada de Qt. `ui/` solo
consume señales y muestra resultados.

Esto permite, por ejemplo, escribir tests de `SqlTemplateEngine` o de
`ProcessRepository` sin levantar ninguna ventana, o cambiar `pyodbc` por otro
driver sin tocar una sola vista.

## 2. Patrones de diseño usados

| Patrón | Clase | Propósito |
|---|---|---|
| Singleton | `ConnectionManager` | una única conexión SQL Server reutilizada por todos los procesos |
| Repository | `ProcessRepository`, `WorkflowRepository` | abstraen la lectura de carpetas/JSON |
| Factory + Strategy | `ParameterWidgetFactory` | crea el widget correcto según `type` del parámetro |
| Template/Engine | `SqlTemplateEngine` | reemplaza `{{VAR}}` en el SQL |
| Command (implícito) | pasos de `Workflow` / `WorkflowRunner` | cada paso es una unidad ejecutable, ordenable y cancelable |
| Observer (Qt Signals) | `ProcessWorker`, `WorkflowRunner` | la UI se entera de progreso/log/resultado sin acoplarse a la ejecución |
| Composition Root | `MainWindow.__init__` | único lugar donde se instancian todas las dependencias concretas |

## 3. Estructura de carpetas

```
sql_automation_suite/
├── main.py                          # punto de entrada
├── config/
│   └── settings.json                 # conexión SQL Server (editable desde la app)
├── core/
│   ├── models.py                     # Parameter, ProcessDefinition, Workflow, ExecutionRecord
│   └── interfaces.py                 # contratos (puertos)
├── infrastructure/
│   ├── db/
│   │   └── connection_manager.py     # Singleton de conexión pyodbc
│   ├── process_repository.py         # escanea /processes
│   ├── workflow_repository.py        # escanea /workflows
│   ├── sql_template_engine.py        # reemplazo de {{VAR}}
│   └── excel_exporter.py             # pandas + openpyxl con formato
├── application/
│   ├── process_executor.py           # ProcessWorker (QThread) — ejecuta 1 proceso
│   ├── workflow_executor.py          # WorkflowRunner — ejecuta N procesos en secuencia
│   └── history_service.py            # historial + "últimos parámetros usados"
├── ui/
│   ├── main_window.py                # composition root de la UI, sidebar, navegación
│   ├── theme.py                      # QSS claro/oscuro
│   ├── widgets/
│   │   ├── module_card.py            # tarjeta reutilizable
│   │   ├── parameter_form.py         # formulario dinámico + Factory de widgets
│   │   ├── preview_table.py          # tabla tipo Excel (orden/buscar/copiar)
│   │   └── console_widget.py         # consola de logs
│   └── views/
│       ├── dashboard_view.py         # tarjetas de módulos
│       ├── module_processes_view.py  # tarjetas de procesos de un módulo
│       ├── process_run_view.py       # formulario + ejecutar + preview + exportar
│       ├── quick_execution_view.py   # checklist + ejecutar seleccionados
│       ├── workflows_view.py         # ejecutar secuencias predefinidas
│       ├── settings_view.py          # configuración de conexión
│       └── history_view.py           # historial de ejecuciones
├── processes/                        # <-- AQUÍ SE AGREGAN PROCESOS NUEVOS
│   ├── CMR/ResultadosQubo/{process.json, query.sql}
│   ├── GobiernoDatos/CalidadDatos/{process.json, query.sql}
│   └── Modelos/Riesgo/{process.json, query.sql}
├── workflows/
│   └── cierre_mensual.json
├── history/                          # se genera en tiempo de ejecución
│   ├── history.jsonl
│   └── last_parameters.json
└── requirements.txt
```

## 4. Flujo completo de ejecución (un proceso)

```
Usuario navega:  Dashboard → Módulo (CMR) → Proceso (Resultados QUBO)
                                    │
                                    ▼
        MainWindow._open_process(id) --------------------------┐
                                    │                            │
                                    ▼                            │
        ProcessRepository.get_by_id(id) → ProcessDefinition      │
                                    │                            │
                                    ▼                            │
        ProcessRunView.set_process(process)                      │
            └─ ParameterFormWidget construye el formulario        │
               (precargado con HistoryService.get_last_params)    │
                                    │                              │
                     Usuario ajusta parámetros y hace clic          │
                                    ▼                                │
                        [ Ejecutar ]                                  │
                                    │                                  │
                                    ▼                                    │
        ProcessWorker (QThread) ------------------------------------------
            1. lee query.sql
            2. SqlTemplateEngine.render(sql, params)   -> reemplaza {{VAR}}
            3. ConnectionManager.get_connection()      -> reutiliza conexión
            4. cursor.execute(sql) por cada batch (separado por GO)
            5. pandas.read_sql("SELECT * FROM " + final_table, conn)
            6. emit progress / log en cada etapa
                                    │
                     ┌──────────────┴───────────────┐
                     ▼                                ▼
            finished_ok(df, record)             failed(msg, record)
                     │                                │
                     ▼                                ▼
        PreviewTableWidget.set_dataframe(df)   QMessageBox.critical(msg)
        HistoryService.record_execution(record)  (también se registra)
                     │
                     ▼
        Usuario hace clic en "Exportar a Excel"
                     │
                     ▼
        ExcelExporter.export(df, ruta_elegida)
```

## 5. Flujo de un Workflow / Ejecución rápida

```
WorkflowRunner recibe: [(ProcessA, paramsA), (ProcessB, paramsB), ...]

  paso = -1
  loop:
      paso += 1
      si cancelado o paso == total: emitir all_finished(records) y salir
      crear ProcessWorker(steps[paso]) y ejecutar
      al terminar (ok o error): guardar record, continuar con el siguiente paso
```

Cada paso reutiliza exactamente el mismo `ProcessWorker` que la ejecución
individual — no hay lógica duplicada entre "Ejecución rápida", "Workflows" y
la ejecución de un proceso suelto.

## 6. Modelo de datos

```python
Parameter:
    name: str            # variable en el SQL -> {{name}}
    label: str
    type: date|month|text|number|combo|checkbox
    default: Any
    required: bool
    options: list[str]   # solo para type=combo

ProcessDefinition:
    id: str               # ej. "CMR/ResultadosQubo"
    name, module, description
    parameters: list[Parameter]
    final_table: str       # ej. "##BASE_QUBO"
    sql_path: Path
    show_preview, export_excel: bool

Workflow:
    id, name, description
    steps: list[WorkflowStep(process_id, param_overrides)]

ExecutionRecord:            # persistido en history/history.jsonl
    process_id, process_name, started_at, finished_at,
    duration_seconds, row_count, status, error_message,
    parameters_used
```

## 7. Cómo agregar un proceso nuevo (sin tocar Python)

```
processes/
    <Modulo>/
        <NombreProceso>/
            process.json     <- parámetros, tabla final
            query.sql        <- SQL con {{VARIABLES}}
            icon.png          <- opcional
```

1. Copiar una carpeta de ejemplo (p. ej. `processes/CMR/ResultadosQubo`).
2. Escribir el `.sql` reemplazando valores fijos por `{{NOMBRE_VARIABLE}}`.
3. Editar `process.json` con el mismo nombre de variable en `parameters`.
4. Asegurarse de que el script deje el resultado en una tabla temporal y
   que ese nombre coincida con `"final_table"`.
5. Reiniciar la app (o agregar un botón "Recargar procesos", ver sección 9).

La app detecta la carpeta automáticamente vía `ProcessRepository.load_all()`,
que hace `rglob("process.json")` sobre `/processes`.

### Ejemplo de `process.json`

```json
{
  "name": "Clientes Inactivos",
  "module": "CMR",
  "description": "Clientes sin transacciones en los últimos 90 días",
  "parameters": [
    { "name": "COD_MES", "label": "Mes", "type": "month", "default": "current" },
    { "name": "DIAS_INACTIVIDAD", "label": "Días de inactividad", "type": "number", "default": 90 }
  ],
  "final_table": "##CLIENTES_INACTIVOS",
  "show_preview": true,
  "export_excel": true
}
```

### Ejemplo de SQL parametrizado

```sql
IF OBJECT_ID('tempdb..##CLIENTES_INACTIVOS') IS NOT NULL DROP TABLE ##CLIENTES_INACTIVOS;

SELECT COD_CLIENTE, MAX(FECHA_TRANSACCION) AS ULTIMA_TRANSACCION
INTO ##CLIENTES_INACTIVOS
FROM BD_NEGOCIO.dbo.TRANSACCIONES
WHERE COD_MES = {{COD_MES}}
GROUP BY COD_CLIENTE
HAVING DATEDIFF(DAY, MAX(FECHA_TRANSACCION), GETDATE()) > {{DIAS_INACTIVIDAD}};
```

## 8. Cómo crear un Workflow nuevo

Crear un archivo en `workflows/<nombre>.json`:

```json
{
  "name": "Cierre Mensual",
  "description": "...",
  "steps": [
    { "process_id": "GobiernoDatos/CalidadDatos", "parameters": {} },
    { "process_id": "CMR/ResultadosQubo", "parameters": { "PROVEEDOR": "QUBOS" } },
    { "process_id": "Modelos/Riesgo", "parameters": {} }
  ]
}
```

`process_id` es la ruta relativa de la carpeta dentro de `/processes`
(con `/`, tal como aparece en `ProcessDefinition.id`).
Los `parameters` definidos aquí sobrescriben los "últimos parámetros
usados" guardados por `HistoryService` para ese proceso.

## 9. Extensiones sugeridas (siguientes pasos)

Cosas que dejé como base sólida pero que conviene añadir según el uso real:

- **Botón "Recargar procesos"** en la topbar, para no reiniciar la app al
  agregar una carpeta nueva (`MainWindow._reload_data()` ya existe, solo
  falta conectarlo a un botón y a un `QFileSystemWatcher` sobre `/processes`).
- **Encriptar `config/settings.json`** si se guarda usuario/contraseña SQL
  (hoy se guarda en texto plano; con autenticación de Windows no aplica).
- **Paginación en `PreviewTableWidget`** si algún `final_table` supera
  ~200k filas, para no cargar todo en memoria de una vez.
- **Editor de `process.json` desde la UI** (formulario en vez de editar
  el JSON a mano) si los usuarios de negocio no son técnicos.
- **Tests unitarios** de `SqlTemplateEngine` y `ProcessRepository`, que al
  no depender de PySide6 ni de una base real, son triviales de testear.

## 10. Ejecución

```bash
pip install -r requirements.txt
python main.py
```

Ajusta la conexión (server, base de datos, driver) desde
**Configuración** dentro de la app, o editando directamente
`config/settings.json`.
