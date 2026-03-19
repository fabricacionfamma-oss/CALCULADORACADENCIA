import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Reporte Producción FAMMA", layout="centered")

# 2. FUNCIÓN PDF
def generar_pdf(dict_resumenes, dict_productos, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE PRODUCTIVIDAD Y EFICIENCIA - FAMMA", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(5)

    for maquina in dict_resumenes.keys():
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, f" MAQUINA: {maquina}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0); pdf.ln(2)

        # CUADRO 1: Resumen Celda
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(50, 8, "Refs en Turno", border=1, align='C')
        pdf.cell(45, 8, "Tiempo (Hs)", border=1, align='C')
        pdf.cell(45, 8, "Pzas Reales", border=1, align='C')
        pdf.cell(50, 8, "Pzas/Hora Real", border=1, ln=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        for _, row in dict_resumenes[maquina].iterrows():
            pdf.cell(50, 7, f"{int(row['Cant_Refs'])} Referencia(s)", border=1)
            pdf.cell(45, 7, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(45, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        
        pdf.ln(4)

        # CUADRO 2: Desglose Pieza a Pieza (Sincronizado con TC)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 7, "Analisis por Referencia vs Estimado (TC):", ln=True)
        pdf.set_font("Arial", 'B', 8); pdf.set_fill_color(240, 240, 240)
        pdf.cell(35, 8, "Codigo", border=1, fill=True)
        pdf.cell(20, 8, "Refs/T", border=1, fill=True, align='C')
        pdf.cell(25, 8, "TC (min)", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Pzas Real", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Pzas Est.", border=1, fill=True, align='C')
        pdf.cell(30, 8, "Real P/H", border=1, fill=True, align='C')
        pdf.cell(30, 8, "Est. P/H", border=1, ln=True, fill=True, align='C')

        pdf.set_font("Arial", '', 7)
        for _, row in dict_productos[maquina].iterrows():
            pdf.cell(35, 7, str(row['Código Producto'])[:15], border=1)
            pdf.cell(20, 7, f"{int(row['Cant_Refs'])}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Tiempo Ciclo']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Pzas_Estimadas_Total']:.0f}", border=1, align='C')
            pdf.cell(30, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, align='C')
            pdf.cell(30, 7, f"{row['Pzas_Estimadas_Hora']:.2f}", border=1, ln=True, align='C')
        pdf.ln(8)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. CARGA DE DATOS
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
URL_PROD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=315437448"
URL_DATOS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=300)
def load_and_sync():
    df_p = pd.read_csv(URL_PROD)
    df_p.columns = [c.strip() for c in df_p.columns]
    # Unificar Celda 15
    df_p['Máquina'] = df_p['Máquina'].replace(['Celda 15', 'Cell 15', 'CELL 15', 'CELDA 15'], 'Celda 15')
    df_p['Fecha'] = pd.to_datetime(df_p['Fecha'], errors='coerce')
    
    df_d = pd.read_csv(URL_DATOS)
    df_d.columns = [c.strip() for c in df_d.columns]
    df_d['Máquina'] = df_d['Máquina'].replace(['Celda 15', 'Cell 15', 'CELL 15', 'CELDA 15'], 'Celda 15')
    df_d['Fecha'] = pd.to_datetime(df_d['Fecha'], errors='coerce')
    return df_p.dropna(subset=['Fecha', 'Máquina']), df_d.dropna(subset=['Fecha', 'Máquina'])

# 4. INTERFAZ
st.title("📄 Reporte Eficiencia FAMMA")

try:
    df_p_raw, df_d_raw = load_and_sync()
    maqs = sorted(df_p_raw['Máquina'].unique())
    sel_maqs = st.multiselect("Seleccione Máquinas", maqs)
    
    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", df_p_raw['Fecha'].min().date())
    f_fin = c2.date_input("Fin", df_p_raw['Fecha'].max().date())

    if sel_maqs and f_ini <= f_fin:
        res_m = {}; res_p = {}

        for m in sel_maqs:
            dp = df_p_raw[(df_p_raw['Máquina'] == m) & (df_p_raw['Fecha'].dt.date >= f_ini) & (df_p_raw['Fecha'].dt.date <= f_fin)].copy()
            dd = df_d_raw[(df_d_raw['Máquina'] == m) & (df_d_raw['Fecha'].dt.date >= f_ini) & (df_d_raw['Fecha'].dt.date <= f_fin)].copy()

            if not dp.empty:
                # Análisis Refs en DATOS
                def get_r(r):
                    vals = [r.get('Producto 1'), r.get('Producto 2'), r.get('Producto 3'), r.get('Producto 4')]
                    return {str(v).strip() for v in vals if pd.notnull(v) and str(v).strip() != '' and str(v).lower() != 'nan'}
                
                dd['RSet'] = dd.apply(get_r, axis=1)
                comp = dd.groupby(['Fecha', 'Turno'])['RSet'].apply(lambda x: len(set().union(*x))).reset_index()
                comp.columns = ['Fecha', 'Turno', 'Cant_Refs']

                # Procesar Producción
                dp['Tiempo_Hs'] = pd.to_numeric(dp['Tiempo Producción (Min)'].astype(str).str.replace(',','.'), errors='coerce').fillna(0)/60
                dp['Buenas'] = pd.to_numeric(dp['Buenas'], errors='coerce').fillna(0)
                dp['Tiempo Ciclo'] = pd.to_numeric(dp['Tiempo Ciclo'].astype(str).str.replace(',','.'), errors='coerce').fillna(0)
                
                # Sincronizar
                dfm = dp.merge(comp, on=['Fecha', 'Turno'], how='left').fillna({'Cant_Refs': 1})

                # Resumen Máquina
                rm = dfm.groupby('Cant_Refs').agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rm['Pzas_Por_Hora'] = np.where(rm['Tiempo_Hs']>0, rm['Buenas']/rm['Tiempo_Hs'], 0)
                res_m[m] = rm

                # Desglose Producto con Estimaciones
                rp = dfm.groupby(['Código Producto', 'Cant_Refs']).agg({'Buenas': 'sum', 'Tiempo_Hs': 'sum', 'Tiempo Ciclo': 'mean'}).reset_index()
                rp['Pzas_Por_Hora'] = np.where(rp['Tiempo_Hs']>0, rp['Buenas']/rp['Tiempo_Hs'], 0)
                # Cálculos Estimados
                rp['Pzas_Estimadas_Hora'] = np.where(rp['Tiempo Ciclo']>0, 60 / rp['Tiempo Ciclo'], 0)
                rp['Pzas_Estimadas_Total'] = rp['Pzas_Estimadas_Hora'] * rp['Tiempo_Hs']
                
                res_p[m] = rp.sort_values(['Código Producto', 'Cant_Refs'])

        st.divider()
        pdf = generar_pdf(res_m, res_p, f_ini, f_fin)
        st.download_button("📥 DESCARGAR REPORTE PDF", pdf, "Reporte_FAMMA.pdf", "application/pdf", use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
