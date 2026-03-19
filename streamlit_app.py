import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="FAMMA | Productividad Simultánea", layout="wide")

class ReportePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 8)
        self.set_text_color(150)
        self.cell(0, 10, 'FAMMA - Reporte de Cadencias por Referencias Simultáneas', 0, 0, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf(dict_maquinas, dict_detalles, f_ini, f_fin):
    pdf = ReportePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for maq in dict_maquinas.keys():
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(190, 10, f"ANÁLISIS DE MÁQUINA: {maq}", ln=True)
        pdf.set_font("Arial", '', 9)
        pdf.cell(190, 5, f"Periodo: {f_ini} - {f_fin}", ln=True)
        pdf.ln(5)

        # TABLA 1: TOTALES POR MÁQUINA SEGÚN SIMULTANEIDAD
        pdf.set_font("Arial", 'B', 10); pdf.cell(190, 7, "1. Rendimiento Global de la Máquina", ln=True)
        pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 8)
        pdf.cell(50, 8, "Escenario (Simultáneos)", 1, 0, 'C', True)
        pdf.cell(45, 8, "Tiempo Total (Hs)", 1, 0, 'C', True)
        pdf.cell(45, 8, "Piezas Totales", 1, 0, 'C', True)
        pdf.cell(50, 8, "Cadencia Máquina (P/H)", 1, 1, 'C', True)

        pdf.set_font("Arial", '', 8)
        for _, r in dict_maquinas[maq].iterrows():
            pdf.cell(50, 7, f"{int(r['Cant_Refs'])} Referencia(s)", 1, 0, 'C')
            pdf.cell(45, 7, f"{r['Tiempo_Hs']:.2f}", 1, 0, 'C')
            pdf.cell(45, 7, f"{int(r['Buenas'])}", 1, 0, 'C')
            pdf.cell(50, 7, f"{r['Cadencia_Maq']:.2f}", 1, 1, 'C')
        pdf.ln(8)

        # TABLA 2: CADENCIA POR PRODUCTO SEGÚN ESCENARIO
        pdf.set_font("Arial", 'B', 10); pdf.cell(190, 7, "2. Cadencia por Producto según simultaneidad", ln=True)
        pdf.set_fill_color(0, 51, 102); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(45, 8, "Producto", 1, 0, 'C', True)
        pdf.cell(20, 8, "Simult.", 1, 0, 'C', True)
        pdf.cell(25, 8, "Hs Proporc.", 1, 0, 'C', True)
        pdf.cell(25, 8, "Pzas", 1, 0, 'C', True)
        pdf.cell(25, 8, "Cadencia P/H", 1, 0, 'C', True)
        pdf.cell(20, 8, "TC Est.", 1, 0, 'C', True)
        pdf.cell(30, 8, "Efic. Real", 1, 1, 'C', True)

        pdf.set_text_color(0); pdf.set_font("Arial", '', 7)
        for _, r in dict_detalles[maq].iterrows():
            pdf.cell(45, 7, str(r['Producto'])[:22], 1)
            pdf.cell(20, 7, str(int(r['Cant_Refs'])), 1, 0, 'C')
            pdf.cell(25, 7, f"{r['Tiempo_Proporcional']:.2f}", 1, 0, 'C')
            pdf.cell(25, 7, str(int(r['Buenas'])), 1, 0, 'C')
            pdf.cell(25, 7, f"{r['Cadencia_Individual']:.2f}", 1, 0, 'C')
            pdf.cell(20, 7, f"{r['TC_E']:.2f}", 1, 0, 'C')
            pdf.cell(30, 7, f"{r['Efic']:.1f}%", 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. LÓGICA DE PROCESAMIENTO
def get_csv_url(u):
    mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
    return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv"

st.title("📊 FAMMA: Análisis de Cadencia Simultánea")

u_prod = st.text_input("Link Producción:")
u_std = st.text_input("Link Estándares:")

if u_prod and u_std:
    try:
        df_p = pd.read_csv(get_csv_url(u_prod))
        df_s = pd.read_csv(get_csv_url(u_std))
        
        df_p.columns = [c.strip() for c in df_p.columns]
        df_s.columns = [c.strip() for c in df_s.columns]

        # Unificar Celda 15
        df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        
        # Limpieza de datos
        df_p = df_p[df_p['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)
        df_p['Fecha_D'] = pd.to_datetime(df_p['Fecha Inicio']).dt.date

        # Determinar simultaneidad por Turno
        def obtener_lista_productos(fila):
            return [str(fila[p]).strip() for p in ['Producto 1', 'Producto 2'] if pd.notnull(fila[p]) and str(fila[p]).lower() not in ['nan','','none']]

        df_p['Prod_List'] = df_p.apply(obtener_lista_productos, axis=1)
        
        # Cantidad de referencias distintas en el turno (Escenario)
        complejidad = df_p.groupby(['Máquina', 'Fecha_D', 'Turno'])['Prod_List'].apply(lambda x: len(set([p for sub in x for p in sub]))).reset_index()
        complejidad.columns = ['Máquina', 'Fecha_D', 'Turno', 'Cant_Refs']
        df_p = df_p.merge(complejidad, on=['Máquina', 'Fecha_D', 'Turno'])

        # --- CÁLCULO DE PRORRATEO ---
        # Si una fila tiene 2 productos, cada uno consume la mitad del tiempo de esa fila
        df_p['Tiempo_Prorrateado'] = df_p['Tiempo_Hs'] / df_p['Prod_List'].apply(lambda x: len(x) if len(x) > 0 else 1)

        maqs = sorted(df_p['Máquina'].unique())
        sel = st.multiselect("Seleccione Máquinas:", maqs)

        if sel:
            d_maq = {}; d_det = {}
            for m in sel:
                df_m = df_p[df_p['Máquina'] == m]
                
                # 1. Agrupación por Máquina y Escenario
                res_m = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs':'sum', 'Buenas':'sum'}).reset_index()
                res_m['Cadencia_Maq'] = res_m['Buenas'] / res_m['Tiempo_Hs']
                d_maq[m] = res_m
                
                # 2. Agrupación por Producto y Escenario
                expandido = []
                for _, fila in df_m.iterrows():
                    for p in fila['Prod_List']:
                        expandido.append({
                            'Producto': p, 
                            'Cant_Refs': fila['Cant_Refs'], 
                            'Tiempo_Proporcional': fila['Tiempo_Prorrateado'], 
                            'Buenas': fila['Buenas']
                        })
                
                df_exp = pd.DataFrame(expandido)
                res_p = df_exp.groupby(['Producto', 'Cant_Refs']).agg({'Tiempo_Proporcional':'sum', 'Buenas':'sum'}).reset_index()
                res_p['Cad
