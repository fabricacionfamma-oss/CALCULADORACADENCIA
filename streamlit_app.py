import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from fpdf import FPDF
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Panel de Producción", layout="wide")
st.title("📊 Análisis de Producción y Rendimiento Ejecutivo")

# ==========================================
# 1. CONFIGURACIÓN DE FUENTE DE DATOS FIJA
# ==========================================
# URL de tu Google Sheet específica (Exportada como CSV)
SHEET_ID = "1TdQ3yNxx29SgQ7u8oexxlnL80rAcXQuP118wQVBd9ew"
GID = "315437448"  # El ID de la pestaña 'PRODUCCION'
url_csv = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

@st.cache_data(ttl=600)  # Cache por 10 minutos para no saturar la red
def cargar_datos(url):
    return pd.read_csv(url)

try:
    st.info("Obteniendo datos desde Google Sheets...")
    df_raw = cargar_datos(url_csv)
    
    # Pre-procesamiento de fechas para el filtro
    df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'], errors='coerce')
    df_raw = df_raw.dropna(subset=['Fecha'])

    # ==========================================
    # 2. FILTRO POR RANGO DE TIEMPO (Sidebar)
    # ==========================================
    st.sidebar.header("Filtros de Tiempo")
    fecha_min = df_raw['Fecha'].min().date()
    fecha_max = df_raw['Fecha'].max().date()
    
    rango_fechas = st.sidebar.date_input(
        "Selecciona el rango de fechas:",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max
    )

    # Validar que se seleccionen ambas fechas del rango
    if len(rango_fechas) == 2:
        inicio, fin = rango_fechas
        mask = (df_raw['Fecha'].dt.date >= inicio) & (df_raw['Fecha'].dt.date <= fin)
        df = df_raw.loc[mask].copy()
    else:
        st.warning("Por favor, selecciona un rango de fechas (Inicio y Fin).")
        st.stop()

    # ==========================================
    # 3. LIMPIEZA Y CÁLCULOS (Tu lógica original corregida)
    # ==========================================
    df = df.dropna(how='all')
    df['Máquina'] = df['Máquina'].astype(str).str.strip()
    df = df[~df['Máquina'].str.lower().isin(['nan', 'none', '', 'null'])]

    columnas_num = ['Buenas', 'Retrabajo', 'Observadas', 'Tiempo Producción (Min)', 'Tiempo Ciclo', 'Hora']
    for col in columnas_num:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df = df[df['Tiempo Producción (Min)'] > 0]
    df['Hora_Real'] = df['Hora'].astype(int)
    df['Orden_Hora'] = df['Hora_Real'].apply(lambda x: x if x >= 6 else x + 24)
    df['Total_Piezas_Fabricadas'] = df['Buenas'] + df['Retrabajo'] + df['Observadas']
    df['Horas_Decimal'] = df['Tiempo Producción (Min)'] / 60

    # Lógica de agrupamiento (Igual a la original)
    def calcular_sub_bloque(g):
        if g.empty: return pd.Series({'Total_Piezas': 0.0, 'Total_Horas': 0.0, 'Cantidad_Productos': 0, 'Ciclos_Maquina': 0.0})
        total_piezas = float(g['Total_Piezas_Fabricadas'].sum())
        cantidad_productos = int(g['Código Producto'].nunique())
        total_horas = float(g['Horas_Decimal'].iloc[0])
        ciclos_maquina = total_piezas / cantidad_productos if cantidad_productos > 0 else 0.0
        return pd.Series([total_piezas, total_horas, cantidad_productos, ciclos_maquina], 
                         index=['Total_Piezas', 'Total_Horas', 'Cantidad_Productos', 'Ciclos_Maquina'])

    despliegue_hora = df.groupby(['Fecha', 'Máquina', 'Hora_Real', 'Orden_Hora', 'Horas_Decimal']).apply(calcular_sub_bloque).reset_index()
    despliegue_hora['Pzs_Hora_Bloque'] = np.where(despliegue_hora['Total_Horas'] > 0, despliegue_hora['Total_Piezas'] / despliegue_hora['Total_Horas'], 0)
    despliegue_hora['Ciclos_Hora_Bloque'] = np.where(despliegue_hora['Total_Horas'] > 0, despliegue_hora['Ciclos_Maquina'] / despliegue_hora['Total_Horas'], 0)

    # --- El resto de tu código de visualización (Tabs, Matplotlib, FPDF) sigue igual ---
    # (Pestañas tab1, tab2, tab3, tab4 y generación de PDF...)
    
    st.success(f"Analizando datos desde el {inicio} hasta el {fin}")
    
    # [Aquí insertas el resto de las pestañas y la lógica del PDF que ya tenías]
    # ... (Omitido por brevedad, pero se mantiene igual)

except Exception as e:
    st.error(f"Error de procesamiento: {e}")
    st.info("Asegúrate de que el Google Sheet sea público o compartido con 'Cualquier persona con el enlace'.")
