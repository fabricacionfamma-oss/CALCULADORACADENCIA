import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Sincronizador Multimáquina FAMMA", page_icon="⚙️", layout="centered")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF
def generar_pdf(df_final, maquinas_sel, f_inicio, f_fin):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE PRODUCTIVIDAD MULTIMÁQUINA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    maqs_txt = ", ".join(maquinas_sel) if len(maquinas_sel) < 5 else "Múltiples Máquinas"
    pdf.cell(190, 8, f"Maquinas: {maqs_txt}", ln=True, align='C')
    pdf.cell(190, 8, f"Periodo: {f_inicio} a {f_fin}", ln=True, align='C')
    pdf.ln(10)

    # Tabla de Resultados
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(50, 10, "Tipo (Refs en Datos)", border=1, fill=True)
    pdf.cell(45, 10, "Tiempo Prod (Hs)", border=1, fill=True)
    pdf.cell(45, 10, "Total Buenas (Pzas)", border=1, fill=True)
    pdf.cell(50, 10, "Cadencia (Pza/Hs)", border=1, ln=True, fill=True)
    
    pdf.set_font("Arial", '', 10)
    for _, row in df_final.iterrows():
        pdf.cell(50, 9, str(row['Tipo']), border=1)
        pdf.cell(45, 9, f"{row['Tiempo_Hs']:.2f}", border=1)
        pdf.cell(45, 9, f"{int(row['Buenas'])}", border=1)
        # Cadencia: Piezas / Horas
        pdf.cell(50, 9, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(190, 5, "Nota: El cálculo de Cadencia (Pza/Hs) representa la velocidad de producción. Los datos de tiempo y piezas provienen de 'Producción', cruzados con la complejidad de 'Datos'.")

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
st.title("📄 Reporte Consolidado FAMMA")
st.markdown("Cruce de datos para múltiples máquinas simultáneas.")

try:
    df_prod_raw, df_datos_raw = load_and_sync_data(URL_PROD, URL_DATOS)
    
    st.write("---")
    
    # 1. MULTI-SELECTOR DE MÁQUINAS
    lista_maquinas = sorted(df_prod_raw['Máquina'].unique())
    maquinas_sel = st.multiselect("1. Seleccione las Máquinas", lista_maquinas, default=None)
    
    # 2. SELECTOR DE FECHAS
    min_d, max_d = df_prod_raw['Fecha'].min().date(), df_prod_raw['Fecha'].max().date()
    c1, c2 = st.columns(2)
    with c1: start_date = st.date_input("2. Fecha Inicio", min_d)
    with c2: end_date = st.date_input("3. Fecha Fin", max_d)

    if maquinas_sel and start_date <= end_date:
        # Filtrado por Múltiples Máquinas y Rango
        p_mask = (df_prod_raw['Máquina'].isin(maquinas_sel)) & (df_prod_raw['Fecha'].dt.date >= start_date) & (df_prod_raw['Fecha'].dt.date <= end_date)
        d_mask = (df_datos_raw['Máquina'].isin(maquinas_sel)) & (df_datos_raw['Fecha'].dt.date >= start_date) & (df_datos_raw['Fecha'].dt.date <= end_date)
        
        df_p = df_prod_raw[p_mask].copy()
        df_d = df_datos_raw[d_mask].copy()

        # A. ANALIZAR REFERENCIAS (Pestaña DATOS)
        def get_unique_refs(row):
            prods = [row.get('Producto 1'), row.get('Producto 2'), row.get('Producto 3'), row.get('Producto 4')]
            return {str(p).strip() for p in prods if pd.notnull(p) and str(p).strip() != '' and str(p).lower() != 'nan'}

        df_d['Refs'] = df_d.apply(get_unique_refs, axis=1)
        # Sincronizamos por Máquina, Fecha y Turno para precisión multimáquina
        complex_map = df_d.groupby(['Máquina', 'Fecha', 'Turno'])['Refs'].apply(lambda x: len(set().union(*x))).reset_index()
        complex_map['Tipo'] = complex_map['Refs'].apply(lambda x: 'Una Referencia' if x <= 1 else 'Multireferencia')

        # B. PROCESAR VALORES (Pestaña PRODUCCIÓN)
        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo Producción (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

        # C. CRUZAR
        df_final = df_p.merge(complex_map[['Máquina', 'Fecha', 'Turno', 'Tipo']], on=['Máquina', 'Fecha', 'Turno'], how='left')
        df_final['Tipo'] = df_final['Tipo'].fillna('Sin Datos de Referencia')

        # D. AGRUPAR PARA EL PDF
        resumen = df_final.groupby('Tipo').agg({
            'Tiempo_Hs': 'sum',
            'Buenas': 'sum'
        }).reset_index()
        
        # Cadencia: Piezas / Horas (Pza/Hs)
        resumen['Pzas_Por_Hora'] = np.where(resumen['Tiempo_Hs'] > 0, resumen['Buenas'] / resumen['Tiempo_Hs'], 0)

        # --- BOTÓN DE EXPORTACIÓN ---
        st.write("---")
        pdf_bytes = generar_pdf(resumen, maquinas_sel, start_date, end_date)
        
        st.download_button(
            label=f"💾 GENERAR PDF ({len(maquinas_sel)} máquinas seleccionadas)",
            data=pdf_bytes,
            file_name=f"Reporte_FAMMA_Multimaquina.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
        st.success(f"Análisis listo para las máquinas seleccionadas.")

    elif not maquinas_sel:
        st.info("Por favor, seleccione al menos una máquina arriba.")
    else:
        st.error("Rango de fechas inválido.")

except Exception as e:
    st.error(f"Error de proceso: {e}")
