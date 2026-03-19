import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="FAMMA | Reporte de Eficiencia Real", layout="centered")

# 2. CLASE PDF CON PAGINACIÓN
class ReportePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 8)
        self.set_text_color(150)
        self.cell(0, 10, 'FAMMA - Sistema de Control de Productividad', 0, 0, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf(dict_resumenes, dict_productos, f_inicio, f_fin):
    pdf = ReportePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for maquina in dict_resumenes.keys():
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(0, 66, 134)
        pdf.cell(190, 10, f"REPORTE CELDA: {maquina}", ln=True)
        
        pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
        pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True)
        pdf.ln(5)

        # TABLA 1: RESUMEN ESCENARIOS
        pdf.set_font("Arial", 'B', 10); pdf.cell(190, 8, "1. Rendimiento por Escenario de Carga", ln=True)
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        pdf.cell(60, 9, "Complejidad", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Horas Turno", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Pzas Totales", border=1, fill=True, align='C')
        pdf.cell(50, 9, "Cadencia Real (P/H)", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        for _, row in dict_resumenes[maquina].iterrows():
            pdf.cell(60, 8, f"{int(row['Cant_Refs'])} Ref(s) simultaneas", border=1)
            pdf.cell(40, 8, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 8, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 8, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

        # TABLA 2: DETALLE POR PRODUCTO (CON TIEMPO PRORRATEADO)
        pdf.set_font("Arial", 'B', 10); pdf.cell(190, 8, "2. Analisis por Referencia (Tiempo Prorrateado)", ln=True)
        pdf.set_fill_color(0, 66, 134); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(45, 9, "Codigo", border=1, fill=True, align='C')
        pdf.cell(20, 9, "TC Est.", border=1, fill=True, align='C')
        pdf.cell(25, 9, "P/H Est.", border=1, fill=True, align='C')
        pdf.cell(25, 9, "P/H Real", border=1, fill=True, align='C')
        pdf.cell(20, 9, "Efic. %", border=1, fill=True, align='C')
        pdf.cell(20, 9, "Refs/T", border=1, fill=True, align='C')
        pdf.cell(35, 9, "Pzas", border=1, ln=True, fill=True, align='C')

        pdf.set_font("Arial", '', 7); pdf.set_text_color(0)
        for _, row in dict_productos[maquina].iterrows():
            pdf.cell(45, 7, str(row['Producto'])[:22], border=1)
            pdf.cell(20, 7, f"{row['TC_E']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['PH_E']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Pzas_Real_Adj']:.2f}", border=1, align='C')
            pdf.cell(20, 7, f"{row['Efic_Adj']:.1f}%", border=1, align='C')
            pdf.cell(20, 7, f"{int(row['Cant_Refs'])}", border=1, align='C')
            pdf.cell(35, 7, f"{int(row['Buenas'])}", border=1, ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO
def get_csv_url(u):
    mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
    return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv"

# --- INTERFAZ ---
st.title("📊 Correccion de Eficiencia Multireferencia")

u_p = st.text_input("Link Produccion:")
u_s = st.text_input("Link Estandares:")

if u_p and u_s:
    try:
        df_p = pd.read_csv(get_csv_url(u_p))
        df_s = pd.read_csv(get_csv_url(u_s))
        df_p.columns = [c.strip() for c in df_p.columns]
        df_s.columns = [c.strip() for c in df_s.columns]
        
        # Unificar Celda 15
        df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        df_s['Código Máquina'] = df_s['Código Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        
        # Limpieza
        df_p = df_p[df_p['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

        # Complejidad por Turno
        def get_refs_list(r):
            return [str(r.get('Producto 1', '')), str(r.get('Producto 2', ''))]
        
        df_p['Lista_Refs'] = df_p.apply(lambda r: [x for x in get_refs_list(r) if str(x).lower() not in ['nan','','none']], axis=1)
        df_p['Fecha_D'] = pd.to_datetime(df_p['Fecha Inicio']).dt.date
        
        comp = df_p.groupby(['Máquina', 'Fecha_D', 'Turno'])['Lista_Refs'].apply(lambda x: len(set([item for sublist in x for item in sublist]))).reset_index()
        comp.columns = ['Máquina', 'Fecha_D', 'Turno', 'Cant_Refs']
        df_p = df_p.merge(comp, on=['Máquina', 'Fecha_D', 'Turno'])

        # --- LÓGICA DE PRORRATEO ---
        # Si un evento tiene 2 productos, cada uno se lleva el 50% del tiempo del evento para el calculo individual
        df_p['Tiempo_Adj'] = df_p['Tiempo_Hs'] / df_p['Lista_Refs'].apply(lambda x: len(x) if len(x) > 0 else 1)

        maqs = sorted(df_p['Máquina'].unique())
        sel = st.multiselect("Seleccionar Maquinas:", maqs)

        if sel:
            dict_m = {}; dict_p = {}
            for m in sel:
                df_m = df_p[df_p['Máquina'] == m]
                
                # Resumen Maquina (Tiempo real de ocupacion de la celda)
                rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rm['Pzas_Por_Hora'] = rm['Buenas'] / rm['Tiempo_Hs']
                dict_m[m] = rm
                
                # Resumen Producto (Expandir si hay Producto 1 y 2 en la misma fila)
                rows = []
                for _, row in df_m.iterrows():
                    for prod in row['Lista_Refs']:
                        rows.append({'Producto': prod, 'Cant_Refs': row['Cant_Refs'], 'Buenas': row['Buenas'], 'Tiempo_Adj': row['Tiempo_Adj']})
                
                df_expand = pd.DataFrame(rows)
                rp = df_expand.groupby(['Producto', 'Cant_Refs']).agg({'Tiempo_Adj': 'sum', 'Buenas': 'sum'}).reset_index()
                
                # Cruce Estandares
                std_c = df_s[['Código Producto', 'Tiempo Ciclo']].copy()
                std_c['TC_E'] = pd.to_numeric(std_c['Tiempo Ciclo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                
                rp = rp.merge(std_c, left_on='Producto', right_on='Código Producto', how='left')
                rp['PH_E'] = np.where(rp['TC_E'] > 0, 60 / rp['TC_E'], 0)
                rp['Pzas_Real_Adj'] = rp['Buenas'] / rp['Tiempo_Adj']
                rp['Efic_Adj'] = np.where(rp['PH_E'] > 0, (rp['Pzas_Real_Adj'] / rp['PH_E']) * 100, 0)
                
                dict_p[m] = rp.sort_values(['Producto', 'Cant_Refs'])

            st.download_button("Descargar PDF Corregido", generar_pdf(dict_m, dict_p, "Inicio", "Fin"), "Reporte_Famma_OK.pdf")

    except Exception as e:
        st.error(f"Error: {e}")
