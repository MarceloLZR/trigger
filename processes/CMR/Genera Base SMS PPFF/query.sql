-- =========================================================
-- Proceso: Generación de Base SMS PPFF
-- Descripción:
--   Genera bases de email y SMS para clientes PPFF con 
--   segmentación por producto (SAE/SAR), monto mínimo, 
--   propensión y enrolamiento digital.
--   Los mensajes se calculan en Python usando las reglas de la UI.
--
-- Variables disponibles:
--   {{CAMPANA}}                -- mes de campaña (yyyyMM)
--   {{ELECCION_TIPO}}          -- filtro de elecciones (SAR y SAE, Solo SAR, Solo SAE)
--   {{FILTRAR_MONTO}}          -- flag de filtro monto (1 o 0)
--   {{MONTO_MINIMO}}           -- monto mínimo
--   {{FILTRAR_PROPENSION}}     -- flag de filtro propensión (1 o 0)
--   {{COD_MES_MODELO}}         -- mes de modelo propensión
--   {{DECIL_LIST}}             -- lista de deciles a considerar (ej: 1,2)
--   {{SOLO_ENROLADOS_DIGITAL}} -- flag de filtro digital (1 o 0)
--   {{SIEMBRA_MENSAJE_TEMPLATE}}-- mensaje para base de siembras
--   {{TIPO_SIEMBRA_VAL}}       -- valor de TIPO_SIEMBRA (ej: SMS-CALL)
--   {{URL_PROMO}}              -- URL de promoción para base con URL
-- =========================================================

-- 1. Filtrar base inicial de elecciones
DROP TABLE IF EXISTS ##ALERTA_SAE_SAP_ACTUAL

SELECT
    CASE 
        WHEN TIPDOC = 1 THEN '1' + CODDOC 
        ELSE '2000' + CODDOC 
    END AS COD_CLIE,
    ELECCION,
    CASE 
        WHEN ELECCION IN ('SAE', 'SAR') THEN PCT_SAE 
        ELSE NULL 
    END AS PCT,
    CASE 
        WHEN ELECCION = 'SAE' THEN LINEA_SAE 
        WHEN ELECCION = 'SAR' THEN MONTO_DESEMBOLSAR 
        ELSE NULL 
    END AS MONTO
INTO ##ALERTA_SAE_SAP_ACTUAL
FROM CRM.ELECCION_SAE_SAP
WHERE CAMPANA = '{{CAMPANA}}'
  AND (
      ('{{ELECCION_TIPO}}' = 'SAR y SAE' AND ELECCION IN ('SAR', 'SAE'))
      OR ('{{ELECCION_TIPO}}' = 'Solo SAR' AND ELECCION = 'SAR')
      OR ('{{ELECCION_TIPO}}' = 'Solo SAE' AND ELECCION = 'SAE')
  )
  -- Filtro por monto mínimo si está activo
  AND (
      {{FILTRAR_MONTO}} = 0
      OR (
          (ELECCION = 'SAE' AND LINEA_SAE >= {{MONTO_MINIMO}})
          OR (ELECCION = 'SAR' AND MONTO_DESEMBOLSAR >= {{MONTO_MINIMO}})
      )
  )

-- 2. Cruzar con base de comunicaciones para obtener Nombre y Celular
ALTER TABLE ##ALERTA_SAE_SAP_ACTUAL ADD NOMBRE VARCHAR(100), CELULAR VARCHAR(15)

UPDATE A
SET NOMBRE = B.NOMBRE, 
    CELULAR = B.CELULAR
FROM ##ALERTA_SAE_SAP_ACTUAL A
INNER JOIN CRM.GRAN_BASE_COMUNICACIONES B
    ON A.COD_CLIE = B.COD_CLIE

-- 3. Filtrar por propensión / decil si está activo
DROP TABLE IF EXISTS ##ALERTA_SAE_SAP_ACTUAL_PROP

SELECT 
    A.*, 
    M.DECIL
INTO ##ALERTA_SAE_SAP_ACTUAL_PROP
FROM ##ALERTA_SAE_SAP_ACTUAL A
LEFT JOIN BA.MODELO_SAE M
    ON A.COD_CLIE = M.COD_CLIE 
   AND M.COD_MES = {{COD_MES_MODELO}}
WHERE 
    {{FILTRAR_PROPENSION}} = 0
    OR M.DECIL IN ({{DECIL_LIST}})

-- 4. Limpieza de caracteres y formateo de la línea disponible
DROP TABLE IF EXISTS ##SMS_EC

SELECT 
    A.CELULAR, 
    A.COD_CLIE, 
    A.ELECCION,
    A.DECIL,
    TRANSLATE(A.NOMBRE, 'áéíóúÁÉÍÓÚñÑäëïöü', 'aeiouAEIOUnnaeiou') AS NOMBRE_, 
    A.PCT,
    CAST(A.MONTO / 100 AS INT) * 100 AS LINEA_DISP
INTO ##SMS_EC
FROM ##ALERTA_SAE_SAP_ACTUAL_PROP A
LEFT JOIN STG.SMS_EMAIL_PPFF_0 B
    ON A.COD_CLIE = B.COD_CLIE 
   AND (B.ELECCION LIKE 'SAE%' OR B.ELECCION LIKE 'SAR%')

-- 5. Filtrar por enrolados digitales si está activo
DROP TABLE IF EXISTS ##ENROLADOS

SELECT DISTINCT COD_CLIE 
INTO ##ENROLADOS
FROM CRM.ACTIVIDAD_DIGITAL WITH(NOLOCK)
WHERE TIPO_ACTIVIDAD IN ('Registrar Clave Digital', 'Validar') 
  AND ESTADO_ACTIVIDAD = 'CONFORME'
  AND CANAL = 'APP'

DROP TABLE IF EXISTS ##SMS_EC_FINAL

SELECT * 
INTO ##SMS_EC_FINAL
FROM ##SMS_EC
WHERE 
    {{SOLO_ENROLADOS_DIGITAL}} = 0
    OR COD_CLIE IN (SELECT COD_CLIE FROM ##ENROLADOS)

-- 6. Pre-cargar ##SMS_FINAL únicamente con la base de siembras
-- Python se encargará de realizar el append de la base procesada por reglas
DROP TABLE IF EXISTS ##SMS_FINAL;

SELECT 
    CELULAR, 
    REPLACE('{{SIEMBRA_MENSAJE_TEMPLATE}}', '"Nombre"', NOMBRE) AS MENSAJE,
    CASE 
        WHEN '{{URL_PROMO}}' <> '' THEN '{{URL_PROMO}}'
        ELSE NULL
    END AS URL
INTO ##SMS_FINAL
FROM CRM.BASE_SIEMBRAS 
WHERE TIPO_SIEMBRA = '{{TIPO_SIEMBRA_VAL}}'
