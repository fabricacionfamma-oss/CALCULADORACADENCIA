import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Reporte por Máquina FAMMA", page_icon="🏭", layout="centered")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF (Un cuadro por máquina)
def generar_pdf(dict_resumenes, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for maquina, df_res in dict_resumenes.items():
        pdf.add_page()
        
        # Encabezado por Máquina
        pdf.set_font("Arial", 'B', 15)
        pdf.cell(190, 10, f"REPORTE DE PRODUCTIVIDAD: {maquina}", ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(190, 8, f"Periodo: {f_inicio} a {f_fin}", ln=True, align='C')
        pdf.ln(10)

        # Tabla de Resultados
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(60, 10, "Cant. de Referencias", border=1, fill=True, align='C')
        pdf.cell(40, 10, "Tiempo (Hs)", border=1, fill=True, align='C')
        pdf.cell(40, 10, "Total Piezas", border=1, fill=True, align='C')
        pdf.cell(50, 10, "Piezas por Hora", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 10)
        for _, row in df_res.iterrows():
            # Texto descriptivo según cantidad de referencias
            txt_ref = f"{int(row['Cant_Refs'])} Referencia(s)"
            
            pdf.cell(60, 9, txt_ref, border=1)
            pdf.cell(40, 9, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 9, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 9, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 8)
        pdf.multi_cell(190, 5, f"Nota: La columna 'Cant. de Referencias' indica cuántos productos distintos se detectaron en la pestaña Datos para los turnos de la máquina {maquina}.")

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
URL_PROD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=315437448"
URL_DATOS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=300)
def load_and_sync_data(url_p, url_d):
    # Producción
    df_p = pd.read_csv(url_p)
    df_p.columns = [c.strip() for c in df_p.columns]
    df_p['Fecha'] = pd.to_datetime(df_p['Fecha'], errors='coerce')
    # Datos
    df_d = pd.read_csv(url_d)
    df_d.columns = [c.strip() for c in df_d.columns]
    df_d['Fecha'] = pd.to_datetime(df_d['Fecha'], errors='coerce')
    return df_p.dropna(subset=['Fecha', 'Máquina']), df_d.dropna(subset=['Fecha', 'Máquina'])

# --- INTERFAZ ---
st.title("📄 Reporte por Máquina y Referencias")
st.markdown("Genera un análisis de velocidad (Piezas/Hora) desglosado por cantidad de productos.")

try:
    df_prod_raw, df_datos_raw = load_and_sync_data(URL_PROD, URL_DATOS)
    
    st.write("---")
    lista_maquinas = sorted(df_prod_raw['Máquina'].unique())
    maquinas_sel = st.multiselect("1. Seleccione las Máquinas", lista_maquinas)
    
    min_d, max_d = df_prod_raw['Fecha'].min().date(), df_prod_raw['Fecha'].max().date()
    c1, c2 = st.columns(2)
    with c1: start_date = st.date_input("2. Fecha Inicio", min_d)
    with c2: end_date = st.date_input("3. Fecha Fin", max_d)

    if maquinas_sel and start_date <= end_date:
        # Contenedor de resultados para el PDF
        resultados_por_maquina = {}

        for maq in maquinas_sel:
            # Filtrar por máquina actual
            df_p = df_prod_raw[(df_prod_raw['Máquina'] == maq) & (df_prod_raw['Fecha'].dt.date >= start_date) & (df_prod_raw['Fecha'].dt.date <= end_date)].copy()
            df_d = df_datos_raw[(df_datos_raw['Máquina'] == maq) & (df_datos_raw['Fecha'].dt.date >= start_date) & (df_datos_raw['Fecha'].dt.date <= end_date)].copy()

            if not df_p.empty:
                # A. Detectar Cantidad de Referencias en DATOS
                def get_refs(row):
                    p_cols = [row.get('Producto 1'), row.get('Producto 2'), row.get('Producto 3'), row.get('Producto 4')]
                    return {str(p).strip() for p in p_cols if pd.notnull(p) and str(p).strip() != '' and str(p).lower() != 'nan'}

                df_d['Refs_Set'] = df_d.apply(get_refs, axis=1)
                # Agrupar por Turno/Fecha para contar cuántas refs únicas hubo
                complexity = df_d.groupby(['Fecha', 'Turno'])['Refs_Set'].apply(lambda x: len(set().union(*x))).reset_index()
                complexity.columns = ['Fecha', 'Turno', 'Cant_Refs']

                # B. Preparar Producción
                df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo Producción (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
                df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

                # C. Cruzar
                df_merged = df_p.merge(complexity, on=['Fecha', 'Turno'], how='left')
                df_merged['Cant_Refs'] = df_merged['Cant_Refs'].fillna(1) # Si no hay datos, asumimos al menos 1

                # D. Resumen para esta máquina
                res_maq = df_merged.groupby('Cant_Refs').agg({
                    'Tiempo_Hs': 'sum',
                    'Buenas': 'sum'
                }).reset_index()
                
                # Piezas por Hora
                res_maq['Pzas_Por_Hora'] = np.where(res_maq['Tiempo_Hs'] > 0, res_maq['Buenas'] / res_maq['Tiempo_Hs'], 0)
                
                resultados_por_maquina[maq] = res_maq

        # --- BOTÓN DE EXPORTACIÓN ---
        if resultados_por_maquina:
            st.write("---")
            pdf_bytes = generar_pdf(resultados_por_maquina, start_date, end_date)
            st.download_button(
                label=f"💾 DESCARGAR REPORTE ({len(maquinas_sel)} CUADROS)",
                data=pdf_bytes,
                file_name=f"Reporte_FAMMA_Desglosado.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.success("Reporte generado. Cada máquina tiene su propia página y cuadro en el PDF.")
        else:
            st.warning("No se encontraron datos de producción para los criterios seleccionados.")

    elif not maquinas_sel:
        st.info("Seleccione máquinas para comenzar.")

except Exception as e:
    st.error(f"Error: {e}")
