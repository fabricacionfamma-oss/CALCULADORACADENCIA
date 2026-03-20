import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re
from io import BytesIO

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="FAMMA | Analizador de Eficiencia Unificada Celda 15",
    layout="wide",  # Layout ancho para mayor claridad
    initial_sidebar_state="collapsed",
)

# 2. DEFINICIÓN DEL REPORTE PDF (Reutilizando el estilo del ejemplo)
class ReportePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(150)
        self.cell(0, 10, 'FAMMA - Reporte de Eficiencia Real y Prorrateada (Celda 15)', 0, 0, 'R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

# Función para convertir URL de vista a CSV
def get_csv_url(u):
    try:
        if 'd/' in u:
            mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
            gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
            return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"
    except Exception:
        pass
    return u

# Función para preprocesar datos de producción
def preprocesar_datos(df_p):
    df_p.columns = [c.strip() for c in df_p.columns]  # Limpiar nombres de columnas

    # UNIFICACIÓN DE MÁQUINAS: Reemplazar cualquier cosa con "15" por "Celda 15"
    if 'Máquina' in df_p.columns:
        df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)

    # Filtrado por 'Producción' en Nivel 1 (Columna K)
    # Ignora mayúsculas/minúsculas y acentos
    df_p = df_p[df_p['Nivel 1'].str.contains('Producci|Produccion', na=False, case=False)].copy()

    # Parseo de fechas y números
    df_p['Fecha Inicio'] = pd.to_datetime(df_p['Fecha Inicio'], dayfirst=True, errors='coerce')
    df_p['Tiempo_Hs'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0) / 60
    df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)
    df_p['No Buenas'] = pd.to_numeric(df_p['No Buenas'], errors='coerce').fillna(0)
    df_p['Piezas_Totales'] = df_p['Buenas'] + df_p['No Buenas']

    # Identificar productos simultáneos (hasta 4)
    def get_refs_fila(r):
        prods = []
        for i in range(1, 5):  # Busca Producto 1, 2, 3, 4
            col_prod = f'Producto {i}'
            if col_prod in r and pd.notnull(r[col_prod]):
                val = str(r[col_prod]).strip()
                if val.lower() not in ['nan','','none']:
                    prods.append(val)
        return prods

    df_p['Prod_List'] = df_p.apply(get_refs_fila, axis=1)
    df_p['Cant_Refs'] = df_p['Prod_List'].apply(lambda x: len(x) if len(x) > 0 else 1)

    # CÁLCULO PRORRATEADO POR REFERENCIA (SIMULTANEIDAD N)
    df_p['Tiempo_Prorrateado_Hs'] = df_p['Tiempo_Hs'] / df_p['Cant_Refs']
    df_p['Piezas_Prorrateadas'] = df_p['Piezas_Totales'] / df_p['Cant_Refs']

    return df_p

