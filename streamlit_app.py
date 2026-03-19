import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Analizador FAMMA", layout="wide")

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
        pdf.cell(190, 7, txt, border=1, ln=True)
    
    pdf.ln(10)
    # Tabla Productos
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "2. Impacto por Producto (Top 10)", ln=True)
    pdf.set_font("Arial", '', 9)
    for i, row in df_prod.head(10).iterrows():
        txt_prod = f"{row['Código']} - {row['Producto'][:30]}: Impacto {row['Impacto Multiref (%)']:.1f}%"
        pdf.cell(190, 7, txt_prod, border=1, ln=True)
        
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- Interfaz de Streamlit ---
st.title("📊 Calculador de Cadencia FAMMA")

uploaded_file = st.file_uploader("Sube tu archivo de producción (Excel o CSV)", type=['xlsx', 'csv'])

if uploaded_file is not None:
    # 1. Leer datos
    df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
    df.columns = [c.strip() for c in df.columns]

    # 2. Convertir columna Fecha a datetime
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']) # Eliminar filas con fechas inválidas
        
        # --- FILTRO DE FECHAS EN EL SIDEBAR ---
        st.sidebar.header("Filtros de Informe")
        min_date = df['Fecha'].min().date()
        max_date = df['Fecha'].max().date()
        
        rango_fechas = st.sidebar.date_input(
            "Selecciona el rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        # Verificar que se seleccionaron ambas fechas (inicio y fin)
        if len(rango_fechas) == 2:
            start_date, end_date = rango_fechas
            # Filtrar el DataFrame original
            mask = (df['Fecha'].dt.date >= start_date) & (df['Fecha'].dt.date <= end_date)
            df_filtrado = df.loc[mask].copy()
            
            st.success(f"Analizando datos desde {start_date} hasta {end_date}")
        else:
            st.warning("Por favor selecciona una fecha de inicio y una de fin.")
            st.stop()
    else:
        st.error("No se encontró la columna 'Fecha' en el archivo.")
        st.stop()

    # 3. Procesamiento (Identificar Sesiones sobre los datos filtrados)
    # Agrupamos por Máquina, Fecha y Turno
    sesiones = df_filtrado.groupby(['Máquina', 'Fecha', 'Turno'])['Código Producto'].nunique().reset_index()
    sesiones.columns = ['Máquina', 'Fecha', 'Turno', 'Cant_Refs']
    df_filtrado = df_filtrado.merge(sesiones, on=['Máquina', 'Fecha', 'Turno'])
    df_filtrado['Tipo'] = df_filtrado['Cant_Refs'].apply(lambda x: 'Una Referencia' if x == 1 else 'Multireferencia')

    # 4. Cálculos de Máquina
    resumen_maq = df_filtrado.groupby(['Máquina', 'Tipo']).agg({'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'}).reset_index()
    resumen_maq['Cadencia'] = resumen_maq['Tiempo Producción (Min)'] / resumen_maq['Buenas']
    pivot_maq = resumen_maq.pivot(index='Máquina', columns='Tipo', values='Cadencia').reset_index()
    
    # Asegurar que existan ambas columnas para evitar errores de cálculo
    if 'Una Referencia' not in pivot_maq: pivot_maq['Una Referencia'] = np.nan
    if 'Multireferencia' not in pivot_maq: pivot_maq['Multireferencia'] = np.nan
    
    pivot_maq['Promedio Global'] = pivot_maq[['Una Referencia', 'Multireferencia']].mean(axis=1)

    # 5. Cálculos de Producto
    resumen_prod = df_filtrado.groupby(['Código Producto', 'Producto', 'Tipo']).agg({'Buenas': 'sum', 'Tiempo Producción (Min)': 'sum'}).reset_index()
    resumen_prod['CadReal'] = resumen_prod['Tiempo Producción (Min)'] / resumen_prod['Buenas']
    pivot_prod = resumen_prod.pivot(index=['Código Producto', 'Producto'], columns='Tipo', values='CadReal').reset_index()
    
    # Renombrar dinámicamente según lo que exista
    pivot_prod.columns = [c if c not in ['Una Referencia', 'Multireferencia'] else ('Cadencia (Excluida)' if c=='Una Referencia' else 'Cadencia (Multiref)') for c in pivot_prod.columns]
    
    if 'Cadencia (Excluida)' in pivot_prod and 'Cadencia (Multiref)' in pivot_prod:
        pivot_prod['Impacto Multiref (%)'] = ((pivot_prod['Cadencia (Multiref)'] - pivot_prod['Cadencia (Excluida)']) / pivot_prod['Cadencia (Excluida)']) * 100
    else:
        pivot_prod['Impacto Multiref (%)'] = 0

    # 6. Mostrar en Pantalla
    st.subheader("Análisis de Cadencia por Máquina")
    st.dataframe(pivot_maq.style.format(precision=3))
    
    st.subheader("Análisis de Cadencia por Producto")
    st.dataframe(pivot_prod.sort_values(by='Impacto Multiref (%)', ascending=False).style.format(precision=2))

    # 7. Exportar PDF
    st.divider()
    st.subheader("📄 Exportar Reporte Formal")
    
    try:
        pdf_data = generar_pdf(pivot_maq, pivot_prod, start_date, end_date)
        st.download_button(
            label=f"Descargar Reporte ({start_date} a {end_date})",
            data=pdf_data,
            file_name=f"reporte_famma_{start_date}_{end_date}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error al generar el PDF: {e}")

else:
    st.info("Sube el archivo de producción para habilitar los filtros de fecha y cálculos.")
