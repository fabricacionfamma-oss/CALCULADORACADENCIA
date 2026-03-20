import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import re

# 1. CONFIGURACIÓN
st.set_page_config(page_title="FAMMA | Analizador de Producción", layout="centered")

class ReportePDF(FPDF):
    def header(self):
        if self.page_no() > 0:
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.cell(0, 10, 'FAMMA - Reporte de Eficiencia Real', 0, 0, 'R')
            self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def generar_pdf(dict_resumenes, dict_productos):
    pdf = ReportePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for maquina in sorted(dict_resumenes.keys()):
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(0, 66, 134)
        pdf.cell(190, 10, f"REPORTE DE PRODUCCION: {maquina}", ln=True)
        pdf.ln(5)

        # TABLA 1: RESUMEN GLOBAL
        pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0)
        pdf.cell(190, 8, "1. Rendimiento Global por Complejidad de Celda", ln=True)
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        pdf.cell(60, 9, "Complejidad (Refs)", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Horas Totales", border=1, fill=True, align='C')
        pdf.cell(40, 9, "Pzas Totales", border=1, fill=True, align='C')
        pdf.cell(50, 9, "Cadencia Real (P/H)", border=1, ln=True, fill=True, align='C')
        
        pdf.set_font("Arial", '', 9)
        if not dict_resumenes[maquina].empty:
            for _, row in dict_resumenes[maquina].iterrows():
                pdf.cell(60, 8, f"{int(row['Cant_Refs'])} Ref(s) simultaneas", border=1)
                pdf.cell(40, 8, f"{row['Tiempo_Hs']:.2f}", border=1, align='C')
                pdf.cell(40, 8, f"{int(row['Piezas_Calc'])}", border=1, align='C')
                cad = row['Piezas_Calc'] / row['Tiempo_Hs'] if row['Tiempo_Hs'] > 0 else 0
                pdf.cell(50, 8, f"{cad:.2f}", border=1, ln=True, align='C')
        else:
            pdf.cell(190, 8, "Sin datos de produccion", border=1, ln=True, align='C')
        pdf.ln(10)

        # TABLA 2: DETALLE PRODUCTO
        pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "2. Detalle de Eficiencia por Referencia", ln=True)
        pdf.set_fill_color(0, 66, 134); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(45, 9, "Producto", 1, 0, 'C', True)
        pdf.cell(20, 9, "Simult.", 1, 0, 'C', True)
        pdf.cell(25, 9, "Horas", 1, 0, 'C', True)
        pdf.cell(25, 9, "Pzas Calc.", 1, 0, 'C', True)
        pdf.cell(25, 9, "Real P/H", 1, 0, 'C', True)
        pdf.cell(25, 9, "Est. P/H", 1, 0, 'C', True)
        pdf.cell(25, 9, "Efic.", 1, 1, 'C', True)
        
        pdf.set_font("Arial", '', 7); pdf.set_text_color(0)
        if maquina in dict_productos and not dict_productos[maquina].empty:
            for _, row in dict_productos[maquina].iterrows():
                pdf.cell(45, 7, str(row['Producto'])[:22], 1)
                pdf.cell(20, 7, f"{int(row['Cant_Refs'])}", 1, 0, 'C')
                pdf.cell(25, 7, f"{row['Tiempo']:.2f}", 1, 0, 'C')
                pdf.cell(25, 7, f"{int(row['Piezas'])}", 1, 0, 'C')
                pdf.cell(25, 7, f"{row['Cadencia_Ind']:.2f}", 1, 0, 'C')
                pdf.cell(25, 7, f"{row['PH_E']:.2f}", 1, 0, 'C')
                pdf.cell(25, 7, f"{row['Efic']:.1f}%", 1, 1, 'C')
        else:
            pdf.cell(190, 7, "Sin datos por producto", 1, 1, 'C')
            
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

def get_csv_url(u):
    if 'd/' in u:
        mid = re.search(r'd/([a-zA-Z0-9-_]+)', u).group(1)
        gid = re.search(r'gid=([0-9]+)', u).group(1) if 'gid=' in u else '0'
        return f"https://docs.google.com/spreadsheets/d/{mid}/export?format=csv&gid={gid}"
    return u

# 2. INTERFAZ DE USUARIO (SOLO ENTRADAS)
st.title("📊 FAMMA | Calculador de Producción")

u_p = st.text_input("1. Link de Producción (Google Sheets):")
u_s = st.text_input("2. Link de Estándares (Google Sheets):")

