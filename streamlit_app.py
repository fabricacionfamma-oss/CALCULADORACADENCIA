import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="FAMMA | Reporte de Cadencia", page_icon="📄")

# 2. ESTILO SIMPLIFICADO (CSS)
st.markdown("""
    <style>
    .main { text-align: center; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNCIÓN PARA GENERAR EL PDF
def generar_pdf(dict_resumenes, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Título Principal
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE CADENCIA Y PRODUCTIVIDAD", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(10)

    for maquina, df_res in dict_resumenes.items():
        # Encabezado de Máquina
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, f" MAQUINA: {maquina}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0); pdf.ln(2)

        # Tabla de Datos
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(60, 10, "Cant. Referencias", border=1, fill=True, align='C')
        pdf.cell(40, 10, "Tiempo (Hs)", border=1, fill=True, align='C')
        pdf.cell(40, 10, "Piezas Buenas", border=1, fill=True, align='C')
        pdf.cell(50, 10, "Piezas / Hora", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 10)
        for _, row in df_res.iterrows():
            pdf.cell(60, 9, f"{int(row['Cant_Refs'])} Ref(s) en Turno", border=1)
            pdf.cell(40, 9, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 9, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 9, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 4. PROCESAMIENTO DE DATOS
def procesar_datos(url):
    # Extraer link de exportación
    sheet_id = re.search(r'd/([a-zA-Z0-9-_]+)', url).group(1)
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    df = pd.read_csv(csv_url)
    df.columns = [c.strip() for c in df.columns]
    
    # Unificar Celda 15
    df['Máquina'] = df['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
    
    # Filtrar solo Producción
    df = df[df['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
    
    # Conversiones
    df['Fecha Inicio'] = pd.to_datetime(df['Fecha Inicio'], errors='coerce')
    df['Tiempo_Hs'] = pd.to_numeric(df['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
    df['Buenas'] = pd.to_numeric(df['Buenas'], errors='coerce').fillna(0)
    
    # Contar Referencias por fila y luego por turno
    def count_refs(r):
        p = {str(r.get('Producto 1')), str(r.get('Producto 2'))}
        return {x for x in p if x.lower() not in ['nan', '', 'none']}
    
    df['Refs_Fila'] = df.apply(count_refs, axis=1)
    df['Fecha_Dia'] = df['Fecha Inicio'].dt.date
    
    # Complejidad del turno
    comp = df.groupby(['Máquina', 'Fecha_Dia', 'Turno'])['Refs_Fila'].apply(lambda x: len(set().union(*x))).reset_index()
    comp.columns = ['Máquina', 'Fecha_Dia', 'Turno', 'Cant_Refs']
    
    return df.merge(comp, on=['Máquina', 'Fecha_Dia', 'Turno'])

# --- INTERFAZ STREAMLIT ---
st.title("📄 Exportador de Cadencia FAMMA")
st.write("Configuración rápida para reportes en PDF")

url_input = st.text_input("1. Pegue el link de Google Sheets", placeholder="https://docs.google.com/spreadsheets/d/...")

if url_input:
    try:
        df_final = procesar_datos(url_input)
        
        # Selección de Máquinas
        maqs_disponibles = sorted(df_final['Máquina'].unique())
        sel_maqs = st.multiselect("2. Seleccione las Máquinas", maqs_disponibles)
        
        if sel_maqs:
            # Cálculos finales
            resumenes = {}
            for m in sel_maqs:
                res = df_final[df_final['Máquina'] == m].groupby('Cant_Refs').agg({
                    'Tiempo_Hs': 'sum',
                    'Buenas': 'sum'
                }).reset_index()
                res['Pzas_Por_Hora'] = np.where(res['Tiempo_Hs'] > 0, res['Buenas'] / res['Tiempo_Hs'], 0)
                resumenes[m] = res
            
            # Botón de Descarga
            st.write("---")
            f_ini = df_final['Fecha Inicio'].min().strftime('%d/%m/%Y')
            f_fin = df_final['Fecha Inicio'].max().strftime('%d/%m/%Y')
            
            pdf_bytes = generar_pdf(resumenes, f_ini, f_fin)
            
            st.download_button(
                label="📥 GENERAR Y DESCARGAR PDF",
                data=pdf_bytes,
                file_name=f"Reporte_FAMMA_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
            st.success("Reporte listo para descargar.")

    except Exception as e:
        st.error(f"Error: Verifique que el link sea público y las columnas correctas.")
