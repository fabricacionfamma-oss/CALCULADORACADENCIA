import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="FAMMA | Reporte de Cadencia", page_icon="📄", layout="centered")

# Estilo visual simple
st.markdown("""
    <style>
    .main { text-align: center; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #004286; color: white; font-weight: bold; }
    .stTextInput>div>div>input { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNCIÓN PARA GENERAR EL PDF
def generar_pdf(dict_resumenes, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE ANALITICO DE PRODUCTIVIDAD - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Periodo Analizado: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(10)

    for maquina, df_res in dict_resumenes.items():
        # Título de la Máquina
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(40, 40, 40); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, f" MAQUINA: {maquina}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0); pdf.ln(2)

        # Tabla de Cadencia
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(235, 235, 235)
        pdf.cell(60, 10, "Complejidad (Cant. Refs)", border=1, fill=True, align='C')
        pdf.cell(40, 10, "Tiempo Prod (Hs)", border=1, fill=True, align='C')
        pdf.cell(40, 10, "Piezas Buenas", border=1, fill=True, align='C')
        pdf.cell(50, 10, "Piezas / Hora", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 10)
        for _, row in df_res.iterrows():
            pdf.cell(60, 9, f"{int(row['Cant_Refs'])} Referencia(s) en Turno", border=1)
            pdf.cell(40, 9, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 9, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 9, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(190, 5, "Nota: El reporte considera unicamente eventos etiquetados como 'Produccion'. El tiempo ha sido convertido de minutos a horas.")

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO DE DATOS DESDE GOOGLE SHEETS
def procesar_google_sheets(url):
    # Extraer ID y generar URL de exportación CSV
    match = re.search(r'd/([a-zA-Z0-9-_]+)', url)
    if not match: return None
    csv_url = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv"
    
    # Lectura de datos
    df = pd.read_csv(csv_url)
    df.columns = [c.strip() for c in df.columns]
    
    # --- CAMBIO SOLICITADO: UNIFICAR CELDA 15 ---
    df['Máquina'] = df['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
    
    # --- CAMBIO SOLICITADO: FILTRAR SOLO PRODUCCIÓN ---
    # Buscamos en 'Nivel 1' o la columna que contenga el tipo de evento
    if 'Nivel 1' in df.columns:
        df = df[df['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
    
    # Conversión de Tiempo y Buenas
    df['Fecha Inicio'] = pd.to_datetime(df['Fecha Inicio'], errors='coerce')
    df['Tiempo_Hs'] = pd.to_numeric(df['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
    df['Buenas'] = pd.to_numeric(df['Buenas'], errors='coerce').fillna(0)
    
    # Detección de Referencias Simultáneas
    def identificar_refs(r):
        prods = {str(r.get('Producto 1', '')), str(r.get('Producto 2', ''))}
        return {x for x in prods if x.lower() not in ['nan', '', 'none']}
    
    df['Refs_Fila'] = df.apply(identificar_refs, axis=1)
    df['Fecha_Dia'] = df['Fecha Inicio'].dt.date
    
    # Calcular complejidad por turno (Máquina + Día + Turno)
    complejidad = df.groupby(['Máquina', 'Fecha_Dia', 'Turno'])['Refs_Fila'].apply(
        lambda x: len(set().union(*x))
    ).reset_index()
    complejidad.columns = ['Máquina', 'Fecha_Dia', 'Turno', 'Cant_Refs']
    
    return df.merge(complejidad, on=['Máquina', 'Fecha_Dia', 'Turno'])

# --- INTERFAZ STREAMLIT (LAYOUT SIMPLIFICADO) ---
st.title("📄 FAMMA | Reporte de Cadencia")
st.write("Herramienta automatizada para el cálculo de piezas por hora.")

# Paso 1: Link
url_input = st.text_input("1. Ingrese el link de Google Sheets", placeholder="https://docs.google.com/spreadsheets/d/...")

if url_input:
    try:
        with st.spinner('Analizando datos de la nube...'):
            df_final = procesar_google_sheets(url_input)
        
        if df_final is not None:
            # Paso 2: Selección de Máquinas
            maqs_disponibles = sorted(df_final['Máquina'].unique())
            sel_maqs = st.multiselect("2. Seleccione las Máquinas", maqs_disponibles)
            
            if sel_maqs:
                # Paso 3: Cálculo y Generación
                st.write("---")
                
                resumenes = {}
                for m in sel_maqs:
                    res = df_final[df_final['Máquina'] == m].groupby('Cant_Refs').agg({
                        'Tiempo_Hs': 'sum',
                        'Buenas': 'sum'
                    }).reset_index()
                    # Cadencia: Piezas / Horas
                    res['Pzas_Por_Hora'] = np.where(res['Tiempo_Hs'] > 0, res['Buenas'] / res['Tiempo_Hs'], 0)
                    resumenes[m] = res
                
                # Fechas para el reporte
                f_min = df_final['Fecha Inicio'].min().strftime('%d/%m/%Y')
                f_max = df_final['Fecha Inicio'].max().strftime('%d/%m/%Y')
                
                # Generar PDF en memoria
                pdf_bytes = generar_pdf(resumenes, f_min, f_max)
                
                # Botón de Descarga Centrado
                st.download_button(
                    label="📥 DESCARGAR REPORTE PDF",
                    data=pdf_bytes,
                    file_name=f"Reporte_FAMMA_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("Cálculos de cadencia realizados correctamente.")
        else:
            st.error("No se pudo extraer el ID del link proporcionado.")

    except Exception as e:
        st.error(f"Error de acceso: Asegúrese de que el archivo sea público y contenga las columnas requeridas.")
        st.info(f"Detalle técnico: {e}")
