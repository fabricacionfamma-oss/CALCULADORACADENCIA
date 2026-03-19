import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="FAMMA | Real vs Estimado", layout="centered")

# 2. FUNCIÓN PDF MEJORADA
def generar_pdf(dict_resumenes, dict_productos, f_inicio, f_fin):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE PRODUCTIVIDAD: REAL VS ESTIMADO", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Periodo: {f_inicio} al {f_fin}", ln=True, align='C')
    pdf.ln(10)

    for maquina in dict_resumenes.keys():
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(40, 40, 40); pdf.set_text_color(255, 255, 255)
        pdf.cell(190, 10, f" MAQUINA: {maquina}", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0); pdf.ln(2)

        # CUADRO 1: Resumen de Máquina
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(60, 8, "Escenario (Refs)", border=1, align='C')
        pdf.cell(40, 8, "Tiempo (Hs)", border=1, align='C')
        pdf.cell(40, 8, "Pzas Reales", border=1, align='C')
        pdf.cell(50, 8, "Pzas / Hora Real", border=1, ln=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        for _, row in dict_resumenes[maquina].iterrows():
            pdf.cell(60, 7, f"{int(row['Cant_Refs'])} Referencia(s) en Turno", border=1)
            pdf.cell(40, 7, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(40, 7, f"{int(row['Buenas'])}", border=1, align='C')
            pdf.cell(50, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, ln=True, align='C')
        pdf.ln(5)

        # CUADRO 2: Comparativa por Producto (Real vs Estimado)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 7, "Desglose de Eficiencia por Producto:", ln=True)
        pdf.set_font("Arial", 'B', 8); pdf.set_fill_color(240, 240, 240)
        pdf.cell(40, 8, "Codigo", border=1, fill=True)
        pdf.cell(25, 8, "TC Est.", border=1, fill=True, align='C')
        pdf.cell(25, 8, "P/H Est.", border=1, fill=True, align='C')
        pdf.cell(25, 8, "P/H Real", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Eficiencia", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Refs/T", border=1, fill=True, align='C')
        pdf.cell(25, 8, "Hs Prod", border=1, ln=True, fill=True, align='C')

        pdf.set_font("Arial", '', 7)
        df_prod = dict_productos[maquina]
        for _, row in df_prod.iterrows():
            eficiencia = (row['Pzas_Por_Hora'] / row['PH_Est']) * 100 if row['PH_Est'] > 0 else 0
            pdf.cell(40, 7, str(row['Producto 1'])[:18], border=1)
            pdf.cell(25, 7, f"{row['Tiempo Ciclo']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['PH_Est']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Pzas_Por_Hora']:.2f}", border=1, align='C')
            pdf.cell(25, 7, f"{eficiencia:.1f}%", border=1, align='C')
            pdf.cell(25, 7, f"{int(row['Cant_Refs'])}", border=1, align='C')
            pdf.cell(25, 7, f"{row['Tiempo_Hs']:.2f}", border=1, ln=True, align='C')
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. PROCESAMIENTO
def procesar_famma(url_principal, url_estandares):
    # Función para obtener CSV de links
    def get_csv(u):
        mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
        gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
        return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"

    # Cargar Producción
    df = pd.read_csv(get_csv(url_principal))
    df.columns = [c.strip() for c in df.columns]
    df['Máquina'] = df['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
    df = df[df['Nivel 1'].str.contains('Producción', na=False, case=False)].copy()
    
    # Cargar Estándares
    df_est = pd.read_csv(get_csv(url_estandares))
    df_est.columns = [c.strip() for c in df_est.columns]
    df_est['Código Máquina'] = df_est['Código Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)

    # Limpieza de datos reales
    df['Fecha Inicio'] = pd.to_datetime(df['Fecha Inicio'], errors='coerce')
    df['Tiempo_Hs'] = pd.to_numeric(df['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
    df['Buenas'] = pd.to_numeric(df['Buenas'], errors='coerce').fillna(0)

    # Identificar complejidad por turno
    def get_refs(r):
        return {str(r.get('Producto 1', '')), str(r.get('Producto 2', ''))} - {'nan', '', 'None'}
    
    df['Refs_Fila'] = df.apply(get_refs, axis=1)
    df['Fecha_D'] = df['Fecha Inicio'].dt.date
    comp = df.groupby(['Máquina', 'Fecha_D', 'Turno'])['Refs_Fila'].apply(lambda x: len(set().union(*x))).reset_index()
    comp.columns = ['Máquina', 'Fecha_D', 'Turno', 'Cant_Refs']
    df = df.merge(comp, on=['Máquina', 'Fecha_D', 'Turno'])

    return df, df_est

# --- INTERFAZ ---
st.title("📄 Reporte Eficiencia: Real vs Estándar")

url_data = st.text_input("1. Link de Producción (Eventos):")
url_std = st.text_input("2. Link de Estándares (Tiempo Ciclo):")

if url_data and url_std:
    try:
        df_real, df_std = procesar_famma(url_data, url_std)
        maqs = sorted(df_real['Máquina'].unique())
        sel = st.multiselect("Seleccione las Máquinas:", maqs)
        
        if sel:
            res_m = {}; res_p = {}
            for m in sel:
                # Filtrar real por máquina
                df_m = df_real[df_real['Máquina'] == m]
                
                # Resumen Máquina
                rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rm['Pzas_Por_Hora'] = np.where(rm['Tiempo_Hs'] > 0, rm['Buenas'] / rm['Tiempo_Hs'], 0)
                res_m[m] = rm
                
                # Resumen Producto + Cruce con Estándares
                rp = df_m.groupby(['Producto 1', 'Cant_Refs']).agg({'Tiempo_Hs': 'sum', 'Buenas': 'sum'}).reset_index()
                rp['Pzas_Por_Hora'] = np.where(rp['Tiempo_Hs'] > 0, rp['Buenas'] / rp['Tiempo_Hs'], 0)
                
                # Unir con Estándares por Código Producto y Máquina
                # Nota: Asegurarse que 'Producto 1' en real coincida con 'Código Producto' en estándares
                rp = rp.merge(df_std[['Código Producto', 'Código Máquina', 'Tiempo Ciclo']], 
                              left_on=['Producto 1', 'Cant_Refs'], # Aquí puedes ajustar la lógica de cruce
                              right_on=['Código Producto', 'Código Producto'], # Ajustar nombres de columnas según sea necesario
                              how='left')
                
                # Si el cruce directo falla por nombres, lo simplificamos a Producto 1
                rp = rp.merge(df_std[['Código Producto', 'Tiempo Ciclo']], 
                              left_on='Producto 1', right_on='Código Producto', how='left').drop_duplicates()
                
                rp['Tiempo Ciclo'] = pd.to_numeric(rp['Tiempo Ciclo'], errors='coerce').fillna(0)
                rp['PH_Est'] = np.where(rp['Tiempo Ciclo'] > 0, 60 / rp['Tiempo Ciclo'], 0)
                
                res_p[m] = rp.sort_values(['Producto 1', 'Cant_Refs'])

            st.divider()
            pdf_b = generar_pdf(res_m, res_p, df_real['Fecha Inicio'].min().date(), df_real['Fecha Inicio'].max().date())
            st.download_button("📥 DESCARGAR REPORTE COMPARATIVO PDF", pdf_b, "Reporte_Eficiencia.pdf", use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