if u_p and u_s:
    try:
        df_p = pd.read_csv(get_csv_url(u_p))
        df_s = pd.read_csv(get_csv_url(u_s))
        df_p.columns = [c.strip() for c in df_p.columns]
        df_s.columns = [c.strip() for c in df_s.columns]

        # --- UNIFICACIÓN DE MÁQUINAS (Celda 15) ---
        if 'Máquina' in df_p.columns:
            df_p['Máquina'] = df_p['Máquina'].astype(str).replace(r'.*15.*', 'Celda 15', regex=True)
        
        # Identificar las columnas clave según instrucciones
        # Columna K generalmente es el índice 10
        col_evento = df_p.columns[10] if len(df_p.columns) > 10 else 'Evento'
        col_buenas = 'Buenas' if 'Buenas' in df_p.columns else df_p.columns[7]
        col_nobuenas = 'No Buenas' if 'No Buenas' in df_p.columns else df_p.columns[8]
        col_tiempo = 'Tiempo (Min)' if 'Tiempo (Min)' in df_p.columns else 'Tiempo'
        
        # Limpieza de valores
        df_p[col_buenas] = pd.to_numeric(df_p[col_buenas], errors='coerce').fillna(0)
        df_p[col_nobuenas] = pd.to_numeric(df_p[col_nobuenas], errors='coerce').fillna(0)
        df_p[col_tiempo] = pd.to_numeric(df_p[col_tiempo].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # Agrupar por Evento (Columna K) y Máquina para unificar filas del mismo evento
        agg_cols = {
            col_tiempo: 'sum',
            col_buenas: 'sum',
            col_nobuenas: 'sum'
        }
        
        # Contemplar hasta 4 productos en la celda
        for i in range(1, 5):
            col_p = f'Producto {i}'
            if col_p in df_p.columns:
                agg_cols[col_p] = 'first'
                
        group_keys = []
        if 'Máquina' in df_p.columns: group_keys.append('Máquina')
        if col_evento in df_p.columns: group_keys.append(col_evento)
        elif 'Evento' in df_p.columns: group_keys.append('Evento')
        
        if group_keys:
            df_eventos = df_p.groupby(group_keys, as_index=False).agg(agg_cols)
        else:
            df_eventos = df_p.copy()
        
        # Cálculos de Tiempo y Piezas Totales
        df_eventos['Tiempo_Hs'] = df_eventos[col_tiempo] / 60
        df_eventos['Piezas_Totales'] = df_eventos[col_buenas] + df_eventos[col_nobuenas]
        
        # Determinar simultaneidad
        def get_refs_fila(r):
            prods = []
            for i in range(1, 5):
                col = f'Producto {i}'
                if col in r and pd.notnull(r[col]):
                    val = str(r[col]).strip()
                    if val.lower() not in ['nan', '', 'none']:
                        prods.append(val)
            return prods
        
        df_eventos['Prod_List'] = df_eventos.apply(get_refs_fila, axis=1)
        df_eventos['Cant_Refs'] = df_eventos['Prod_List'].apply(lambda x: len(x) if len(x) > 0 else 1)
        
        # División de piezas por producto (prorrateo de factor simultaneidad)
        df_eventos['Piezas_Calc'] = df_eventos['Piezas_Totales'] / df_eventos['Cant_Refs']
        
        maquinas = sorted(df_eventos['Máquina'].unique()) if 'Máquina' in df_eventos.columns else ['General']
        
        dict_m = {}; dict_p = {}
        
        for m in maquinas:
            df_m = df_eventos[df_eventos['Máquina'] == m] if 'Máquina' in df_eventos.columns else df_eventos
            
            # 1. Resumen Global de la Máquina
            rm = df_m.groupby('Cant_Refs').agg({'Tiempo_Hs':'sum', 'Piezas_Calc':'sum'}).reset_index()
            dict_m[m] = rm
            
            # 2. Detalle por Producto individual
            expandido = []
            for _, fila in df_m.iterrows():
                cant = fila['Cant_Refs']
                if cant == 0: continue
                for p in fila['Prod_List']:
                    expandido.append({
                        'Producto': p,
                        'Cant_Refs': cant,
                        'Tiempo': fila['Tiempo_Hs'],
                        'Piezas': fila['Piezas_Calc']
                    })
                    
            if expandido:
                df_exp = pd.DataFrame(expandido)
                rp = df_exp.groupby(['Producto', 'Cant_Refs']).agg({'Tiempo':'sum', 'Piezas':'sum'}).reset_index()
                
                # Cadencia Real
                rp['Cadencia_Ind'] = np.where(rp['Tiempo'] > 0, rp['Piezas'] / rp['Tiempo'], 0)
                
                # Integrar con hoja de Estándares (Tiempos de Ciclo)
                col_cod_prod = 'Código Producto' if 'Código Producto' in df_s.columns else df_s.columns[0]
                col_tc = 'Tiempo Ciclo' if 'Tiempo Ciclo' in df_s.columns else df_s.columns[1]
                
                std_c = df_s[[col_cod_prod, col_tc]].copy()
                std_c['TC_E'] = pd.to_numeric(std_c[col_tc].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                
                rp = rp.merge(std_c, left_on='Producto', right_on=col_cod_prod, how='left')
                
                # Estándar P/H dividido en la cantidad de productos en simultáneo
                rp['PH_E'] = np.where(rp['TC_E'] > 0, (60 / rp['TC_E']) / rp['Cant_Refs'], 0)
                rp['Efic'] = np.where(rp['PH_E'] > 0, (rp['Cadencia_Ind'] / rp['PH_E']) * 100, 0)
                
                dict_p[m] = rp.fillna(0).sort_values(['Producto', 'Cant_Refs'])
            else:
                dict_p[m] = pd.DataFrame()

        # Generar PDF y mostrar botón
        pdf_bytes = generar_pdf(dict_m, dict_p)
        st.download_button(
            label="📥 DESCARGAR REPORTE PDF", 
            data=pdf_bytes, 
            file_name="Reporte_Produccion.pdf", 
            mime="application/pdf", 
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error técnico procesando la base de datos: {e}")
