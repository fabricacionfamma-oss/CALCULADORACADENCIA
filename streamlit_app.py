import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Analizador FAMMA - OEE", layout="wide")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF
def generar_pdf(df_maq, df_prod, fecha_inicio, fecha_fin):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Título y Fechas
    pdf.cell(190, 10, "Reporte de Cadencia y Productividad - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Periodo analizado: {fecha_inicio} al {fecha_fin}", ln=True, align='C')
    pdf.ln(5)
    
    # Tabla de Máquinas
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "1. Resumen de Cadencia por Maquina (Min/Pza)", ln=True)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(60, 8, "Maquina", border=1)
    pdf.cell(40, 8, "Una Ref", border=1)
    pdf.cell(40, 8, "Multiref", border=1)
    pdf.cell(50, 8, "Promedio", border=1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    for _, row in df_maq.iterrows():
        pdf.cell(60, 7, str(row['Máquina'])[:25], border=1)
        pdf.cell(40, 7, f"{row.get('Una Referencia', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Multireferencia', 0):.3f}", border=1)
        pdf.cell(50, 7, f"{row.get('Promedio Global', 0):.3f}", border=1, ln=True)
    
    pdf.ln(10)
    
    # Tabla de Productos (Top 15 Impacto)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "2. Impacto de Multireferencia por Producto", ln=True)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(30, 8, "Codigo", border=1)
    pdf.cell(80, 8, "Producto", border=1)
    pdf.cell(40, 8, "Cad. Excluida", border=1)
    pdf.cell(40, 8, "Impacto %", border=1, ln=True)
    
    pdf.set_font("Arial", '', 8)
    top_impacto = df_prod.sort_values('Impacto Multiref (%)', ascending=False).head(15)
    for _, row in top_impacto.iterrows():
        pdf.cell(30, 7, str(row['Código'])[:12], border=1)
        pdf.cell(80, 7, str(row['Producto'])[:45], border=1)
        pdf.cell(40, 7, f"{row.get('Cadencia (Excluida)', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Impacto Multiref (%)', 0):.1f}%", border=1, ln=True)
        
    # El PDF se genera como string de bytes para Streamlit
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CONEXIÓN A GOOGLE SHEETS
# Link directo de exportación CSV de la pestaña 'Produccion'
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
GID = "315437448" 
URL_G_SHEETS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

@st.cache_data(ttl=300) # Se actualiza cada 5 minutos
def load_and_clean_data(url):
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    
    # Limpieza de columnas numéricas (evita el error str/int)
    cols_num = ['Buenas', 'Tiempo Producción (Min)', 'Retrabajo', 'Observadas']
    for col in cols_num:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Convertir Fechas
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])
    
    return df

# --- INICIO DE LA APP ---
st.title("🚀 Analizador de Cadencia FAMMA")
st.markdown("Datos obtenidos en tiempo real de Google Sheets.")

try:
    data_raw = load_and_clean_data(URL_G_SHEETS)
    
    # Filtros en Sidebar
    st.sidebar.header("Configuración de Informe")
    min_d = data_raw['Fecha'].min().date()
    max_d = data_raw['Fecha'].max().date()
    
    rango = st.sidebar.date_input("Selecciona Rango de Fechas", [min_d, max_d], min_value=min_d, max_value=max_d)

    if len(rango) == 2:
        inicio, fin = rango
        # Filtrado de datos por fecha
        df = data_raw[(data_raw['Fecha'].dt.date >= inicio) & (data_raw['Fecha'].dt.date <= fin)].copy()

        # --- LÓGICA DE CÁLCULO ---
        # 1. Identificar si el turno fue Mono-referencia o Multi-referencia
        idx_cols = ['Máquina', 'Fecha', 'Turno']
        sesiones = df.groupby(idx_cols)['Código Producto'].nunique().reset_index()
        sesiones.columns = idx_cols + ['Num_Prods']
        
        df = df.merge(sesiones, on=idx_cols)
        df['Tipo Trabajo'] = df['Num_Prods'].apply(lambda x: 'Una Referencia' if x == 1 else 'Multireferencia')

        # 2. Análisis por Máquina
        res_maq = df.groupby(['Máquina', 'Tipo Trabajo']).agg({
            'Buenas': 'sum', 
            'Tiempo Producción (Min)': 'sum'
        }).reset_index()
        
        # Calcular cadencia (Minutos por Pieza)
        res_maq['Cadencia'] = np.where(res_maq['Buenas'] > 0, res_maq['Tiempo Producción (Min)'] / res_maq['Buenas'], 0)
        
        pivot_maq = res_maq.pivot(index='Máquina', columns='Tipo Trabajo', values='Cadencia').reset_index()
        
        # Asegurar columnas
        for c in ['Una Referencia', 'Multireferencia']:
            if c not in pivot_maq: pivot_maq[c] = 0.0
            
        pivot_maq['Promedio Global'] = pivot_maq[['Una Referencia', 'Multireferencia']].replace(0, np.nan).mean(axis=1).fillna(0)

        # 3. Análisis por Producto
        res_prod = df.groupby(['Código Producto', 'Producto', 'Tipo Trabajo']).agg({
            'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'
        }).reset_index()
        res_prod['CadReal'] = np.where(res_prod['Buenas'] > 0, res_prod['Tiempo Producción (Min)'] / res_prod['Buenas'], 0)
        
        pivot_prod = res_prod.pivot(index=['Código Producto', 'Producto'], columns='Tipo Trabajo', values='CadReal').reset_index()
        pivot_prod.columns = [c if c not in ['Una Referencia', 'Multireferencia'] else ('Cadencia (Excluida)' if c=='Una Referencia' else 'Cadencia (Multiref)') for c in pivot_prod.columns]
        
        # Calcular impacto porcentual
        if 'Cadencia (Excluida)' in pivot_prod and 'Cadencia (Multiref)' in pivot_prod:
            # Solo calcular donde existan ambos valores para comparar
            mask = (pivot_prod['Cadencia (Excluida)'] > 0) & (pivot_prod['Cadencia (Multiref)'] > 0)
            pivot_prod['Impacto Multiref (%)'] = 0.0
            pivot_prod.loc[mask, 'Impacto Multiref (%)'] = ((pivot_prod['Cadencia (Multiref)'] - pivot_prod['Cadencia (Excluida)']) / pivot_prod['Cadencia (Excluida)']) * 100

        # --- MOSTRAR RESULTADOS ---
        st.subheader(f"📊 Resultados del {inicio} al {fin}")
        
        tab1, tab2 = st.tabs(["Análisis por Máquina", "Análisis por Producto"])
        
        with tab1:
            st.dataframe(pivot_maq.style.format(precision=3), use_container_width=True)
            
        with tab2:
            st.dataframe(pivot_prod.sort_values('Impacto Multiref (%)', ascending=False).style.format(precision=2), use_container_width=True)

        # --- EXPORTACIÓN ---
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            pdf_out = generar_pdf(pivot_maq, pivot_prod, inicio, fin)
            st.download_button(
                label="📥 Descargar Reporte PDF",
                data=pdf_out,
                file_name=f"Reporte_FAMMA_{inicio}_{fin}.pdf",
                mime="application/pdf"
            )
        with col_btn2:
            csv_data = pivot_prod.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Datos CSV", csv_data, "datos_famma.csv", "text/csv")

except Exception as e:
    st.error(f"⚠️ Error en el procesamiento: {e}")
    st.info("Revisa que las columnas del Google Sheets se llamen: 'Máquina', 'Fecha', 'Turno', 'Código Producto', 'Buenas' y 'Tiempo Producción (Min)'.")
