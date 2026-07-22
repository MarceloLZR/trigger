-- =========================================================
-- Proceso: Resultados QUBO
-- Descripción:
--   Genera la base final de resultados de gestión QUBO,
--   cruza con feedback de llamadas y primera compra posterior
--   dentro del rango indicado.
--
-- Variables disponibles:
--   {{COD_MES}}
--   {{FECHA_INICIO}}
--   {{FECHA_FIN}}
--   {{PROVEEDOR}}
--   {{CALL_CENTER}}
--   {{TIPO_XCLU}}
-- =========================================================


/* =========================================================
   1. Limpieza de tablas temporales globales
   ========================================================= */

IF OBJECT_ID('tempdb..##BASE_QUBO') IS NOT NULL DROP TABLE ##BASE_QUBO;
IF OBJECT_ID('tempdb..##RES_QUBO') IS NOT NULL DROP TABLE ##RES_QUBO;
IF OBJECT_ID('tempdb..##RES_QUBOFIN') IS NOT NULL DROP TABLE ##RES_QUBOFIN;
IF OBJECT_ID('tempdb..##COMPRA_TODS') IS NOT NULL DROP TABLE ##COMPRA_TODS;
IF OBJECT_ID('tempdb..##COMPRA_FINAL') IS NOT NULL DROP TABLE ##COMPRA_FINAL;


/* =========================================================
   2. Base inicial QUBO
   ========================================================= */

SELECT
    COD_CLIE,
    TIPO_BASE,
    MESES_INAC
INTO ##BASE_QUBO
FROM CRM.TB_CAMP_INACTIVOS_HIST
WHERE CALL_CENTER = '{{CALL_CENTER}}'
  AND TIPO_XCLU = '{{TIPO_XCLU}}'
  AND COD_MES = {{COD_MES}};


/* =========================================================
   3. Resultados de feedback de gestión
   ========================================================= */

SELECT
    A.COD_CLIE,
    A.COD_DIA AS FECHA_LLAMADA,
    MIN(A.COD_FEEDBACK) AS ID_DESCRIP,
    B.RESULTADO,
    B.MOTIVO,
    B.SUBMOTIVO
INTO ##RES_QUBO
FROM CRM.FEEDBACK_GESTION A
INNER JOIN MDL.CODIGOS_FEEDBACK B
    ON A.COD_FEEDBACK = B.CODIGO
WHERE A.ELECCION = 'INACTIVOS'
  AND A.PROVEEDOR = '{{PROVEEDOR}}'
  AND A.COD_MES = {{COD_MES}}
GROUP BY
    A.COD_CLIE,
    A.COD_DIA,
    B.RESULTADO,
    B.MOTIVO,
    B.SUBMOTIVO;


/* =========================================================
   4. Seleccionar mejor/primer resultado por cliente
      Ordena por menor feedback y luego primera fecha llamada
   ========================================================= */

SELECT
    COD_CLIE,
    FECHA_LLAMADA,
    RESULTADO,
    MOTIVO,
    SUBMOTIVO,
    ROW_NUMBER() OVER (
        PARTITION BY COD_CLIE
        ORDER BY ID_DESCRIP ASC, FECHA_LLAMADA ASC
    ) AS ORDEN
INTO ##RES_QUBOFIN
FROM ##RES_QUBO;


/* =========================================================
   5. Agregar columnas de gestión a la base
   ========================================================= */

ALTER TABLE ##BASE_QUBO
ADD
    RESULTADO VARCHAR(80),
    MOTIVO VARCHAR(50),
    SUBMOTIVO VARCHAR(150),
    FECH_LLAMADA VARCHAR(8);


/* =========================================================
   6. Actualizar resultado de llamada
   ========================================================= */

UPDATE A
SET
    A.RESULTADO = B.RESULTADO,
    A.MOTIVO = B.MOTIVO,
    A.SUBMOTIVO = B.SUBMOTIVO,
    A.FECH_LLAMADA = CONVERT(VARCHAR(8), B.FECHA_LLAMADA)
FROM ##BASE_QUBO A
INNER JOIN ##RES_QUBOFIN B
    ON A.COD_CLIE = B.COD_CLIE
WHERE B.ORDEN = 1;


/* =========================================================
   7. Compras dentro del rango de campaña
   ========================================================= */

SELECT
    M.COD_CLIE,
    M.COD_DIA,
    M.NUM_MNTO_TRX
INTO ##COMPRA_TODS
FROM CRM.DWF_BANC_CENC_TARJ_CRED_MOVI M
WHERE M.COD_DIA BETWEEN {{FECHA_INICIO}} AND {{FECHA_FIN}}
  AND M.COD_CLIE IN (
        SELECT COD_CLIE
        FROM ##BASE_QUBO
  )
  AND M.COD_GRUP_CATE_MOVI = 1
  AND M.COD_NEGO IN ('1', '2', '4')
  AND M.NUM_MNTO_TRX > 0
GROUP BY
    M.COD_CLIE,
    M.COD_DIA,
    M.NUM_MNTO_TRX;


/* =========================================================
   8. Primera compra por cliente
   ========================================================= */

SELECT
    COD_CLIE,
    COD_DIA,
    NUM_MNTO_TRX,
    ROW_NUMBER() OVER (
        PARTITION BY COD_CLIE
        ORDER BY COD_DIA ASC
    ) AS NRO
INTO ##COMPRA_FINAL
FROM ##COMPRA_TODS;


/* =========================================================
   9. Agregar columnas de compra a la base final
   ========================================================= */

ALTER TABLE ##BASE_QUBO
ADD
    COD_DIA2 VARCHAR(8),
    MONTO DECIMAL(9,2);


/* =========================================================
   10. Actualizar primera compra
   ========================================================= */

UPDATE A
SET
    A.COD_DIA2 = CONVERT(VARCHAR(8), B.COD_DIA),
    A.MONTO = B.NUM_MNTO_TRX
FROM ##BASE_QUBO A
INNER JOIN ##COMPRA_FINAL B
    ON A.COD_CLIE = B.COD_CLIE
WHERE B.NRO = 1;


/* =========================================================
   11. Resultado final
   ========================================================= */