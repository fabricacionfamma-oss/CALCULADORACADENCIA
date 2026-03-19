import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Sincronizador FAMMA", page_icon="⚙️")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF
def generar_pdf(df_final, maq_sel, f_inicio, f_fin):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE PRODUCCIÓN SINCRONIZADO", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Maquina: {maq_sel} | Periodo: {f_inicio} a {f_fin}", ln=True, align='C')
    pdf.ln(10)

    # Tabla de Resultados
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(50, 10, "Tipo (Refs en Datos)", border=1, fill=True)
    pdf.cell(45, 10, "Tiempo Prod (Hs)", border=1, fill=True)
    pdf.cell(45, 10, "Total Buenas (Pzas)", border=1, fill=True)
    pdf.cell(50, 10, "Cadencia (Hs/Pza)", border=1, ln=True, fill=True)
    
    pdf.set_font("Arial", '', 10)
    for _, row in df_final.iterrows():
        pdf.cell(50, 9, str(row['Tipo']), border=1)
        pdf.cell(45, 9, f"{row['Tiempo_Hs']:.2f}", border=1)
        pdf.cell(45, 9, f"{int(row['Buenas'])}", border=1)
        pdf.cell(50, 9, f"{row['Cadencia_Hs']:.4f}", border=1, ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(190, 5, "Nota: Las piezas y el tiempo provienen de la pestaña 'Producción'. La clasificación de Referencias proviene del cruce con la pestaña 'Datos' por Fecha y Turno.")

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS (Doble Pestaña)
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
URL_PROD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=315437448"
URL_DATOS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=300)
def load_and_sync_data(url_p, url_d):
    # Cargar Producción
    df_p = pd.read_csv(url_p)
    df_p.columns = [c.strip() for c in df_p.columns]
    df_p['Fecha'] = pd.to_datetime(df_p['Fecha'], errors='coerce')
    
    # Cargar Datos
    df_d = pd.read_csv(url_d)
    df_d.columns = [c.strip() for c in df_d.columns]
    df_d['Fecha'] = pd.to_datetime(df_d['Fecha'], errors='coerce')

    return df_p.dropna(subset=['Fecha', 'Máquina']), df_d.dropna(subset=['Fecha', 'Máquina'])

# --- INTERFAZ CENTRALIZADA ---
st.title("📄 Generador de Reportes Cruzados")
st.markdown("Cruce automático entre pestañas **Producción** (Valores) y **Datos** (Referencias).")

try:
    df_prod_raw, df_datos_raw = load_and_sync_data(URL_PROD, URL_DATOS)
    
    st.write("---")
    lista_maquinas = sorted(df_prod_raw['Máquina'].unique())
    maquina_sel = st.selectbox("1. Seleccione la Máquina", lista_maquinas)
    
    min_d, max_d = df_prod_raw['Fecha'].min().date(), df_prod_raw['Fecha'].max().date()
    c1, c2 = st.columns(2)
    with c1: start_date = st.date_input("2. Fecha Inicio", min_d)
    with c2: end_date = st.date_input("3. Fecha Fin", max_d)

    if start_date <= end_date:
        # Filtrar ambas fuentes
        p_mask = (df_prod_raw['Máquina'] == maquina_sel) & (df_prod_raw['Fecha'].dt.date >= start_date) & (df_prod_raw['Fecha'].dt.date <= end_date)
        d_mask = (df_datos_raw['Máquina'] == maquina_sel) & (df_datos_raw['Fecha'].dt.date >= start_date) & (df_datos_raw['Fecha'].dt.date <= end_date)
        
        df_p = df_prod_raw[p_mask].copy()
        df_d = df_datos_raw[d_mask].copy()

        # A. Analizar Referencias en Pestaña DATOS (Producto 1 al 4)
        def get_unique_refs(row):
            prods = [row.get('Producto 1'), row.get('Producto 2'), row.get('Producto 3'), row.get('Producto 4')]
            return {str(p).strip() for p in prods if pd.notnull(p) and str(p).strip() != '' and str(p).lower() != 'nan'}

        df_d['Refs'] = df_d.apply(get_unique_refs, axis=1)
        
        # Agrupar DATOS por Fecha/Turno para saber complejidad
        complex_map = df_d.groupby(['Fecha', 'Turno'])['Refs'].apply(lambda x: len(set().union(*x))).reset_index()
        complex_map['Tipo'] = complex_map['Refs'].apply(lambda x: 'Una Referencia' if x <= 1 else 'Multireferencia')

        # B. Procesar PRODUCCIÓN (Tomar Tiempos y Piezas)
        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo Producción (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

        # C. CRUZAR: Asignar el "Tipo" de la pestaña DATOS a la pestaña PRODUCCIÓN
        df_final = df_p.merge(complex_map[['Fecha', 'Turno', 'Tipo']], on=['Fecha', 'Turno'], how='left')
        df_final['Tipo'] = df_final['Tipo'].fillna('Sin Datos de Referencia')

        # D. Agrupar para el PDF
        resumen = df_final.groupby('Tipo').agg({
            'Tiempo_Hs': 'sum',
            'Buenas': 'sum'
        }).reset_index()
        
        resumen['Cadencia_Hs'] = np.where(resumen['Buenas'] > 0, resumen['Tiempo_Hs'] / resumen['Buenas'], 0)

        # --- BOTÓN DE EXPORTACIÓN ---
        st.write("---")
        pdf_bytes = generar_pdf(resumen, maquina_sel, start_date, end_date)
        
        st.download_button(
            label=f"💾 DESCARGAR REPORTE SINCRONIZADO: {maquina_sel}",
            data=pdf_bytes,
            file_name=f"Reporte_Sincro_{maquina_sel}_{start_date}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
        st.success(f"Sincronización exitosa: {len(df_final)} registros de producción analizados.")

    else:
        st.error("Error: Rango de fechas inválido.")

except Exception as e:
    st.error(f"Error de proceso: {e}")
