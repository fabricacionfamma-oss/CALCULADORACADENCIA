import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Analizador FAMMA - Google Sheets", layout="wide")

# --- Función para generar PDF ---
def generar_pdf(df_maq, df_prod, fecha_inicio, fecha_fin):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "Reporte de Cadencia y Productividad - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Periodo: {fecha_inicio} al {fecha_fin}", ln=True, align='C')
    pdf.ln(5)
    
    # Tabla Maquinas
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "1. Resumen por Maquina (Min/Pza)", ln=True)
    pdf.set_font("Arial", '', 10)
    for i, row in df_maq.iterrows():
        txt = f"Maquina: {row['Máquina']} | Una Ref: {row.get('Una Referencia', 0):.2f} | Multi: {row.get('Multireferencia', 0):.2f}"
        pdf.cell(190, 7, txt.encode('latin-1', 'ignore').decode('latin-1'), border=1, ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "2. Impacto por Producto (Top 10)", ln=True)
    pdf.set_font("Arial", '', 9)
    for i, row in df_prod.head(10).iterrows():
        txt_prod = f"{row['Código']} - {str(row['Producto'])[:30]}: Impacto {row['Impacto Multiref (%)']:.1f}%"
        pdf.cell(190, 7, txt_prod.encode('latin-1', 'ignore').decode('latin-1'), border=1, ln=True)
        
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- Conexión a Google Sheets ---
# Transformamos el link normal en un link de descarga directa CSV
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
GID = "315437448" # ID de la pestaña de Producción
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

st.title("📊 Monitor de Producción FAMMA (Google Sheets)")

@st.cache_data(ttl=600) # Se actualiza cada 10 minutos
def load_data(url):
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    return df

try:
    df_raw = load_data(url)
    st.sidebar.success("✅ Conectado a Google Sheets")
    
    # Procesar Fechas
    df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'], errors='coerce')
    df_raw = df_raw.dropna(subset=['Fecha'])

    # --- FILTRO DE FECHAS ---
    min_date = df_raw['Fecha'].min().date()
    max_date = df_raw['Fecha'].max().date()
    
    st.sidebar.header("Filtros de Informe")
    rango = st.sidebar.date_input("Rango de fechas", [min_date, max_date])

    if len(rango) == 2:
        start_date, end_date = rango
        mask = (df_raw['Fecha'].dt.date >= start_date) & (df_raw['Fecha'].dt.date <= end_date)
        df = df_raw.loc[mask].copy()

        # --- CALCULOS ---
        # 1. Identificar Sesiones (Celdas trabajando con una o más referencias)
        sesiones = df.groupby(['Máquina', 'Fecha', 'Turno'])['Código Producto'].nunique().reset_index()
        sesiones.columns = ['Máquina', 'Fecha', 'Turno', 'Cant_Refs']
        df = df.merge(sesiones, on=['Máquina', 'Fecha', 'Turno'])
        df['Tipo'] = df['Cant_Refs'].apply(lambda x: 'Una Referencia' if x == 1 else 'Multireferencia')

        # 2. Resumen Máquina
        res_maq = df.groupby(['Máquina', 'Tipo']).agg({'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'}).reset_index()
        res_maq['Cadencia'] = res_maq['Tiempo Producción (Min)'] / res_maq['Buenas']
        pivot_maq = res_maq.pivot(index='Máquina', columns='Tipo', values='Cadencia').reset_index()
        
        # Columnas de seguridad
        for col in ['Una Referencia', 'Multireferencia']:
            if col not in pivot_maq: pivot_maq[col] = np.nan
        pivot_maq['Promedio Global'] = pivot_maq[['Una Referencia', 'Multireferencia']].mean(axis=1)

        # 3. Resumen Producto
        res_prod = df.groupby(['Código Producto', 'Producto', 'Tipo']).agg({'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'}).reset_index()
        res_prod['CadReal'] = res_prod['Tiempo Producción (Min)'] / res_prod['Buenas']
        pivot_prod = res_prod.pivot(index=['Código Producto', 'Producto'], columns='Tipo', values='CadReal').reset_index()
        
        # Renombrar dinámicamente
        pivot_prod.columns = [c if c not in ['Una Referencia', 'Multireferencia'] else ('Cadencia (Excluida)' if c=='Una Referencia' else 'Cadencia (Multiref)') for c in pivot_prod.columns]
        
        if 'Cadencia (Excluida)' in pivot_prod and 'Cadencia (Multiref)' in pivot_prod:
            pivot_prod['Impacto Multiref (%)'] = ((pivot_prod['Cadencia (Multiref)'] - pivot_prod['Cadencia (Excluida)']) / pivot_prod['Cadencia (Excluida)']) * 100
        else:
            pivot_prod['Impacto Multiref (%)'] = 0

        # --- INTERFAZ ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Cadencia por Máquina")
            st.dataframe(pivot_maq.style.format(precision=3), use_container_width=True)
        with col2:
            st.subheader("Top Impacto por Cambio de Referencia")
            st.dataframe(pivot_prod.sort_values('Impacto Multiref (%)', ascending=False).head(10), use_container_width=True)

        # Botón PDF
        st.divider()
        pdf_bytes = generar_pdf(pivot_maq, pivot_prod, start_date, end_date)
        st.download_button("📥 Descargar Reporte PDF", pdf_bytes, f"reporte_famma_{start_date}.pdf", "application/pdf")

except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.info("Asegúrate de que el archivo de Google Sheets tenga activada la opción 'Cualquier persona con el enlace puede ver'.")
