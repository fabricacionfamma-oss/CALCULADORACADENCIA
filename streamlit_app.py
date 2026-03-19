import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="FAMMA | Reporte de Precisión Final", layout="centered")

class ReportePDF(FPDF):
    def header(self):
        if self.page_no() > 0:
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.cell(0, 10, 'FAMMA - Reporte de Cadencia (Lógica por Fila)', 0, 0, 'R')
            self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
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

        # TABLA 1: RESUMEN (Ahora debe coincidir con tu filtro manual)
        pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "1. Rendimiento por Escenario (Suma de Filas)", ln=True)
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        pdf.cell(60, 9, "Cant. Referencias", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Horas Totales", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Pzas Totales", border=1, fill=True, align='C')
        pdf.cell(50, 9, "Piezas / Hora", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        for _, row in dict_resumenes[maquina].iterrows():
            pdf.cell(60, 8, f"{int(row['Cant_Refs'])} Referencia(s)", border=1)
            pdf.cell(40, 8, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 8, f"{int(row['Buenas'])}", border=1, align='C')
            cad = row['Buenas'] / row['Tiempo_Hs'] if row['Tiempo_Hs'] > 0 else 0
            pdf.cell(50, 8, f"{cad:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

        # TABLA 2: DETALLE PRODUCTO
        pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "2. Detalle por Referencia", ln=True)
        pdf.set_fill_color(0, 66, 134); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(45, 9, "Producto", 1, 0, 'C', True)
        pdf.cell(20, 9, "Refs/F", 1, 0, 'C', True)
        pdf.cell(25, 9, "Hs Prop.", 1, 0, 'C', True)
        pdf.cell(25, 9, "Pzas", 1, 0, 'C', True)
        pdf.cell(25, 9, "Real P/H", 1, 0, 'C', True)
        pdf.cell(25, 9, "Est. P/H", 1, 0, 'C', True)
        pdf.cell(25, 9, "Efic.", 1, 1, 'C', True)
        pdf.set_font("Arial", '', 7); pdf.set_text_color(0)
        df_prod = dict_productos[maquina]
        for _, row in df_prod.iterrows():
            pdf.cell(45, 7, str(row['Producto'])[:22], 1)
            pdf.cell(20, 7, f"{int(row['Cant_Refs'])}", 1, 0, 'C')
            pdf.cell(25, 7, f"{row['Tiempo_Proporcional']:.2f}", 1, 0, 'C')
            pdf.cell(25, 7, f"{int(row['Buenas'])}", 1, 0, 'C')
            pdf.cell(25, 7, f"{row['Cadencia_Individual']:.2f}", 1, 0, 'C')
            pdf.cell(25, 7, f"{row['PH_E']:.2f}", 1, 0, 'C')
            pdf.cell(25, 7, f"{row['Efic']:.1f}%", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO
def get_csv_url(u):
    mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
    gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
    return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"

st.title("📊 FAMMA | Analizador de Precisión")

u_p = st.text_input("1. Link de Producción (Eventos):")
u_s = st.text_input("2. Link de Estándares (TC):")

if u_p and u_s:
    try:
        df_p = pd.read_csv(get_csv_url(u_p))
        df_s = pd.read_csv(get_csv_url(u_s))
        df_p.columns = [c.strip() for c in df_p.columns]
        df_s.columns = [c.strip() for c in df_s.columns]

        df_p = df_p[df_p['Nivel 1'].str.contains('Producción|Produccion', na=False, case=False)].copy()
        df_p['Fecha Inicio'] = pd.to_datetime(df_p['Fecha Inicio'], dayfirst=True, errors='coerce')
        df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
        df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)

        # Lógica de Referencias FILA POR FILA (Cambio crítico)
        def get_refs_fila(r):
            prods = [str(r.get('Producto 1')), str(r.get('Producto 2'))]
            return [p.strip() for p in prods if pd.notnull(p) and p.strip().lower() not in ['nan','','none']]
        
        df_p['Prod_List'] = df_p.apply(get_refs_fila, axis=1)
        
        # DEFINICIÓN DE CANT_REFS: Ahora se basa solo en la fila actual
        df_p['Cant_Refs'] = df_p['Prod_List'].apply(lambda x: len(x) if len(x) > 0 else 1)

        # Tiempo Prorrateado
        df_p['Tiempo_Prorrateado'] = df_p['Tiempo_Hs'] / df_p['Cant_Refs']

        maqs = sorted(df_p['Máquina'].unique())
        sel = st.multiselect("Seleccione Máquinas:", maqs)

        if sel:
            dict_m = {}; dict_p = {}
            for m in sel:
                df_m = df_p[df_p['Máquina'] == m]
                rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs':'sum', 'Buenas':'sum'}).reset_index()
                dict_m[m] = rm
                
                expandido = []
                for _, fila in df_m.iterrows():
                    for p in fila['Prod_List']:
                        expandido.append({
                            'Producto': p, 
                            'Cant_Refs': fila['Cant_Refs'], 
                            'Tiempo_Proporcional': fila['Tiempo_Prorrateado'], 
                            'Buenas': fila['Buenas']
                        })
                
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
            f_i = df_p['Fecha Inicio'].min().strftime('%d/%m/%Y') if not df_p.empty else "---"
            st.download_button("📥 DESCARGAR REPORTE PDF", generar_pdf(dict_m, dict_p, f_i, "---"), "Reporte_FAMMA.pdf", use_container_width=True)

    except Exception as e:
        st.error(f"Error técnico: {e}")
