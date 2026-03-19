import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from fpdf import FPDF
from datetime import datetime

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="Generador de Reportes de Producción - FUMISCOR", layout="centered")
st.title("📊 Generador de Reporte Analítico (PDF) - FUMISCOR")
st.markdown("**Análisis de Exclusividad y Producción Compartida**")

# ==========================================
# 1. FUENTE DE DATOS FIJA
# ==========================================
SHEET_ID = "1c4aEFtCS-sJZFcH6iLb8AdBVsPrz0pNWayHR2-Dhfm8"
GID = "315437448"
url_csv = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

@st.cache_data(ttl=600)
def cargar_datos(url):
    return pd.read_csv(url)

try:
    st.info("Obteniendo datos de producción desde Google Sheets...")
    df_raw = cargar_datos(url_csv)
    
    # Pre-procesamiento de fechas
    df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'], dayfirst=True, errors='coerce')
    df_raw = df_raw.dropna(subset=['Fecha'])

    # ==========================================
    # 2. FILTROS (FECHA Y MÁQUINA)
    # ==========================================
    st.markdown("### Configuración del Reporte")
    
    fecha_min = df_raw['Fecha'].min().date()
    fecha_max = df_raw['Fecha'].max().date()
    
    rango_fechas = st.date_input(
        "📅 1. Selecciona el rango de fechas:",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max
    )

    if len(rango_fechas) == 2:
        inicio, fin = rango_fechas
        mask = (df_raw['Fecha'].dt.date >= inicio) & (df_raw['Fecha'].dt.date <= fin)
        df_filtrado = df_raw.loc[mask].copy()
    else:
        st.warning("Por favor, selecciona un rango de fechas completo (Inicio y Fin).")
        st.stop()

    # --- LIMPIEZA Y FILTRO FUMISCOR ---
    df_filtrado = df_filtrado.dropna(subset=['Máquina'])
    df_filtrado['Máquina'] = df_filtrado['Máquina'].astype(str).str.strip()
    df_filtrado = df_filtrado[~df_filtrado['Máquina'].str.lower().isin(['nan', 'none', '', 'null'])]

    if 'Fábrica' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Fábrica'].str.contains('FUMISCOR', case=False, na=False)]

    lista_maquinas = sorted(df_filtrado['Máquina'].unique().tolist())
    
    maquinas_seleccionadas = st.multiselect(
        "⚙️ 2. Selecciona la(s) Máquina(s) a incluir en el PDF:", 
        options=lista_maquinas,
        default=lista_maquinas
    )

    if not maquinas_seleccionadas:
        st.warning("Por favor, selecciona al menos una máquina para generar el reporte.")
        st.stop()

    df = df_filtrado[df_filtrado['Máquina'].isin(maquinas_seleccionadas)].copy()

    st.success(f"Datos listos para procesar ({len(df)} registros encontrados).")
    st.divider()

    # ==========================================
    # 3. LÓGICA DE EXCLUSIVIDAD (SOLO VS COMPARTIDO)
    # ==========================================
    with st.spinner("Calculando exclusividad de piezas y promedios..."):
        # Limpieza de valores numéricos
        for col in ['Buenas', 'Retrabajo', 'Observadas', 'Tiempo Producción (Min)']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df = df[df['Tiempo Producción (Min)'] > 0].copy()
        df['Hora_Real'] = df['Hora'].astype(int)
        df['Total_Piezas'] = df['Buenas'] + df['Retrabajo'] + df['Observadas']
        df['Horas_Decimal'] = df['Tiempo Producción (Min)'] / 60

        # Identificar si la hora fue exclusiva o compartida
        bloques_stats = []
        for name, group in df.groupby(['Fecha', 'Máquina', 'Hora_Real']):
            fecha, maq, hora = name
            cant_prods = group['Código Producto'].nunique()
            modo = "Exclusivo" if cant_prods == 1 else "Compartido"
            
            # El tiempo real que la máquina estuvo operando en ese bloque (hora)
            horas_maq = group['Horas_Decimal'].max()
            piezas_totales = group['Total_Piezas'].sum()
            
            bloques_stats.append({
                'Fecha': fecha, 'Máquina': maq, 'Hora_Real': hora,
                'Modo': modo, 'Horas_Maq': horas_maq, 'Piezas_Maq': piezas_totales
            })
            
        df_bloques = pd.DataFrame(bloques_stats)

        # RESUMEN GENERAL POR MÁQUINA
        resumen_maq = df_bloques.groupby(['Máquina', 'Modo']).agg(
            Horas_Totales=('Horas_Maq', 'sum'),
            Piezas_Totales=('Piezas_Maq', 'sum')
        ).reset_index()
        resumen_maq['Promedio_Pzs_Hr'] = np.where(resumen_maq['Horas_Totales'] > 0, 
                                                  resumen_maq['Piezas_Totales'] / resumen_maq['Horas_Totales'], 0)
        resumen_maq = resumen_maq.sort_values(by=['Máquina', 'Modo'], ascending=[True, False])

        # RESUMEN DETALLADO POR PRODUCTO
        df = df.merge(df_bloques[['Fecha', 'Máquina', 'Hora_Real', 'Modo']], on=['Fecha', 'Máquina', 'Hora_Real'], how='left')
        
        # Agrupamos primero por bloque para no duplicar horas si un producto tiene 2 registros en la misma hora (raro, pero seguro)
        prod_bloque = df.groupby(['Máquina', 'Código Producto', 'Modo', 'Fecha', 'Hora_Real']).agg(
            Piezas_Prod=('Total_Piezas', 'sum'),
            Horas_Prod=('Horas_Decimal', 'max')
        ).reset_index()
        
        resumen_prod = prod_bloque.groupby(['Máquina', 'Código Producto', 'Modo']).agg(
            Horas_Totales=('Horas_Prod', 'sum'),
            Piezas_Totales=('Piezas_Prod', 'sum')
        ).reset_index()
        
        resumen_prod['Promedio_Pzs_Hr'] = np.where(resumen_prod['Horas_Totales'] > 0, 
                                                   resumen_prod['Piezas_Totales'] / resumen_prod['Horas_Totales'], 0)
        
        # Mapeamos "Exclusivo" -> "Solo" y "Compartido" -> "En Conjunto" para lectura amigable
        resumen_prod['Modo'] = resumen_prod['Modo'].replace({"Exclusivo": "Solo", "Compartido": "En Conjunto"})
        resumen_prod = resumen_prod.sort_values(by=['Máquina', 'Código Producto', 'Modo'])

    # ==========================================
    # 4. GENERACIÓN DEL PDF
    # ==========================================
    with st.spinner("Armando el documento PDF..."):
        pdf = FPDF()
        AZUL_TITULO = (0, 51, 102)
        AZUL_FONDO = (204, 229, 255)

        pdf.add_page()
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(*AZUL_TITULO)
        pdf.cell(190, 10, "REPORTE DE EXCLUSIVIDAD Y RENDIMIENTO - FUMISCOR", 0, 1, 'C')
        
        pdf.set_font("Arial", "I", 11)
        pdf.set_text_color(100, 100, 100)
        texto_maquinas = "Multiples Seleccionadas" if len(maquinas_seleccionadas) > 1 else maquinas_seleccionadas[0]
        pdf.cell(190, 8, f"Periodo: {inicio} al {fin} | Maquina(s): {texto_maquinas}", 0, 1, 'C')
        pdf.ln(5)

        # ---- SECCIÓN 1: Análisis General por Máquina ----
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(190, 10, "1. Rendimiento de la Maquina (Exclusivo vs Compartido)", 0, 1)
        
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(*AZUL_FONDO)
        pdf.cell(50, 8, "Maquina", 1, 0, 'C', True)
        pdf.cell(35, 8, "Modo Trabajo", 1, 0, 'C', True)
        pdf.cell(30, 8, "Horas Totales", 1, 0, 'C', True)
        pdf.cell(40, 8, "Piezas Producidas", 1, 0, 'C', True)
        pdf.cell(35, 8, "Promedio (Pzs/h)", 1, 1, 'C', True)
        
        pdf.set_font("Arial", "", 9)
        for _, r in resumen_maq.iterrows():
            pdf.cell(50, 7, str(r['Máquina'])[:25], 1)
            pdf.cell(35, 7, r['Modo'], 1, 0, 'C')
            pdf.cell(30, 7, f"{r['Horas_Totales']:.2f} h", 1, 0, 'C')
            pdf.cell(40, 7, str(int(r['Piezas_Totales'])), 1, 0, 'C')
            pdf.cell(35, 7, f"{r['Promedio_Pzs_Hr']:.2f}", 1, 1, 'C')
        pdf.ln(8)

        # ---- SECCIÓN 2: Desglose por Producto ----
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "2. Rendimiento por Producto (Solo vs En Conjunto)", 0, 1)
        
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(*AZUL_FONDO)
        pdf.cell(35, 8, "Maquina", 1, 0, 'C', True)
        pdf.cell(55, 8, "Codigo Producto", 1, 0, 'C', True)
        pdf.cell(30, 8, "Estado", 1, 0, 'C', True)
        pdf.cell(20, 8, "Horas", 1, 0, 'C', True)
        pdf.cell(25, 8, "Piezas", 1, 0, 'C', True)
        pdf.cell(25, 8, "Prom (Pzs/h)", 1, 1, 'C', True)
        
        pdf.set_font("Arial", "", 8)
        for _, r in resumen_prod.iterrows():
            # Cortar nombres largos para no romper tabla
            maq_str = str(r['Máquina'])[:18]
            prod_str = str(r['Código Producto'])[:30]
            
            pdf.cell(35, 7, maq_str, 1)
            pdf.cell(55, 7, prod_str, 1)
            
            # Destacar colores si trabaja Solo vs Conjunto
            if r['Modo'] == 'Solo':
                pdf.set_text_color(0, 100, 0) # Verde
            else:
                pdf.set_text_color(150, 100, 0) # Naranja/Marrón
                
            pdf.cell(30, 7, r['Modo'], 1, 0, 'C')
            pdf.set_text_color(0, 0, 0) # Volver a negro
            
            pdf.cell(20, 7, f"{r['Horas_Totales']:.2f}", 1, 0, 'C')
            pdf.cell(25, 7, str(int(r['Piezas_Totales'])), 1, 0, 'C')
            pdf.cell(25, 7, f"{r['Promedio_Pzs_Hr']:.2f}", 1, 1, 'C')

        # ==========================================
        # DESCARGA DEL ARCHIVO
        # ==========================================
        fecha_str = f"{inicio.strftime('%d%m%y')}_al_{fin.strftime('%d%m%y')}"
        if len(maquinas_seleccionadas) > 1:
            nombre_archivo = f"Fumiscor_Exclusividad_Multi_{fecha_str}.pdf"
        else:
            nombre_limpio = maquinas_seleccionadas[0].replace(' ', '_')
            nombre_archivo = f"Fumiscor_Exclusividad_{nombre_limpio}_{fecha_str}.pdf"
            
        pdf.output(nombre_archivo)

    # Botón de descarga
    with open(nombre_archivo, "rb") as f:
        st.download_button(
            label="📥 Descargar Reporte Analítico FUMISCOR", 
            data=f, 
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True
        )

    if os.path.exists(nombre_archivo):
        os.remove(nombre_archivo)

except Exception as e:
    st.error(f"Error de procesamiento: {e}")
