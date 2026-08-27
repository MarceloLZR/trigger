import pandas as pd
import numpy as np

def post_process(results, params, log, conn):
    log("Iniciando motor de reglas de mensaje en Python...")
    
    # 1. Obtener la tabla de reglas de los parámetros
    rules = params.get("REGLAS_MENSAJE")
    if not rules:
        log("[Advertencia] No se especificó ninguna regla de mensaje en la UI. Saltando procesamiento.")
        return
        
    log(f"Cargadas {len(rules)} reglas desde la interfaz gráfica.")
    
    # 2. Leer la base cruda ##SMS_EC_FINAL desde SQL Server
    log("Leyendo base temporal ##SMS_EC_FINAL de SQL Server...")
    try:
        df_raw = pd.read_sql("SELECT * FROM ##SMS_EC_FINAL", conn)
    except Exception as e:
        log(f"[Error] No se pudo leer ##SMS_EC_FINAL: {e}")
        raise e
        
    total_raw = df_raw.shape[0]
    log(f"Total registros crudos a procesar: {total_raw}")
    if total_raw == 0:
        log("No hay registros en la base cruda para procesar.")
        return
        
    # 3. Evaluar cada cliente contra las reglas
    mensajes = []
    urls = []
    
    url_promo = params.get("URL_PROMO", "")
    url_val = str(url_promo).strip() if url_promo else ""
    
    matched_count = 0
    for idx, row in df_raw.iterrows():
        pct = row["PCT"]
        linea = row["LINEA_DISP"]
        elec = row["ELECCION"]
        decil = row["DECIL"]
        nombre = row["NOMBRE_"]
        
        # Coerción de tipos segura
        decil_val = int(decil) if decil is not None and not pd.isna(decil) else None
        pct_val = float(pct) if pct is not None and not pd.isna(pct) else None
        linea_val = float(linea) if linea is not None and not pd.isna(linea) else None
        
        mensaje_final = None
        
        # Evaluar reglas en orden secuencial (la primera coincidencia gana)
        for rule in rules:
            # A. Validar PCT
            p_min = rule.get("PCT_MIN")
            p_max = rule.get("PCT_MAX")
            if p_min is not None and not pd.isna(p_min) and str(p_min).strip() != "":
                if pct_val is None or not (float(p_min) <= pct_val <= float(p_max)):
                    continue
            
            # B. Validar Línea Mínima
            l_min = rule.get("LINEA_MIN")
            if l_min is not None and not pd.isna(l_min) and str(l_min).strip() != "":
                if linea_val is None or not (linea_val >= float(l_min)):
                    continue
                    
            # C. Validar Elección (SAE, SAR, AMBOS)
            r_elec = rule.get("ELECCION")
            if r_elec and not pd.isna(r_elec) and str(r_elec).strip() != "":
                r_elec_str = str(r_elec).strip().upper()
                if r_elec_str != "AMBOS" and r_elec_str != str(elec).strip().upper():
                    continue
                    
            # D. Validar Decil (ej: "1,2")
            r_decils_str = rule.get("DECIL_LIST")
            if r_decils_str and not pd.isna(r_decils_str) and str(r_decils_str).strip() != "":
                try:
                    r_decils = [int(x.strip()) for x in str(r_decils_str).split(",") if x.strip().isdigit()]
                    if decil_val is None or decil_val not in r_decils:
                        continue
                except Exception:
                    continue # Error de formato de lista de deciles, ignoramos regla
            
            # Si pasa todas las validaciones de la regla, construimos el mensaje
            template = str(rule.get("MENSAJE_TEMPLATE", ""))
            cuotas = rule.get("CUOTAS")
            tasa_text = rule.get("TASA_TEXT")
            
            cuotas_val = str(int(float(cuotas))) if cuotas is not None and not pd.isna(cuotas) and str(cuotas).strip() != "" else "60"
            tasa_text_val = str(tasa_text).strip() if tasa_text is not None and not pd.isna(tasa_text) else ""
            
            msg = template
            msg = msg.replace('"Nombre"', str(nombre))
            msg = msg.replace('"MONTO"', str(int(linea_val)) if linea_val is not None else "")
            msg = msg.replace('{Cuotas}', cuotas_val)
            msg = msg.replace('{Tasa_Texto}', tasa_text_val)
            
            mensaje_final = msg
            break
            
        if mensaje_final:
            mensajes.append(mensaje_final)
            urls.append(url_val if url_val != "" else None)
            matched_count += 1
        else:
            mensajes.append(None)
            urls.append(None)
            
    df_raw["MENSAJE"] = mensajes
    df_raw["URL"] = urls
    
    # 4. Quedarse solo con registros coincidentes
    df_processed = df_raw.dropna(subset=["MENSAJE"])
    df_processed = df_processed[["CELULAR", "MENSAJE", "URL"]]
    log(f"Clientes emparejados exitosamente: {matched_count} de {total_raw} ({matched_count/total_raw*100:.1f}%)")
    
    # 5. Concatenar con la tabla ##SMS_FINAL (que contiene el grupo de siembras)
    for res in results:
        if res["final_table"].table == "##SMS_FINAL":
            df_siembras = res["df"]
            log(f"Registros de siembras pre-cargados: {df_siembras.shape[0]}")
            
            df_final = pd.concat([df_processed, df_siembras], ignore_index=True)
            res["df"] = df_final
            log(f"DataFrame final ##SMS_FINAL generado exitosamente con {df_final.shape[0]} registros en total.")
            break
