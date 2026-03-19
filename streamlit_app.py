import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Reporte Producción FAMMA", page_icon="🏭")

# 2. FUNCIÓN PDF
def generar_pdf(df_maq, df_diario, f_inicio, f_fin):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE OPERACIONES Y CADENCIA - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Rango: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(5)

    # SECCIÓN 1: Actividad Diaria
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "1. Resumen de Actividad Diaria (Pestaña Datos)", ln=True)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(40, 8, "Fecha", border=1)
    pdf.cell(40, 8, "N° Eventos", border=1)
    pdf.cell(55, 8, "Tiempo Total (Min)", border=1)
    pdf.cell(55, 8, "Cadencia Promedio", border=1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    for _, row in df_diario.iterrows():
        pdf.cell(40, 7, str(row['Fecha'].date()), border=1)
        pdf.cell(40, 7, f"{int(row['Evento'])}", border=1)
        pdf.cell(55, 7, f"{row['Tiempo (Min)']:.1f}", border=1)
        cad_prom = row['Tiempo (Min)']/row['Evento'] if row['Evento'] > 0 else 0
        pdf.cell(55, 7, f"{cad_prom:.2f} min/ev", border=1, ln=True)
    
    pdf.ln(10)

    # SECCIÓN 2: Cadencias por Máquina
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "2. Analisis de Cadencia (Una Ref vs Multiref)", ln=True)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(70, 8, "Maquina", border=1)
    pdf.cell(40, 8, "Una Ref (Exc)", border=1)
    pdf.cell(40, 8, "Multiref", border=1)
    pdf.cell(40, 8, "Promedio", border=1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    for _, row in df_maq.iterrows():
        pdf.cell(70, 7, str(row['Máquina'])[:30], border=1)
        pdf.cell(40, 7, f"{row.get('Una Referencia', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Multireferencia', 0):.3f}", border=1)
        pdf.cell(40, 7, f"{row.get('Promedio Global', 0):.3f}", border=1, ln=True)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
URL_DATOS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=300)
def load_data(url):
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    
    # Limpieza de Tiempo
    if 'Tiempo (Min)' in df.columns:
        df['Tiempo (Min)'] = pd.to_numeric(df['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    # Limpieza de Fecha
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    return df.dropna(subset=['Fecha'])

# 4. LÓGICA DE LA APP
st.title("📄 Generador de Reportes FAMMA")
st.info("Analizando actividad diaria y cadencias (Productos 1 al 4).")

try:
    df_raw = load_data(URL_DATOS)
    min_d, max_d = df_raw['Fecha'].min().date(), df_raw['Fecha'].max().date()
    
    f_inicio = st.date_input("Fecha Inicio", min_d)
    f_fin = st.date_input("Fecha Fin", max_d)

    if f_inicio <= f_fin:
        df_f = df_raw[(df_raw['Fecha'].dt.date >= f_inicio) & (df_raw['Fecha'].dt.date <= f_fin)].copy()

        # A. Resumen Diario
        df_diario = df_f.groupby('Fecha').agg({'Evento': 'count', 'Tiempo (Min)': 'sum'}).reset_index()

        # B. Lógica Multireferencia (Producto 1 hasta Producto 4)
        def contar_referencias_fila(row):
            # Extraer valores de las 4 columnas de productos y quitar nulos/vacíos
            prods = [row.get('Producto 1'), row.get('Producto 2'), row.get('Producto 3'), row.get('Producto 4')]
            valid_prods = {str(p).strip() for p in prods if pd.notnull(p) and str(p).strip() != '' and str(p).lower() != 'nan'}
            return list(valid_prods)

        # Aplicamos la función para identificar qué productos hay en cada fila
        df_f['Lista_Prods'] = df_f.apply(contar_referencias_fila, axis=1)

        # Agrupamos por Máquina/Turno para ver cuántos productos distintos hubo en total
        idx = ['Máquina', 'Fecha', 'Turno']
        turno_resumen = df_f.groupby(idx)['Lista_Prods'].sum().reset_index()
        # Contar elementos únicos en la lista de productos del turno
        turno_resumen['Total_Refs_Turno'] = turno_resumen['Lista_Prods'].apply(lambda x: len(set(x)))
        
        # Unimos de vuelta
        df_f = df_f.merge(turno_resumen[idx + ['Total_Refs_Turno']], on=idx)
        df_f['Tipo'] = df_f['Total_Refs_Turno'].apply(lambda x: 'Una Referencia' if x <= 1 else 'Multireferencia')

        # C. Cálculo de Cadencia
        res_maq = df_f.groupby(['Máquina', 'Tipo']).agg({'Evento': 'count', 'Tiempo (Min)': 'sum'}).reset_index()
        res_maq['Cadencia'] = np.where(res_maq['Evento'] > 0, res_maq['Tiempo (Min)'] / res_maq['Evento'], 0)
        
        pivot_maq = res_maq.pivot(index='Máquina', columns='Tipo', values='Cadencia').reset_index()
        for c in ['Una Referencia', 'Multireferencia']:
            if c not in pivot_maq: pivot_maq[c] = 0.0
        pivot_maq['Promedio Global'] = pivot_maq[['Una Referencia', 'Multireferencia']].replace(0, np.nan).mean(axis=1).fillna(0)

        # D. Botón PDF
        st.divider()
        pdf_bytes = generar_pdf(pivot_maq, df_diario, f_inicio, f_fin)
        
        st.download_button(
            label="📊 DESCARGAR REPORTE PDF",
            data=pdf_bytes,
            file_name=f"Reporte_FAMMA_{f_inicio}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        st.success(f"Procesados {len(df_f)} eventos considerando referencias hasta Producto 4.")

except Exception as e:
    st.error(f"Error: {e}")
