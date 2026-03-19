import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Exportador de Reportes FAMMA", page_icon="📄")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF (Lógica interna)
def generar_pdf(df_maq, df_prod, fecha_inicio, fecha_fin):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Título y Fechas
    pdf.cell(190, 10, "Reporte de Cadencia y Productividad - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Periodo analizado: {fecha_inicio} al {fecha_fin}", ln=True, align='C')
    pdf.ln(10)
    
    # Tabla de Máquinas
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "1. Resumen de Cadencia por Maquina (Min/Pza)", ln=True)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(70, 8, "Maquina", border=1)
    pdf.cell(40, 8, "Una Ref", border=1)
    pdf.cell(40, 8, "Multiref", border=1)
    pdf.cell(40, 8, "Promedio", border=1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    for _, row in df_maq.iterrows():
        pdf.cell(70, 7, str(row['Máquina'])[:30], border=1)
        pdf.cell(40, 7, f"{row.get('Una Referencia', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Multireferencia', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Promedio Global', 0):.3f}", border=1, ln=True)
    
    pdf.ln(10)
    
    # Tabla de Productos
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "2. Impacto de Multireferencia por Producto", ln=True)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(30, 8, "Codigo", border=1)
    pdf.cell(80, 8, "Producto", border=1)
    pdf.cell(40, 8, "Cad. Excl.", border=1)
    pdf.cell(40, 8, "Impacto %", border=1, ln=True)
    
    pdf.set_font("Arial", '', 8)
    # Filtramos solo los que tengan impacto calculado
    df_prod_filtered = df_prod[df_prod['Impacto Multiref (%)'] != 0].sort_values('Impacto Multiref (%)', ascending=False).head(20)
    for _, row in df_prod_filtered.iterrows():
        pdf.cell(30, 7, str(row['Código'])[:12], border=1)
        pdf.cell(80, 7, str(row['Producto'])[:45], border=1)
        pdf.cell(40, 7, f"{row.get('Cadencia (Excluida)', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Impacto Multiref (%)', 0):.1f}%", border=1, ln=True)
        
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS (GOOGLE SHEETS)
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
GID = "315437448" 
URL_G_SHEETS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

@st.cache_data(ttl=300)
def load_and_clean_data(url):
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    cols_num = ['Buenas', 'Tiempo Producción (Min)']
    for col in cols_num:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])
    return df

# --- INTERFAZ ÚNICA ---
st.title("📄 Generador de Reportes PDF")
st.info("Configura las fechas y descarga el análisis de cadencias directamente.")

try:
    data_raw = load_and_clean_data(URL_G_SHEETS)
    
    # Selectores de fecha en la página principal
    min_d = data_raw['Fecha'].min().date()
    max_d = data_raw['Fecha'].max().date()
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        start_date = st.date_input("Fecha Inicio", min_d, min_value=min_d, max_value=max_d)
    with col_f2:
        end_date = st.date_input("Fecha Fin", max_d, min_value=min_d, max_value=max_d)

    if start_date <= end_date:
        # --- PROCESAMIENTO SILENCIOSO ---
        df = data_raw[(data_raw['Fecha'].dt.date >= start_date) & (data_raw['Fecha'].dt.date <= end_date)].copy()
        
        # Lógica de Cadencia
        idx_cols = ['Máquina', 'Fecha', 'Turno']
        sesiones = df.groupby(idx_cols)['Código Producto'].nunique().reset_index()
        sesiones.columns = idx_cols + ['Num_Prods']
        df = df.merge(sesiones, on=idx_cols)
        df['Tipo'] = df['Num_Prods'].apply(lambda x: 'Una Referencia' if x == 1 else 'Multireferencia')

        # Resumen Máquina
        res_maq = df.groupby(['Máquina', 'Tipo']).agg({'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'}).reset_index()
        res_maq['Cadencia'] = np.where(res_maq['Buenas'] > 0, res_maq['Tiempo Producción (Min)'] / res_maq['Buenas'], 0)
        pivot_maq = res_maq.pivot(index='Máquina', columns='Tipo', values='Cadencia').reset_index()
        for c in ['Una Referencia', 'Multireferencia']:
            if c not in pivot_maq: pivot_maq[c] = 0.0
        pivot_maq['Promedio Global'] = pivot_maq[['Una Referencia', 'Multireferencia']].replace(0, np.nan).mean(axis=1).fillna(0)

        # Resumen Producto
        res_prod = df.groupby(['Código Producto', 'Producto', 'Tipo']).agg({'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'}).reset_index()
        res_prod['CadReal'] = np.where(res_prod['Buenas'] > 0, res_prod['Tiempo Producción (Min)'] / res_prod['Buenas'], 0)
        pivot_prod = res_prod.pivot(index=['Código Producto', 'Producto'], columns='Tipo', values='CadReal').reset_index()
        pivot_prod.columns = [c if c not in ['Una Referencia', 'Multireferencia'] else ('Cadencia (Excluida)' if c=='Una Referencia' else 'Cadencia (Multiref)') for c in pivot_prod.columns]
        
        pivot_prod['Impacto Multiref (%)'] = 0.0
        if 'Cadencia (Excluida)' in pivot_prod and 'Cadencia (Multiref)' in pivot_prod:
            mask = (pivot_prod['Cadencia (Excluida)'] > 0) & (pivot_prod['Cadencia (Multiref)'] > 0)
            pivot_prod.loc[mask, 'Impacto Multiref (%)'] = ((pivot_prod['Cadencia (Multiref)'] - pivot_prod['Cadencia (Excluida)']) / pivot_prod['Cadencia (Excluida)']) * 100

        # --- BOTÓN DE EXPORTACIÓN ---
        st.write("---")
        pdf_bytes = generar_pdf(pivot_maq, pivot_prod, start_date, end_date)
        
        st.download_button(
            label="📊 DESCARGAR REPORTE EN PDF",
            data=pdf_bytes,
            file_name=f"Reporte_Cadencia_{start_date}_{end_date}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
        st.success(f"Datos procesados correctamente para {len(df)} registros.")
    else:
        st.error("La fecha de inicio debe ser anterior a la fecha de fin.")

except Exception as e:
    st.error(f"Hubo un problema al conectar con Google Sheets: {e}")
