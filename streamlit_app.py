import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Reporte Operativo FAMMA", page_icon="📊", layout="centered")

# Estilo visual para los botones
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #004286; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. CLASE PDF CON SALTO DE PÁGINA POR CELDA
class ReportePDF(FPDF):
    def header(self):
        if self.page_no() > 0:
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.cell(0, 10, 'FAMMA - Reporte de Eficiencia por Referencia', 0, 0, 'R')
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def generar_pdf(dict_resumenes, dict_productos, f_inicio, f_fin):
    pdf = ReportePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for maquina in dict_resumenes.keys():
        # REGLA: Cada celda inicia en una hoja nueva
        pdf.add_page()
        
        # Título de la Celda
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(0, 66, 134)
        pdf.cell(190, 10, f"CELDA DE PRODUCCION: {maquina}", ln=True, align='L')
        
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0)
        pdf.cell(190, 8, f"Rango de Analisis: {f_inicio} al {f_fin}", ln=True)
        pdf.ln(5)

        # CUADRO 1: RESUMEN GENERAL DE LA CELDA
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, "1. Resumen de Velocidad por Complejidad de Turno", ln=True)
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(60, 9, "Combinacion de Refs", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Horas Totales", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Piezas Reales", border=1, fill=True, align='C')
        pdf.cell(50, 9, "Pza / Hora Real", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        df_res = dict_resumenes[maquina]
        for _, row in df_res.iterrows():
            pdf.cell(60, 8, f"{int(row['Cant_Refs'])} Producto(s) en Turno", border=1)
            pdf.cell(40, 8, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 8, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 8, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        
        pdf.ln(10)

        # CUADRO 2: TABLA DETALLADA PRODUCTO POR PRODUCTO
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, f"2. Desglose Detallado de todas las Referencias en {maquina}", ln=True)
        pdf.set_fill_color(0, 66, 134); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 8)
        
        # Encabezados de la tabla de productos
        pdf.cell(45, 9, "Codigo Producto", border=1, fill=True, align='C')
        pdf.cell(20, 9, "TC Est.", border=1, fill=True, align='C')
        pdf.cell(25, 9, "P/H Est.", border=1, fill=True, align='C')
        pdf.cell(25, 9, "P/H Real", border=1, fill=True, align='C')
        pdf.cell(20, 9, "Efic. %", border=1, fill=True, align='C')
        pdf.cell(20, 9, "Refs/T", border=1, fill=True, align='C')
        pdf.cell(35, 9, "Piezas Fabricadas", border=1, ln=True, fill=True, align='C')

        pdf.set_font("Arial", '', 7); pdf.set_text_color(0)
        df_prod = dict_productos[maquina]
        
        # Aquí se listan TODAS las referencias de la celda
        for _, row in df_prod.iterrows():
            ph_est = (60 / row['TC_E']) if row['TC_E'] > 0 else 0
            eficiencia = (row['Pzas_Por_Hora'] / ph_est * 100) if ph_est > 0 else 0
            
            pdf.cell(45, 7, str(row['Producto 1'])[:22], border=1)
            pdf.cell(20, 7, f"{row['TC_E']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{ph_est:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, align='C')
            pdf.cell(20, 7, f"{eficiencia:.1f}%", border=1, align='C')
            pdf.cell(20, 7, f"{int(row['Cant_Refs'])}", border=1, align='C')
            pdf.cell(35, 7, f"{int(row['Buenas'])}", border=1, ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO DE GOOGLE SHEETS
def get_csv_url(u):
    mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
    gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
    return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"

# --- INTERFAZ STREAMLIT ---
st.title("📄 Reporte por Celda y Referencia")
st.write("Carga los datos para generar el PDF con saltos de pagina por maquina.")

url_prod = st.text_input("1. Enlace de Eventos (Pestana Datos):")
url_std = st.text_input("2. Enlace de Estandares (Pestana Tiempos):")

if url_prod and url_std:
    try:
        # Carga
        df_p = pd.read_csv(get_csv_url(url_prod))
        df_s = pd.read_csv(get_csv_url(url_std))
        
        df_p.columns = [c.strip() for c in df_p.columns]
        df_s.columns = [c.strip() for c in df_s.columns]
        
        # Unificar Celda 15
        df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        df_s['Código Máquina'] = df_s['Código Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        
        # Filtrar Produccion y limpiar
        df_p = df_p[df_p['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
        df_p['Fecha Inicio'] = pd.to_datetime(df_p['Fecha Inicio'], errors='coerce')
        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

        # Calculo de Cant_Refs (Complejidad)
        def get_refs(r):
            return {str(r.get('Producto 1', '')), str(r.get('Producto 2', ''))} - {'nan', '', 'None'}
        df_p['Refs_Fila'] = df_p.apply(get_refs, axis=1)
        df_p['Fecha_D'] = df_p['Fecha Inicio'].dt.date
        
        comp = df_p.groupby(['Máquina', 'Fecha_D', 'Turno'])['Refs_Fila'].apply(lambda x: len(set().union(*x))).reset_index()
        comp.columns = ['Máquina', 'Fecha_D', 'Turno', 'Cant_Refs']
        comp['Cant_Refs'] = comp['Cant_Refs'].astype(int)
        df_p = df_p.merge(comp, on=['Máquina', 'Fecha_D', 'Turno'])

        # Seleccion
        maqs = sorted(df_p['Máquina'].unique())
        sel_maqs = st.multiselect("Seleccione las Maquinas para el reporte:", maqs)

        if sel_maqs:
            dict_m = {}; dict_p = {}
            for m in sel_maqs:
                df_m = df_p[df_p['Máquina'] == m]
                
                # Resumen Maquina
                rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rm['Pzas_Por_Hora'] = np.where(rm['Tiempo_Hs'] > 0, rm['Buenas'] / rm['Tiempo_Hs'], 0)
                dict_m[m] = rm
                
                # Desglose Producto (Aqui se listan todas las refs de la Celda 3, por ejemplo)
                rp = df_m.groupby(['Producto 1', 'Cant_Refs']).agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rp['Pzas_Por_Hora'] = np.where(rp['Tiempo_Hs'] > 0, rp['Buenas'] / rp['Tiempo_Hs'], 0)
                
                # Cruce con TC
                std_c = df_s[['Código Producto', 'Tiempo Ciclo']].copy()
                std_c['TC_E'] = pd.to_numeric(std_c['Tiempo Ciclo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                rp = rp.merge(std_c[['Código Producto', 'TC_E']], left_on='Producto 1', right_on='Código Producto', how='left')
                
                dict_p[m] = rp.fillna(0).sort_values(['Producto 1', 'Cant_Refs'])

            st.divider()
            f_i = df_p['Fecha Inicio'].min().strftime('%d/%m/%Y')
            f_f = df_p['Fecha Inicio'].max().strftime('%d/%m/%Y')
            
            pdf_data = generar_pdf(dict_m, dict_p, f_i, f_f)
            st.download_button("📥 DESCARGAR REPORTE PDF (POR HOJAS)", pdf_data, "Reporte_FAMMA_Final.pdf", use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
