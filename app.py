import streamlit as st
from google import genai

# Configuración de la página
st.set_page_config(page_title="IA Diagnóstico Automotriz - Gadiel", layout="wide")

st.title("🚗 IA de Diagnóstico Automotriz de Gadiel")
st.caption("Versión 0.1 - Análisis de causas raíz y lectura de reportes Ediag")

# Campo para ingresar la API Key de forma segura
api_key = st.sidebar.text_input("Ingresa tu API Key de Google Gemini:", type="password")

# Instrucciones del sistema para el razonamiento técnico de la IA
SYSTEM_INSTRUCTION = """
Eres un asistente experto en diagnóstico automotriz avanzado. Tu objetivo principal NO es traducir códigos DTC ni recomendar cambiar piezas por código.
Tu meta es encontrar la CAUSA RAÍZ (causas comunes como alimentaciones, tierras, fusibles compartidos, retransmisiones o redes CAN) que explique la mayor cantidad de síntomas y códigos con la menor cantidad de suposiciones.

Sigue estrictamente estas reglas:
1. Extrae automáticamente del reporte Ediag: Marca, Modelo, Año, VIN, Motor, Módulos afectados y Lista de DTCs.
2. Distingue claramente entre: CÓDIGOS, SÍNTOMAS, HIPÓTESIS y CONFIRMADO.
3. Si hay múltiples módulos sin comunicación o códigos en varios sistemas, analiza primero alimentaciones y tierras compartidas o redes de comunicación antes de asumir fallas en módulos o componentes individuales.
4. Razona paso a paso como un técnico y sugiere la prueba eléctrica o física más lógica para descartar o confirmar hipótesis.
5. Mantén una lógica de árbol de diagnóstico dinámico.
"""

# Formularios de entrada de datos
col1, col2 = st.columns(2)

with col1:
    reporte_ediag = st.text_area("📋 Pega aquí el reporte completo de Ediag:", height=250)

with col2:
    sintomas = st.text_area("🔧 Describe los síntomas observados y pruebas previas:", height=250)

if st.button("🔍 Analizar Caso"):
    if not api_key:
        st.error("Por favor ingresa tu API Key en la barra lateral izquierda.")
    elif not reporte_ediag:
        st.warning("Por favor pega un reporte de Ediag para analizar.")
    else:
        try:
            client = genai.Client(api_key=api_key)
            
            prompt = f"""
            Analiza el siguiente caso de diagnóstico automotriz:
            
            --- REPORTE EDIAG ---
            {reporte_ediag}
            
            --- SÍNTOMAS Y NOTAS DEL TÉCNICO ---
            {sintomas}
            """
            
            with st.spinner("Analizando causas raíz y diagramas lógicos..."):
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt,
                    config={'system_instruction': SYSTEM_INSTRUCTION}
                )
                
                st.subheader("💡 Diagnóstico y Razonamiento de Causa Raíz")
                st.markdown(response.text)
                
        except Exception as e:
            st.error(f"Ocurrió un error al procesar el análisis: {e}")
