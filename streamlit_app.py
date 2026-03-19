import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="FAMMA | Reporte de Eficiencia", page_icon="📊", layout="centered")

# Estilo visual simple para el layout
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #004286; color: white; font-weight: bold; }
    .stTextInput>div>div>input { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNCIÓN PARA GENERAR EL PDF
def generar_pdf(dict_resumenes, dict_productos, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Título Principal
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE PRODUCTIVIDAD: REAL VS ESTANDAR", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(10)

    for maquina in dict_resumenes.keys():
        # Encabezado de Máquina
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(40, 40, 40); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, f" MAQUINA: {maquina}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0); pdf.ln(2)

        # CUADRO 1: Resumen de Máquina (Por cantidad de referencias)
        pdf.set_font("Arial", 'B', 9)
        pdf.set_fill_color(235, 235, 235)
        pdf.cell(60, 8, "Escenario (Refs)", border=1, fill=True, align='C')
        pdf.cell(40, 8, "Tiempo (Hs)", border=1, fill=True, align='C')
        pdf.cell(40, 8, "Pzas Reales", border=1, fill=True, align='C')
        pdf.cell(50, 8, "Pzas/Hora Real", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        for _, row in dict_resumenes[maquina].iterrows():
            pdf.cell(60, 7, f"{int(row['Cant_Refs'])} Referencia(s) en Turno", border=1)
            pdf.cell(40, 7, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        pdf.ln(5)

        # CUADRO 2: Comparativa por Producto (Eficiencia vs Estándar)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 7, "Desglose de Eficiencia por Producto (Real vs TC):", ln=True)
        pdf.set_font("Arial", 'B', 8); pdf.set_fill_color(245, 245, 245)
        pdf.cell(40, 8, "Codigo", border=1, fill=True)
        pdf.cell(20, 8, "TC Est.", border=1, fill=True, align='C')
        pdf.cell(25, 8, "P/H Est.", border=1, fill=True, align='C')
        pdf.cell(25, 8, "P/H Real", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Efic. %", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Refs/T", border=1, fill=True, align='C')
        pdf.cell(30, 8, "Hs Prod", border=1, ln=True, fill=True, align='C')

        pdf.set_font("Arial", '', 7)
        df_prod = dict_productos[maquina]
        for _, row in df_prod.iterrows():
            # Cálculos de eficiencia para el PDF
            ph_est = (60 / row['TC_E']) if row['TC_E'] > 0 else 0
            eficiencia = (row['Pzas_Por_Hora'] / ph_est * 100) if ph_est > 0 else 0
            
            pdf.cell(40, 7, str(row['Producto 1'])[:20], border=1)
            pdf.cell(20, 7, f"{row['TC_E']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{ph_est:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{eficiencia:.1f}%", border=1, align='C')
            pdf.cell(25, 7, f"{int(row['Cant_Refs'])}", border=1, align='C')
            pdf.cell(30, 7, f"{row['Tiempo_Hs']:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO DE DATOS
def get_csv_url(u):
    mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
    gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
    return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"

# --- INTERFAZ STREAMLIT ---
st.title("📊 FAMMA | Eficiencia Real vs Estándar")
st.write("Sincronice sus eventos de producción con los tiempos de ciclo maestros.")

url_prod = st.text_input("1. Pegue el link de Producción (Eventos):")
url_std = st.text_input("2. Pegue el link de Estándares (TC):")

if url_prod and url_std:
    try:
        # Carga de datos desde Google Sheets
        df_real = pd.read_csv(get_csv_url(url_prod))
        df_std = pd.read_csv(get_csv_url(url_std))
        
        # Limpieza de encabezados
        df_real.columns = [c.strip() for c in df_real.columns]
        df_std.columns = [c.strip() for c in df_std.columns]
        
        # Unificar Máquinas (Celda 15A/B -> Celda 15)
        df_real['Máquina'] = df_real['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        df_std['Código Máquina'] = df_std['Código Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        
        # Filtrado de eventos de Producción y limpieza numérica
        df_real = df_real[df_real['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
        df_real['Fecha Inicio'] = pd.to_datetime(df_real['Fecha Inicio'], errors='coerce')
        df_real['Tiempo_Hs'] = pd.to_numeric(df_real['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_real['Buenas'] = pd.to_numeric(df_real['Buenas'], errors='coerce').fillna(0)

        # Cálculo de complejidad de turno (Cantidad de Referencias)
        def get_refs(r):
            return {str(r.get('Producto 1', '')), str(r.get('Producto 2', ''))} - {'nan', '', 'None'}
        
        df_real['Refs_Fila'] = df_real.apply(get_refs, axis=1)
        df_real['Fecha_D'] = df_real['Fecha Inicio'].dt.date
        
        comp = df_real.groupby(['Máquina', 'Fecha_D', 'Turno'])['Refs_Fila'].apply(lambda x: len(set().union(*x))).reset_index()
        comp.columns = ['Máquina', 'Fecha_D', 'Turno', 'Cant_Refs']
        
        # Forzar tipo de dato para evitar error de merge (int64 vs object)
        comp['Cant_Refs'] = comp['Cant_Refs'].astype(int)
        df_real = df_real.merge(comp, on=['Máquina', 'Fecha_D', 'Turno'])

        # Selección de Máquinas
        maqs = sorted(df_real['Máquina'].unique())
        sel_maqs = st.multiselect("Seleccione las Máquinas para el reporte:", maqs)

        if sel_maqs:
            dict_m = {}; dict_p = {}
            for m in sel_maqs:
                df_m = df_real[df_real['Máquina'] == m]
                
                # Resumen Máquina
                rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rm['Pzas_Por_Hora'] = np.where(rm['Tiempo_Hs'] > 0, rm['Buenas'] / rm['Tiempo_Hs'], 0)
                dict_m[m] = rm
                
                # Resumen Producto
                rp = df_m.groupby(['Producto 1', 'Cant_Refs']).agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rp['Pzas_Por_Hora'] = np.where(rp['Tiempo_Hs'] > 0, rp['Buenas'] / rp['Tiempo_Hs'], 0)
                
                # Cruce con Estándares (Limpieza de Tiempo Ciclo)
                std_clean = df_std[['Código Producto', 'Tiempo Ciclo']].copy()
                std_clean['TC_E'] = pd.to_numeric(std_clean['Tiempo Ciclo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                
                # Unir por código de producto para traer el estándar (TC)
                rp = rp.merge(std_clean[['Código Producto', 'TC_E']], left_on='Producto 1', right_on='Código Producto', how='left')
                rp['TC_E'] = rp['TC_E'].fillna(0)
                
                dict_p[m] = rp.sort_values(['Producto 1', 'Cant_Refs'])

            # Botón Final
            st.write("---")
            f_ini = df_real['Fecha Inicio'].min().strftime('%d/%m/%Y')
            f_fin = df_real['Fecha Inicio'].max().strftime('%d/%m/%Y')
            
            pdf_data = generar_pdf(dict_m, dict_p, f_ini, f_fin)
            st.download_button(
                label="📥 DESCARGAR REPORTE PDF FINAL",
                data=pdf_data,
                file_name=f"Reporte_Eficiencia_FAMMA.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.success("Sincronización completa. El PDF incluye los desgloses por máquina y eficiencia por producto.")

    except Exception as e:
        st.error(f"Error detectado: {e}")