# Función para preprocesar tiempos de ciclo
def preprocesar_ciclos(df_s):
    df_s.columns = [c.strip() for c in df_s.columns]  # Limpiar nombres de columnas
    if 'Máquina' in df_s.columns:
        df_s['Máquina'] = df_s['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
    df_s['Tiempo Ciclo'] = pd.to_numeric(df_s['Tiempo Ciclo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    return df_s

# Función para generar el PDF completo
def generar_pdf(maquinas_seleccionadas, df_global, df_productos_prorrateados):
    pdf = ReportePDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)

    for maquina in maquinas_seleccionadas:
        pdf.add_page()
        
        # Encabezado Principal
        pdf.set_font("Arial", 'B', 18)
        pdf.set_text_color(0, 66, 134)  # Azul FAMMA
        pdf.cell(190, 10, f"REPORTE DE EFICIENCIA: {maquina}", ln=True)
        pdf.ln(5)

        # --- CUADRO 1: RESUMEN GLOBAL DE LA CELDA ---
        pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0)
        pdf.cell(190, 8, "1. Rendimiento Global por Complejidad (Prropateado)", ln=True)
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        
        # Cabeceras
        pdf.cell(50, 9, "Complejidad", border=1, fill=True, align='C')
        pdf.cell(45, 9, "Total Tiempo (Hs)", border=1, fill=True, align='C')
        pdf.cell(45, 9, "Total Piezas (Prop.)", border=1, fill=True, align='C')
        pdf.cell(50, 9, "Pzas/Hora Promedio", border=1, ln=True, fill=True, align='C')
        
        # Datos Globales
        pdf.set_font("Arial", '', 9)
        df_m_global = df_global[df_global['Máquina'] == maquina]
        for _, row in df_m_global.iterrows():
            pdf.cell(50, 8, f"{int(row['Cant_Refs'])} Ref(s) simultáneas", border=1)
            pdf.cell(45, 8, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
            pdf.cell(45, 8, f"{int(row['Piezas'])}", border=1, align='C')
            cad = row['Piezas'] / row['Tiempo_Hs'] if row['Tiempo_Hs'] > 0 else 0
            pdf.cell(50, 8, f"{cad:.2f}", border=1, ln=True, align='C')
        
        if df_m_global.empty:
            pdf.cell(190, 8, "Sin datos de producción global.", border=1, ln=True, align='C')
        pdf.ln(10)

        # --- CUADRO 2: DETALLE POR PIEZA Y CONTEXTO ---
        pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "2. Detalle de Eficiencia por Referencia y Contexto", ln=True)
        pdf.set_fill_color(0, 66, 134); pdf.set_text_color(255, 255, 255)  # Azul y Blanco
        
        # Cabeceras Complejas
        h1 = 11  # Altura cabecera
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(45, h1, "Producto", 1, 0, 'C', True)
        pdf.cell(20, h1, "Simult.", 1, 0, 'C', True)
        pdf.cell(30, h1, "Contexto (Hecho con...)", 1, 0, 'C', True)
        pdf.cell(20, h1, "Tiempo (Hs P.)", 1, 0, 'C', True)
        pdf.cell(20, h1, "Piezas (P.)", 1, 0, 'C', True)
        pdf.cell(20, h1, "P/H Real", 1, 0, 'C', True)
        pdf.cell(10, h1, "TC", 1, 0, 'C', True)
        pdf.cell(15, h1, "P/H Est.", 1, 0, 'C', True)
        pdf.cell(10, h1, "Dif.", 1, 1, 'C', True)
        
        # Datos de Productos
        pdf.set_font("Arial", '', 6.5); pdf.set_text_color(0)
        df_m_prods = df_productos_prorrateados[df_productos_prorrateados['Máquina'] == maquina]
        for _, row in df_m_prods.iterrows():
            pdf.cell(45, 8, str(row['Producto'])[:30], 1)
            pdf.cell(20, 8, f"{int(row['Cant_Refs'])}", 1, 0, 'C')
            
            # Contexto truncado
            contexto = str(row['Contexto']).replace("'","")[:20] + "..." if len(str(row['Contexto'])) > 20 else str(row['Contexto']).replace("'","")
            pdf.cell(30, 8, contexto if contexto != '[]' else '-', 1, 0, 'C')
            
            pdf.cell(20, 8, f"{row['Tiempo']:.2f}", 1, 0, 'C')
            pdf.cell(20, 8, f"{int(row['Piezas'])}", 1, 0, 'C')
            pdf.cell(20, 8, f"{row['Cadencia_Real']:.2f}", 1, 0, 'C')
            pdf.cell(10, 8, f"{row['TC']:.2f}", 1, 0, 'C')
            pdf.cell(15, 8, f"{row['Pzas_Hora_Est']:.2f}", 1, 0, 'C')
            
            # Color de Diferencia
            pdf.set_font("Arial", 'B', 6.5)
            diff = row['Pzas_Hora_Est'] - row['Cadencia_Real']
            if diff < 0: pdf.set_text_color(0, 150, 0) # Verde si es más rápido
            elif diff > 5: pdf.set_text_color(200, 0, 0) # Rojo si es muy lento
            pdf.cell(10, 8, f"{diff:.1f}", 1, 1, 'C')
            pdf.set_font("Arial", '', 6.5); pdf.set_text_color(0) # Reset color

        if df_m_prods.empty:
            pdf.cell(190, 8, "Sin datos prorrateados por referencia.", 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# 3. INTERFAZ DE USUARIO CON STREAMLIT
# Replicando el layout de la vista previa: minimalist, solo inputs y PDF
st.title("📊 FAMMA | Analizador de Eficiencia Unificada Celda 15")

u_p = st.text_input("1. Link de Datos de Producción (Google Sheets CSV):")
u_s = st.text_input("2. Link de Tiempos de Ciclo (Google Sheets CSV):")

# Ejecución principal
if u_p and u_s:
    try:
        # Carga de datos
        with st.spinner("Cargando y unificando datos..."):
            df_p_raw = pd.read_csv(get_csv_url(u_p))
            df_s_raw = pd.read_csv(get_csv_url(u_s))

            df_p = preprocesar_datos(df_p_raw)
            df_s = preprocesar_ciclos(df_s_raw)

        # 1. Cálculo del Cuadro Principal Global por Máquina
        # Agrupar por Máquina y Complejidad (N)
        df_global = df_p.groupby(['Máquina', 'Cant_Refs']).agg({
            'Tiempo_Prorrateado_Hs': 'sum', 
            'Piezas_Prorrateadas': 'sum'
        }).reset_index().rename(columns={'Tiempo_Prorrateado_Hs': 'Tiempo_Hs', 'Piezas_Prorrateadas': 'Piezas'})

        # 2. Cálculo Individual de Piezas (Prorrateo Avanzado)
        expandido = []
        for _, fila in df_p.iterrows():
            cant_refs = fila['Cant_Refs']
            prod_list = fila['Prod_List']
            
            for p in prod_list:
                # El contexto son las 'otras' piezas hechas en el mismo momento
                contexto = [other_p for other_p in prod_list if other_p != p]
                expandido.append({
                    'Producto': p,
                    'Máquina': fila['Máquina'],
                    'Cant_Refs': cant_refs,
                    'Contexto': str(contexto),  # Como string para agrupar
                    'Tiempo': fila['Tiempo_Prorrateado_Hs'],
                    'Piezas': fila['Piezas_Prorrateadas']
                })
        
        df_exp = pd.DataFrame(expandido)
        # Agrupar para obtener cadencias reales prorrateadas por contexto
        df_productos_prorrateados = df_exp.groupby(['Producto', 'Máquina', 'Cant_Refs', 'Contexto']).agg({
            'Tiempo': 'sum', 
            'Piezas': 'sum'
        }).reset_index()
        df_productos_prorrateados['Cadencia_Real'] = df_productos_prorrateados['Piezas'] / df_productos_prorrateados['Tiempo']

        # 3. Comparación con Estándares (Tiempo Ciclo)
        # Integrar TC de la hoja 2
        std_c = df_s[['Código Producto', 'Tiempo Ciclo']].copy().rename(columns={'Tiempo Ciclo': 'TC'})
        df_productos_prorrateados = df_productos_prorrateados.merge(std_c, left_on='Producto', right_on='Código Producto', how='left').fillna(0)
        
        # Pzas_Hora_Est = (60 / TC) / N
        df_productos_prorrateados['Pzas_Hora_Est'] = np.where(
            (df_productos_prorrateados['TC'] > 0),
            (60 / df_productos_prorrateados['TC']) / df_productos_prorrateados['Cant_Refs'],
            0
        )

        # Selector de Máquinas (obligatorio para el reporte)
        maqs_disp = sorted(df_productos_prorrateados['Máquina'].unique())
        sel_maqs = st.multiselect("Seleccionar Máquinas para el Reporte:", maqs_disp, default=maqs_disp if 'Celda 15' in maqs_disp else None)

        if sel_maqs:
            # Botón de Descarga del PDF
            pdf_bytes = generar_pdf(sel_maqs, df_global, df_productos_prorrateados)
            
            st.download_button(
                label="📥 DESCARGAR REPORTE PDF (Reporte_FAMMA.pdf)",
                data=pdf_bytes,
                file_name="Reporte_FAMMA.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.warning("Seleccione al menos una máquina.")

    except Exception as e:
        st.error(f"Error técnico procesando la base de datos: {e}")
