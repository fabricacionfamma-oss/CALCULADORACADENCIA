import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Reporte Detallado FAMMA", page_icon="🏭", layout="centered")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF
def generar_pdf(dict_resumenes, dict_productos, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Encabezado General
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE PRODUCTIVIDAD POR MÁQUINA Y PRODUCTO", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(5)

    for maquina in dict_resumenes.keys():
        # --- TITULO MÁQUINA ---
        pdf.set_font("Arial", 'B', 13)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(50, 50, 50)
        pdf.cell(190, 10, f" MÁQUINA: {maquina}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        # --- CUADRO 1: RESUMEN MÁQUINA ---
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 7, "Resumen de Rendimiento por Complejidad:", ln=True)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(60, 8, "Cant. Referencias", border=1, fill=True, align='C')
        pdf.cell(40, 8, "Tiempo (Hs)", border=1, fill=True, align='C')
        pdf.cell(40, 8, "Total Piezas", border=1, fill=True, align='C')
        pdf.cell(50, 8, "Pza / Hs", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        df_res = dict_resumenes[maquina]
        for _, row in df_res.iterrows():
            pdf.cell(60, 7, f"{int(row['Cant_Refs'])} Referencia(s)", border=1)
            pdf.cell(40, 7, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        
        pdf.ln(3)

        # --- CUADRO 2: DESGLOSE POR PRODUCTO ---
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 7, f"Desglose Individual por Código ({maquina}):", ln=True)
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(35, 8, "Código", border=1, fill=True)
        pdf.cell(45, 8, "Estado", border=1, fill=True)
        pdf.cell(25, 8, "Piezas", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Horas", border=1, fill=True, align='C')
        pdf.cell(30, 8, "Pza / Hs", border=1, fill=True, align='C')
        pdf.cell(30, 8, "Refs Turno", border=1, ln=True, fill=True, align='C')

        pdf.set_font("Arial", '', 8)
        df_prod = dict_productos[maquina]
        for _, row in df_prod.iterrows():
            estado = "Solo" if row['Cant_Refs'] == 1 else "Acompañado"
            pdf.cell(35, 7, str(row['Código Producto'])[:15], border=1)
            pdf.cell(45, 7, estado, border=1)
            pdf.cell(25, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(30, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, align='C')
            pdf.cell(30, 7, f"{int(row['Cant_Refs'])}", border=1, ln=True, align='C')
        
        pdf.ln(10) # Espacio antes de la siguiente máquina

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
URL_PROD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=315437448"
URL_DATOS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=300)
def load_and_sync_data(url_p, url_d):
    df_p = pd.read_csv(url_p)
    df_p.columns = [c.strip() for c in df_p.columns]
    df_p['Fecha'] = pd.to_datetime(df_p['Fecha'], errors='coerce')
    df_d = pd.read_csv(url_d)
    df_d.columns = [c.strip() for c in df_d.columns]
    df_d['Fecha'] = pd.to_datetime(df_d['Fecha'], errors='coerce')
    return df_p.dropna(subset=['Fecha', 'Máquina']), df_d.dropna(subset=['Fecha', 'Máquina'])

# --- INTERFAZ ---
st.title("📄 Reporte de Cadencia FAMMA")
st.markdown("Generación de cuadros comparativos por máquina y producto.")

try:
    df_prod_raw, df_datos_raw = load_and_sync_data(URL_PROD, URL_DATOS)
    
    lista_maquinas = sorted(df_prod_raw['Máquina'].unique())
    maquinas_sel = st.multiselect("1. Seleccione las Máquinas", lista_maquinas)
    
    min_d, max_d = df_prod_raw['Fecha'].min().date(), df_prod_raw['Fecha'].max().date()
    c1, c2 = st.columns(2)
    with c1: start_date = st.date_input("2. Fecha Inicio", min_d)
    with c2: end_date = st.date_input("3. Fecha Fin", max_d)

    if maquinas_sel and start_date <= end_date:
        resumenes_maq = {}
        resumenes_prod = {}

        for maq in maquinas_sel:
            df_p = df_prod_raw[(df_prod_raw['Máquina'] == maq) & (df_prod_raw['Fecha'].dt.date >= start_date) & (df_prod_raw['Fecha'].dt.date <= end_date)].copy()
            df_d = df_datos_raw[(df_datos_raw['Máquina'] == maq) & (df_datos_raw['Fecha'].dt.date >= start_date) & (df_datos_raw['Fecha'].dt.date <= end_date)].copy()

            if not df_p.empty:
                # A. Referencias en DATOS
                def get_refs(row):
                    p_cols = [row.get('Producto 1'), row.get('Producto 2'), row.get('Producto 3'), row.get('Producto 4')]
                    return {str(p).strip() for p in p_cols if pd.notnull(p) and str(p).strip() != '' and str(p).lower() != 'nan'}

                df_d['Refs_Set'] = df_d.apply(get_refs, axis=1)
                complexity = df_d.groupby(['Fecha', 'Turno'])['Refs_Set'].apply(lambda x: len(set().union(*x))).reset_index()
                complexity.columns = ['Fecha', 'Turno', 'Cant_Refs']

                # B. Preparar Producción
                df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo Producción (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
                df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

                # C. Cruzar
                df_merged = df_p.merge(complexity, on=['Fecha', 'Turno'], how='left')
                df_merged['Cant_Refs'] = df_merged['Cant_Refs'].fillna(1)

                # D. Resumen Máquina
                res_maq = df_merged.groupby('Cant_Refs').agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                res_maq['Pzas_Por_Hora'] = np.where(res_maq['Tiempo_Hs'] > 0, res_maq['Buenas'] / res_maq['Tiempo_Hs'], 0)
                resumenes_maq[maq] = res_maq

                # E. Desglose Producto
                res_prod = df_merged.groupby(['Código Producto', 'Cant_Refs']).agg({'Buenas': 'sum', 'Tiempo_Hs': 'sum'}).reset_index()
                res_prod['Pzas_Por_Hora'] = np.where(res_prod['Tiempo_Hs'] > 0, res_prod['Buenas'] / res_prod['Tiempo_Hs'], 0)
                resumenes_prod[maq] = res_prod.sort_values(['Código Producto', 'Cant_Refs'])

        if resumenes_maq:
            st.write("---")
            pdf_bytes = generar_pdf(resumenes_maq, resumenes_prod, start_date, end_date)
            st.download_button(label="📥 DESCARGAR REPORTE PDF COMPLETO", data=pdf_bytes, file_name=f"Reporte_Analitico_FAMMA.pdf", mime="application/pdf", use_container_width=True)
            st.success("Análisis procesado. El PDF contiene los cuadros resumen y los desgloses por código de cada máquina.")

except Exception as e:
    st.error(f"Error: {e}")
