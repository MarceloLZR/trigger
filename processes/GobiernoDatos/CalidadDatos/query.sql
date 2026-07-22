IF OBJECT_ID('tempdb..##alpes') IS NOT NULL
    DROP TABLE ##alpes;

SELECT *
INTO ##alpes
FROM STG.TC_DIST_AMLPES;

SELECT *
FROM ##alpes;
------------------------------------------
IF OBJECT_ID('tempdb..##GESCOB') IS NOT NULL
    DROP TABLE GESCOB;

SELECT *
INTO ##GESCOB
FROM STG.TC_DIST_GESCOB;

SELECT *
FROM ##GESCOB;

-------------------------
IF OBJECT_ID('tempdb..##RyG') IS NOT NULL
    DROP TABLE ##RyG;

SELECT *
INTO ##RyG
FROM STG.TC_DIST_AMLPES;

SELECT *
FROM ##RyG;
