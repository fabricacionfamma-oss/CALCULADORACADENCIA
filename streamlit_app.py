import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="FAMMA | Reporte de Producción", layout="centered")

# --- 2. CLASE PARA EL REPORTE PDF ---
class ReportePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0, 66, 134)
        self.cell(0, 10, 'FAMMA - Reporte de Eficiencia de Produccion', 0, 0, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

# --- 3. FUNCIONES DE PROCESAMIENTO ---
def get_csv_url(u):
    try:
        if 'd/' in u:
            mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
            gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
            return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"
    except Exception:
        pass
    return u

def procesar_datos(df_p, df_s):
    df_p.columns = [c.strip() for c in df_p.columns]
    df_s.columns = [c.strip() for c in df_s.columns]

    # 1. Limpieza y Unificación Celda 15
    if 'Máquina' in df_p.columns:
        df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'(?i).*15.*', 'Celda 15', regex=True)
    
    df_p['Tiempo (Min)'] = pd.to_numeric(df_p['Tiempo (Min)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    df_p['Buenas'] = pd.to_numeric(df_p['Buenas'], errors='coerce').fillna(0)
    df_p['No Buenas'] = pd.to_numeric(df_p['No Buenas'], errors='coerce').fillna(0)
    
    # 2. Agrupar por Evento de Producción (Nivel 1 / Columna K)
    def extraer_productos(grupo):
        prods = []
        for _, row in grupo.iterrows():
            for col in ['Producto 1', 'Producto 2']:
                if col in row and pd.notna(row[col]) and str(row[col]).strip().lower() not in ['', 'nan', 'none']:
                    prods.append(str(row[col]).strip())
        return list(set(prods))[:4] # Máximo 4 piezas simultáneas únicas

    agrupado = df_p.groupby(['Máquina', 'Nivel 1']).apply(lambda g: pd.Series({
        'Tiempo_Hs': g['Tiempo (Min)'].sum() / 60,
        'Total_Pzas_Fisicas': g['Buenas'].sum() + g['No Buenas'].sum(),
        'Productos': extraer_productos(g)
    })).reset_index()

    agrupado = agrupado[(agrupado['Tiempo_Hs'] > 0) | (agrupado['Total_Pzas_Fisicas'] > 0)]

    # 3. Cálculos de Simultaneidad y Prorrateo
    agrupado['Cant_Simultaneas'] = agrupado['Productos'].apply(lambda x: len(x) if len(x) > 0 else 1)
    agrupado['Pzas_Prorrateadas'] = agrupado['Total_Pzas_Fisicas'] / agrupado['Cant_Simultaneas']

    # 4. Desglosar datos para tabla de productos individuales
    registros_productos = []
    for _, fila in agrupado.iterrows():
        cant = fila['Cant_Simultaneas']
        for prod in fila['Productos']:
            registros_productos.append({
                'Máquina': fila['Máquina'],
                'Producto': prod,
                'Simultaneo_Con': cant,
                'Tiempo_Hs': fila['Tiempo_Hs'],
                'Pzas_Prorrateadas': fila['Pzas_Prorrateadas']
            })
    
    df_prod_desglosado = pd.DataFrame(registros_productos)

    # 5. Integrar Tiempos de Ciclo
    col_tc = 'Tiempo Ciclo' if 'Tiempo Ciclo' in df_s.columns else df_s.columns[2]
    col_cod = 'Código Producto' if 'Código Producto' in df_s.columns else df_s.columns[0]
    df_s[col_tc] = pd.to_numeric(df_s[col_tc].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    df_s_min = df_s[[col_cod, col_tc]].drop_duplicates()

    if not df_prod_desglosado.empty:
        df_prod_desglosado = df_prod_desglosado.merge(df_s_min, left_on='Producto', right_on=col_cod, how='left')
        df_prod_desglosado.rename(columns={col_tc: 'TC'}, inplace=True)
        df_prod_desglosado['TC'].fillna(0, inplace=True)
    
    return agrupado, df_prod_desglosado

def generar_pdf(maquinas, agrupado_eventos, df_productos):
    pdf = ReportePDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for maq in maquinas:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, f"MÁQUINA: {maq}", ln=True)
        pdf.ln(5)

        # --- CUADRO PRINCIPAL (MÁQUINA GLOBAL) ---
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Resumen Global por Simultaneidad", ln=True)
        
        pdf.set_font("Arial", 'B', 8)
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(35, 8, "Máquina", 1, 0, 'C', True)
        pdf.cell(35, 8, "Piezas Simultaneas", 1, 0, 'C', True)
        pdf.cell(35, 8, "Tiempo Prod. (Hs)", 1, 0, 'C', True)
        pdf.cell(45, 8, "Total Pzas Fabricadas", 1, 0, 'C', True)
        pdf.cell(40, 8, "Pzas / Hora Promedio", 1, 1, 'C', True)

        df_maq_global = agrupado_eventos[agrupado_eventos['Máquina'] == maq]
        resumen_maq = df_maq_global.groupby('Cant_Simultaneas').agg({
            'Tiempo_Hs': 'sum',
            'Pzas_Prorrateadas': 'sum'
        }).reset_index()

        pdf.set_font("Arial", '', 8)
        
        # DETECCIÓN DINÁMICA: Solo itera sobre los casos que realmente existieron para esta máquina
        casos_existentes_maq = sorted(resumen_maq['Cant_Simultaneas'].unique())
        
        for i in casos_existentes_maq:
            row = resumen_maq[resumen_maq['Cant_Simultaneas'] == i]
            t_hs = row['Tiempo_Hs'].values[0]
            p_tot = row['Pzas_Prorrateadas'].values[0]
            
            # Solo dibuja la fila si hubo tiempo o piezas contabilizadas
            if t_hs > 0 or p_tot > 0:
                ph_prom = p_tot / t_hs if t_hs > 0 else 0
                pdf.cell(35, 8, maq, 1, 0, 'C')
                pdf.cell(35, 8, str(int(i)), 1, 0, 'C')
                pdf.cell(35, 8, f"{t_hs:.2f}", 1, 0, 'C')
                pdf.cell(45, 8, f"{int(p_tot)}", 1, 0, 'C')
                pdf.cell(40, 8, f"{ph_prom:.2f}", 1, 1, 'C')

        pdf.ln(10)

        # --- CUADROS INDIVIDUALES POR PIEZA ---
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Detalle de Cadencia por Producto", ln=True)
        
        df_maq_prods = df_productos[df_productos['Máquina'] == maq] if not df_productos.empty else pd.DataFrame()
        
        if not df_maq_prods.empty:
            productos_unicos = df_maq_prods['Producto'].unique()
            
            for prod in productos_unicos:
                df_p_data = df_maq_prods[df_maq_prods['Producto'] == prod]
                resumen_prod = df_p_data.groupby('Simultaneo_Con').agg({
                    'Tiempo_Hs': 'sum',
                    'Pzas_Prorrateadas': 'sum',
                    'TC': 'first'
                }).reset_index()

                # Si por alguna razón la pieza está pero tiene 0 hs y 0 pzas, la omite
                if resumen_prod['Tiempo_Hs'].sum() == 0 and resumen_prod['Pzas_Prorrateadas'].sum() == 0:
                    continue

                pdf.set_font("Arial", 'B', 9)
                pdf.set_fill_color(0, 66, 134)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(190, 8, f"PIEZA: {str(prod)[:60]}", 1, 1, 'C', True)

                pdf.set_font("Arial", 'B', 7)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(25, 8, "Simultaneo Con", 1, 0, 'C', True)
                pdf.cell(25, 8, "Tiempo Prod (Hs)", 1, 0, 'C', True)
                pdf.cell(30, 8, "Pzas Fabricadas", 1, 0, 'C', True)
                pdf.cell(25, 8, "P/H Real", 1, 0, 'C', True)
                pdf.cell(25, 8, "Tiempo Ciclo", 1, 0, 'C', True)
                pdf.cell(30, 8, "P/H Estimada", 1, 0, 'C', True)
                pdf.cell(30, 8, "Diferencia", 1, 1, 'C', True)

                pdf.set_font("Arial", '', 8)
                
                # DETECCIÓN DINÁMICA: Solo muestra la simultaneidad real ocurrida en la pieza
                casos_existentes_prod = sorted(resumen_prod['Simultaneo_Con'].unique())
                
                for i in casos_existentes_prod:
                    row = resumen_prod[resumen_prod['Simultaneo_Con'] == i]
                    t_hs = row['Tiempo_Hs'].values[0]
                    p_tot = row['Pzas_Prorrateadas'].values[0]
                    
                    if t_hs > 0 or p_tot > 0:
                        tc = row['TC'].values[0]
                        
                        ph_real = p_tot / t_hs if t_hs > 0 else 0
                        ph_est = 60 / tc if tc > 0 else 0 
                        diferencia = ph_real - ph_est
                        
                        pdf.cell(25, 8, str(int(i)), 1, 0, 'C')
                        pdf.cell(25, 8, f"{t_hs:.2f}", 1, 0, 'C')
                        pdf.cell(30, 8, f"{int(p_tot)}", 1, 0, 'C')
                        pdf.cell(25, 8, f"{ph_real:.2f}", 1, 0, 'C')
                        pdf.cell(25, 8, f"{tc:.2f}", 1, 0, 'C')
                        pdf.cell(30, 8, f"{ph_est:.2f}", 1, 0, 'C')
                        
                        if diferencia < 0:
                            pdf.set_text_color(200, 0, 0)
                        else:
                            pdf.set_text_color(0, 150, 0)
                            
                        pdf.cell(30, 8, f"{diferencia:.2f}", 1, 1, 'C')
                        pdf.set_text_color(0, 0, 0)
        else:
            pdf.set_font("Arial", '', 9)
            pdf.cell(0, 8, "No hay productos registrados para esta máquina.", 0, 1)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- 4. INTERFAZ DE STREAMLIT ---
st.title("📊 FAMMA | Calculadora de Eficiencia Unificada")

u_p = st.text_input("1. Link de Datos de Producción (Google Sheets CSV):")
u_s = st.text_input("2. Link de Tiempos de Ciclo (Google Sheets CSV):")

if u_p and u_s:
    try:
        with st.spinner("Procesando datos y agrupando eventos..."):
            df_p = pd.read_csv(get_csv_url(u_p))
            df_s = pd.read_csv(get_csv_url(u_s))
            agrupado_eventos, df_productos = procesar_datos(df_p, df_s)
        
        maquinas_disponibles = sorted(agrupado_eventos['Máquina'].unique())
        maq_seleccionadas = st.multiselect("3. Seleccione la(s) máquina(s) a evaluar:", maquinas_disponibles, default=maquinas_disponibles)

        if maq_seleccionadas:
            pdf_bytes = generar_pdf(maq_seleccionadas, agrupado_eventos, df_productos)
            st.download_button(
                label="📥 DESCARGAR REPORTE DE CADENCIA (PDF)",
                data=pdf_bytes,
                file_name="Reporte_Cadencia_FAMMA.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.warning("Debe seleccionar al menos una máquina para generar el PDF.")
            
    except Exception as e:
        st.error(f"Se encontró un error técnico al leer las hojas de cálculo: {e}")
