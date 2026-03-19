import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Generador de Reportes FAMMA", page_icon="📄")

# 2. FUNCIÓN PARA GENERAR EL REPORTE PDF
def generar_pdf(df_resumen, maq_sel, f_inicio, f_fin):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE TÉCNICO DE CADENCIA - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Máquina: {maq_sel}", ln=True, align='C')
    pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(10)

    # Tabla de Resultados (Tiempo en Horas)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(50, 10, "Tipo Trabajo", border=1, fill=True)
    pdf.cell(45, 10, "Tiempo Prod (Hs)", border=1, fill=True)
    pdf.cell(45, 10, "Total Piezas", border=1, fill=True)
    pdf.cell(50, 10, "Cadencia (Hs/Pza)", border=1, ln=True, fill=True)
    
    pdf.set_font("Arial", '', 10)
    for _, row in df_resumen.iterrows():
        pdf.cell(50, 9, str(row['Tipo']), border=1)
        # Tiempo ya convertido a horas en la lógica de procesamiento
        pdf.cell(45, 9, f"{row['Tiempo_Hs']:.2f}", border=1)
        pdf.cell(45, 9, f"{int(row['Evento'])}", border=1)
        # Cadencia calculada como Hs / Piezas
        pdf.cell(50, 9, f"{row['Cadencia_Hs']:.4f}", border=1, ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(190, 5, "Nota: El tiempo se ha convertido de minutos a horas (Min/60). La cadencia representa cuántas horas toma producir una pieza.")

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS (Google Sheets GID=0 - Pestaña DATOS)
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
URL_DATOS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=300)
def load_data(url):
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    
    # Limpieza de Tiempo y conversión a HORAS (Minutos / 60)
    if 'Tiempo (Min)' in df.columns:
        df['Tiempo_Min_Num'] = pd.to_numeric(df['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['Tiempo_Hs'] = df['Tiempo_Min_Num'] / 60
    
    # Limpieza de Fechas
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    return df.dropna(subset=['Fecha', 'Máquina'])

# --- INTERFAZ CENTRALIZADA ---
st.title("📄 Exportador de Cadencia (Hs)")
st.markdown("Generación de reportes basados en la pestaña **DATOS** con conversión a horas.")

try:
    df_raw = load_data(URL_DATOS)
    
    st.write("---")
    
    # 1. Selector de Máquina
    lista_maquinas = sorted(df_raw['Máquina'].unique())
    maquina_seleccionada = st.selectbox("1. Seleccione la Máquina", lista_maquinas)
    
    # 2. Selectores de Fecha
    min_d, max_d = df_raw['Fecha'].min().date(), df_raw['Fecha'].max().date()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        start_date = st.date_input("2. Fecha Inicio", min_d)
    with col_f2:
        end_date = st.date_input("3. Fecha Fin", max_d)

    if start_date <= end_date:
        # Filtrado por Máquina y Rango
        df_f = df_raw[
            (df_raw['Máquina'] == maquina_seleccionada) & 
            (df_raw['Fecha'].dt.date >= start_date) & 
            (df_raw['Fecha'].dt.date <= end_date)
        ].copy()

        # Lógica Multireferencia (Producto 1-4)
        def obtener_refs(row):
            prods = [row.get('Producto 1'), row.get('Producto 2'), row.get('Producto 3'), row.get('Producto 4')]
            return {str(p).strip() for p in prods if pd.notnull(p) and str(p).strip() != '' and str(p).lower() != 'nan'}

        df_f['Refs_Fila'] = df_f.apply(obtener_refs, axis=1)
        
        idx = ['Máquina', 'Fecha', 'Turno']
        turno_info = df_f.groupby(idx)['Refs_Fila'].apply(lambda x: len(set().union(*x))).reset_index()
        turno_info.columns = idx + ['Total_Refs_Turno']
        
        df_f = df_f.merge(turno_info, on=idx)
        df_f['Tipo'] = df_f['Total_Refs_Turno'].apply(lambda x: 'Una Referencia' if x <= 1 else 'Multireferencia')

        # Cálculos Finales en HORAS
        resumen = df_f.groupby('Tipo').agg({
            'Tiempo_Hs': 'sum',
            'Evento': 'count'
        }).reset_index()
        
        # Cadencia: Tiempo Total (Hs) / Total Piezas (Evento)
        resumen['Cadencia_Hs'] = np.where(resumen['Evento'] > 0, resumen['Tiempo_Hs'] / resumen['Evento'], 0)

        # --- BOTÓN DE EXPORTACIÓN ---
        st.write("---")
        pdf_bytes = generar_pdf(resumen, maquina_seleccionada, start_date, end_date)
        
        st.download_button(
            label=f"💾 DESCARGAR REPORTE EN HORAS: {maquina_seleccionada}",
            data=pdf_bytes,
            file_name=f"Reporte_Hs_{maquina_seleccionada}_{start_date}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
        st.success(f"Configuración lista. Registros encontrados: {len(df_f)}")

    else:
        st.error("Error: La fecha de inicio debe ser anterior a la fecha de fin.")

except Exception as e:
    st.error(f"Error al procesar: {e}")
