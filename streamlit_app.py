def generar_pdf(df_maq, df_prod):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Título
    pdf.cell(190, 10, "Reporte de Cadencia y Productividad - FAMMA", ln=True, align='C')
    pdf.ln(10)
    
    # Sección 1: Resumen por Máquina
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "1. Cadencia Promedio por Máquina (Min/Pza)", ln=True)
    pdf.set_font("Arial", '', 10)
    
    # Encabezados de tabla Máquina
    pdf.cell(50, 8, "Maquina", border=1)
    pdf.cell(45, 8, "Una Ref", border=1)
    pdf.cell(45, 8, "Multiref", border=1)
    pdf.cell(45, 8, "Promedio", border=1, ln=True)
    
    for i, row in df_maq.iterrows():
        pdf.cell(50, 7, str(row['Máquina'])[:25], border=1)
        pdf.cell(45, 7, f"{row.get('Una Referencia', 0):.3f}", border=1)
        pdf.cell(45, 7, f"{row.get('Multireferencia', 0):.3f}", border=1)
        pdf.cell(45, 7, f"{row.get('Promedio Global', 0):.3f}", border=1, ln=True)
        
    pdf.ln(10)
    
    # Sección 2: Impacto por Producto (Top 10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "2. Impacto Multireferencia por Producto (Top 10)", ln=True)
    pdf.set_font("Arial", '', 9)
    
    pdf.cell(30, 8, "Codigo", border=1)
    pdf.cell(70, 8, "Producto", border=1)
    pdf.cell(30, 8, "Exc. (min)", border=1)
    pdf.cell(30, 8, "Multi (min)", border=1)
    pdf.cell(30, 8, "Impacto %", border=1, ln=True)
    
    # Limitamos a los 10 con más impacto para que quepa en la página
    top_prod = df_prod.sort_values('Impacto Multiref (%)', ascending=False).head(10)
    
    for i, row in top_prod.iterrows():
        pdf.cell(30, 7, str(row['Código'])[:12], border=1)
        pdf.cell(70, 7, str(row['Producto'])[:35], border=1)
        pdf.cell(30, 7, f"{row['Cadencia (Excluida)']:.2f}", border=1)
        pdf.cell(30, 7, f"{row['Cadencia (Multiref)']:.2f}", border=1)
        pdf.cell(30, 7, f"{row['Impacto Multiref (%)']:.1f}%", border=1, ln=True)

    return pdf.output(dest='S').encode('latin-1')

# --- BOTÓN DE DESCARGA EN STREAMLIT ---
st.subheader("📄 Exportar Reporte Formal")
if 'pivot_maq' in locals() and 'pivot_prod' in locals():
    try:
        pdf_bytes = generar_pdf(pivot_maq, pivot_prod)
        st.download_button(
            label="Descargar Reporte PDF",
            data=pdf_bytes,
            file_name="reporte_cadencia_famma.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error al generar PDF: {e}. Asegúrate de que no haya caracteres especiales en los nombres.")
