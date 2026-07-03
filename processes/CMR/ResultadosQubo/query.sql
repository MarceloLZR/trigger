-- =========================================================
-- Proceso: Resultados QUBO
-- Descripción: ETL de resultados de campañas por proveedor.
-- Variables disponibles (reemplazadas automáticamente):
--   {{COD_MES}}, {{FECHA_INICIO}}, {{FECHA_FIN}}, {{PROVEEDOR}}
-- =========================================================

IF OBJECT_ID('tempdb..##BASE_CAMPANAS') IS NOT NULL DROP TABLE ##BASE_CAMPANAS;
IF OBJECT_ID('tempdb..##BASE_QUBO') IS NOT NULL DROP TABLE ##BASE_QUBO;

-- 1. Base inicial de campañas del mes
SELECT
    c.COD_CLIENTE,
    c.COD_CAMPANA,
    c.PROVEEDOR,
    c.FECHA_GESTION,
    c.RESULTADO,
    c.COD_MES
INTO ##BASE_CAMPANAS
FROM BD_NEGOCIO.dbo.CAMPANAS c
WHERE c.COD_MES = {{COD_MES}}
  AND c.FECHA_GESTION BETWEEN {{FECHA_INICIO}} AND {{FECHA_FIN}}
  AND c.PROVEEDOR = '{{PROVEEDOR}}';

-- 2. Cruce con maestro de clientes para enriquecer la base
SELECT
    b.COD_CLIENTE,
    m.NOMBRE_CLIENTE,
    b.COD_CAMPANA,
    b.PROVEEDOR,
    b.FECHA_GESTION,
    b.RESULTADO,
    b.COD_MES
INTO ##BASE_QUBO
FROM ##BASE_CAMPANAS b
LEFT JOIN BD_NEGOCIO.dbo.MAESTRO_CLIENTES m
    ON m.COD_CLIENTE = b.COD_CLIENTE
GROUP BY
    b.COD_CLIENTE, m.NOMBRE_CLIENTE, b.COD_CAMPANA,
    b.PROVEEDOR, b.FECHA_GESTION, b.RESULTADO, b.COD_MES;

-- La aplicación leerá automáticamente ##BASE_QUBO (final_table en process.json)
