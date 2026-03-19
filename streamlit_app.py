El error que estás viendo es muy común: ocurre porque el sistema intenta leer la fecha asumiendo que el mes va primero (formato de EE. UU. %m/%d/%Y), pero tus datos tienen el día primero (13/01/2026). Como no existe el mes 13, el código se detiene.

Para solucionarlo de forma definitiva en tu script, vamos a modificar la línea donde se convierten las fechas usando el argumento dayfirst=True.

El Código Corregido
Busca la sección de Procesamiento y reemplaza la línea de conversión de Fecha Inicio por esta:

Python
# Reemplaza la línea vieja por esta:
df_p['Fecha Inicio'] = pd.to_datetime(df_p['Fecha Inicio'], dayfirst=True, errors='coerce')
Código Completo (Actualizado con la corrección de fecha)
Aquí tienes el bloque completo para que simplemente copies y pegues. He aplicado el cambio en la línea 105 aproximadamente:

Python
import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="FAMMA | Reporte de Cadencia", page_icon="📊", layout="centered")

# Estilo visual
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #004286; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. CLASE PDF CON PAGINACIÓN
class ReportePDF(FPDF):
    def header(self):
        if self.page_no() > 0:
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.cell(0, 10, 'FAMMA - Reporte de Cadencia y Eficiencia Real', 0, 0, 'R')
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
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(0, 66, 134)
        pdf.cell(190, 10, f"REPORTE CELDA: {maquina}", ln=True, align='L')
        pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
        pdf.cell(190, 8, f"Rango: {f_inicio} al {f_fin}", ln=True)
        pdf.ln(5)

        # TABLA 1: RESUMEN GLOBAL
        pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "1. Rendimiento Global de la Celda", ln=True)
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        pdf.cell(60, 9, "Escenario Turno", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Horas Totales", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Pzas Totales", border=1, fill=True, align='C')
        pdf.cell(50, 9, "Cadencia (P/H)", border=1, ln=True, fill=True, align='C')
        pdf.set_font("Arial", '', 9)
        for _, row in dict_resumenes[maquina].iterrows():
            pdf.cell(60, 8, f"{int(row['Cant_Refs'])} Referencia(s)", border=1)
            pdf.cell(40, 8, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 8, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 8, f"{row['Cadencia_Maq']:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

        # TABLA 2: DETALLE POR PRODUCTO
        pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "2. Desglose de Cadencia Individual por Producto", ln=True)
        pdf.set_fill_color(0, 66, 134); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(45, 9, "Producto", border=1, fill=True, align='C')
        pdf.cell(20, 9, "Refs/T", border=1, fill=True, align='C')
        pdf.cell(25, 9, "Hs Prop.", border=1, fill=True, align='C')
        pdf.cell(25, 9, "Pzas", border=1, fill=True, align='C')
        pdf.cell(25, 9, "Real P/H", border=1, fill=True, align='C')
        pdf.cell(25, 9, "Est. P/H", border=1, fill=True, align='C')
        pdf.cell(25, 9, "Eficiencia", border=1, ln=True, fill=True, align='C')
        pdf.set_font("Arial", '', 7); pdf.set_text_color(0)
        df_prod = dict_productos[maquina]
        for _, row in df_prod.iterrows():
            pdf.cell(45, 7, str(row['Producto'])[:22], border=1)
            pdf.cell(20, 7, f"{int(row['Cant_Refs'])}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Tiempo_Proporcional']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Cadencia_Individual']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['PH_E']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Efic']:.1f}%", border=1, ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO
def get_csv_url(u):
    mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
    gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
    return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"

st.title("📊 FAMMA | Analizador de Cadencia")
u_prod = st.text_input("1. Link de Producción (Eventos):")
u_std = st.text_input("2. Link de Estándares (Tiempos de Ciclo):")

if u_prod and u_std:
    try:
        df_p = pd.read_csv(get_csv_url(u_prod))
        df_s = pd.read_csv(get_csv_url(u_std))
        df_p.columns = [c.strip() for c in df_p.columns]
        df_s.columns = [c.strip() for c in df_s.columns]

        df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        df_s['Código Máquina'] = df_s['Código Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        
        df_p = df_p[df_p['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
        
        # --- CORRECCIÓN CLAVE AQUÍ ---
        df_p['Fecha Inicio'] = pd.to_datetime(df_p['Fecha Inicio'], dayfirst=True, errors='coerce')
        # -----------------------------

        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)
        df_p['Fecha_D'] = df_p['Fecha Inicio'].dt.date

        def get_refs_fila(r):
            return [str(r.get(p)).strip() for p in ['Producto 1', 'Producto 2'] if pd.notnull(r.get(p)) and str(r.get(p)).lower() not in ['nan','','none']]
        
        df_p['Prod_List'] = df_p.apply(get_refs_fila, axis=1)
        comp = df_p.groupby(['Máquina', 'Fecha_D', 'Turno'])['Prod_List'].apply(lambda x: len(set([p for sub in x for p in sub]))).reset_index()
        comp.columns = ['Máquina', 'Fecha_D', 'Turno', 'Cant_Refs']
        df_p = df_p.merge(comp, on=['Máquina', 'Fecha_D', 'Turno'])
        df_p['Tiempo_Prorrateado'] = df_p['Tiempo_Hs'] / df_p['Prod_List'].apply(lambda x: len(x) if len(x) > 0 else 1)

        maqs = sorted(df_p['Máquina'].unique())
        sel = st.multiselect("Seleccione Máquinas:", maqs)

        if sel:
            dict_m = {}; dict_p = {}
            for m in sel:
                df_m = df_p[df_p['Máquina'] == m]
                rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs':'sum', 'Buenas':'sum'}).reset_index()
                rm['Cadencia_Maq'] = rm['Buenas'] / rm['Tiempo_Hs']
                dict_m[m] = rm
                
                expandido = []
                for _, fila in df_m.iterrows():
                    for p in fila['Prod_List']:
                        expandido.append({'Producto': p, 'Cant_Refs': fila['Cant_Refs'], 'Tiempo_Proporcional': fila['Tiempo_Prorrateado'], 'Buenas': fila['Buenas']})
                
                if expandido:
                    df_exp = pd.DataFrame(expandido)
                    rp = df_exp.groupby(['Producto', 'Cant_Refs']).agg({'Tiempo_Proporcional':'sum', 'Buenas':'sum'}).reset_index()
                    rp['Cadencia_Individual'] = rp['Buenas'] / rp['Tiempo_Proporcional']
                    std_c = df_s[['Código Producto', 'Tiempo Ciclo']].copy()
                    std_c['TC_E'] = pd.to_numeric(std_c['Tiempo Ciclo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                    rp = rp.merge(std_c, left_on='Producto', right_on='Código Producto', how='left')
                    rp['PH_E'] = np.where(rp['TC_E'] > 0, 60 / rp['TC_E'], 0)
                    rp['Efic'] = np.where(rp['PH_E'] > 0, (rp['Cadencia_Individual'] / rp['PH_E']) * 100, 0)
                    dict_p[m] = rp.fillna(0).sort_values(['Producto', 'Cant_Refs'])

            st.divider()
            f_i = df_p['Fecha Inicio'].min().strftime('%d/%m/%Y')
            f_f = df_p['Fecha Inicio'].max().strftime('%d/%m/%Y')
            st.download_button("📥 DESCARGAR REPORTE PDF", generar_pdf(dict_m, dict_p, f_i, f_f), "Reporte_FAMMA.pdf", use_container_width=True)

    except Exception as e:
        st.error(f"Error técnico: {e}")
