import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
import os

st.set_page_config(
    page_title="IA Diagnóstico Automotriz - Gadiel",
    page_icon="🚗",
    layout="wide"
)

# ============================================================
# 1. BASE DE DATOS (MEMORIA DEL TALLER)
# ============================================================

DB_NAME = "memoria_taller.db"

def conectar_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            vehiculo TEXT,
            reporte_ediag TEXT,
            sintomas TEXT,
            diagnostico_ia TEXT,
            pruebas_realizadas TEXT,
            solucion_confirmada TEXT,
            resultado_reparacion TEXT,
            estado TEXT
        )
    """)
    conn.commit()
    return conn

def guardar_diagnostico(vehiculo, reporte, sintomas, diagnostico, pruebas="", solucion="Pendiente de confirmación", resultado="", estado="PENDIENTE"):
    conn = conectar_db()
    c = conn.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO historial (fecha, vehiculo, reporte_ediag, sintomas, diagnostico_ia, pruebas_realizadas, solucion_confirmada, resultado_reparacion, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (fecha_actual, vehiculo, reporte, sintomas, diagnostico, pruebas, solucion, resultado, estado))
    conn.commit()
    conn.close()

def obtener_historial():
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT id, fecha, vehiculo, reporte_ediag, sintomas, diagnostico_ia, pruebas_realizadas, solucion_confirmada, resultado_reparacion, estado FROM historial ORDER BY id DESC")
    datos = c.fetchall()
    conn.close()
    return datos

def obtener_casos_confirmados():
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT id, fecha, vehiculo, sintomas, diagnostico_ia, pruebas_realizadas, solucion_confirmada, resultado_reparacion FROM historial WHERE estado = 'CONFIRMADO' ORDER BY id DESC")
    datos = c.fetchall()
    conn.close()
    return datos

def actualizar_caso_confirmado(caso_id, pruebas, solucion, resultado):
    conn = conectar_db()
    c = conn.cursor()
    c.execute("""
        UPDATE historial
        SET pruebas_realizadas = ?, solucion_confirmada = ?, resultado_reparacion = ?, estado = 'CONFIRMADO'
        WHERE id = ?
    """, (pruebas, solucion, resultado, caso_id))
    conn.commit()
    conn.close()

conectar_db()

# ============================================================
# 2. CONFIGURACIÓN DE LA API Y MODELO MULTIMODAL
# ============================================================

api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    with st.sidebar:
        st.warning("⚠️ No se encontró la API Key en los Secrets de Streamlit.")
        api_key = st.text_input("Ingresa tu Gemini API Key manualmente:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    # Usamos gemini-2.5-flash que procesa excelente texto, imágenes y PDFs nativamente
    modelo_ia = genai.GenerativeModel('gemini-2.5-flash')

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "diagnostico_generado" not in st.session_state:
    st.session_state.diagnostico_generado = False

# ============================================================
# 3. INTERFAZ Y PESTAÑAS
# ============================================================

st.title("🚗 Asistente de Diagnóstico Automotriz de Gadiel")

tab1, tab2, tab3 = st.tabs([
    "🔍 Nuevo Diagnóstico y Chat", 
    "✅ Confirmar Solución / Caso Real", 
    "📚 Base de Conocimientos del Taller"
])

# ------------------------------------------------------------
# PESTAÑA 1: NUEVO DIAGNÓSTICO (CON SOPORTE DE PDF E IMÁGENES)
# ------------------------------------------------------------
with tab1:
    st.write("Sube el **reporte en PDF** de tu escáner o **fotografías** (evidencias, multímetro, componentes) junto con notas para generar tu plan de diagnóstico.")
    
    vehiculo_info = st.text_input("🚗 Vehículo (Marca, Modelo, Año, Motor):", placeholder="Ej: Nissan Versa 2018 1.6L")
    
    # NUEVO: Selector de archivos para PDF o Imágenes
    archivo_subido = st.file_uploader(
        "📄 Sube el Reporte PDF del Escáner o 🖼️ Foto(s) de evidencia:",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=False
    )
    
    # Opción de texto por si quiere complementar o pegar manualmente
    reporte_texto = st.text_area("📋 O pega notas adicionales del reporte / escáner:", height=100, placeholder="Notas extra o texto opcional...")
    sintomas = st.text_area("💬 Síntomas adicionales / Notas del cliente:", height=90, placeholder="Ej: Tiembla en ralentí, pierde potencia en subidas...")

    if st.button("🔍 Analizar e Iniciar Diagnóstico", type="primary"):
        if not api_key:
            st.error("❌ Falta la API Key. Por favor verifícala en los Secrets de Streamlit.")
        elif not archivo_subido and not reporte_texto.strip():
            st.warning("⚠️ Sube al menos un archivo (PDF/Foto) o escribe el reporte para poder analizarlo.")
        else:
            try:
                with st.spinner("🧠 Procesando archivo y buscando en la memoria del taller..."):
                    # Cargar historial del taller para aprendizaje continuo
                    casos_reales = obtener_casos_confirmados()
                    contexto_experiencia = ""
                    if casos_reales:
                        contexto_experiencia = "\n--- EXPERIENCIA PREVIA CONFIRMADA EN ESTE TALLER ---\n"
                        for caso in casos_reales[:5]:
                            contexto_experiencia += f"- Vehículo: {caso[2]} | Síntomas: {caso[3]} | Solución Real: {caso[6]}\n"

                    prompt_inicial = f"""
                    Eres un Máster en Diagnóstico Automotriz y asistente técnico de taller de Gadiel.
                    Analiza el archivo adjunto (PDF del escáner y/o imágenes) y los datos proporcionados, tomando en cuenta la experiencia previa de reparaciones reales en este taller.
                    
                    {contexto_experiencia}
                    
                    --- DATOS DEL VEHÍCULO ---
                    {vehiculo_info if vehiculo_info else "Extraer del reporte o archivo si está disponible."}
                    
                    --- NOTAS / SÍNTOMAS ---
                    {sintomas if sintomas else "Ninguno reportado."}
                    {reporte_texto}
                    
                    Por favor estructura la respuesta así:
                    1. **Información del Vehículo:** Datos identificados.
                    2. **Resumen de Módulos y Códigos DTC:** Agrupados técnicamente.
                    3. **Causa Raíz Probable:** Relación entre códigos y falla real.
                    4. **Diagrama / Esquema de Pines (Texto):** Esquema de pines de sensores/actuadores involucrados.
                    5. **Plan de Pruebas con Multímetro/Osciloscopio:** Valores esperados de voltaje, resistencia y señales.
                    """

                    # Lista de contenidos para enviar al modelo multimodal
                    contenido_prompt = [prompt_inicial]

                    # Si el usuario subió un archivo, lo procesamos con genai.upload_file
                    if archivo_subido is not None:
                        # Guardamos temporalmente el archivo subido para enviarlo a la API
                        temp_path = f"temp_file_{archivo_subido.name}"
                        with open(temp_path, "wb") as f:
                            f.write(archivo_subido.getbuffer())
                        
                        # Subimos el archivo usando la utilidad de Google GenAI
                        with st.spinner("📤 Subiendo archivo a la IA..."):
                            archivo_ia = genai.upload_file(temp_path)
                            contenido_prompt.append(archivo_ia)
                        
                        # Limpiamos el archivo local temporal
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                    # Llamada a la IA con soporte multimodal
                    response = modelo_ia.generate_content(contenido_prompt)
                    
                    st.session_state.chat_history = [
                        {"role": "user", "parts": [prompt_inicial]},
                        {"role": "model", "parts": [response.text]}
                    ]
                    st.session_state.diagnostico_generado = True
                    
                    # Guardar en base de datos
                    nombre_archivo_reg = archivo_subido.name if archivo_subido else "Texto manual"
                    guardar_diagnostico(
                        vehiculo_info if vehiculo_info else "No especificado",
                        f"Archivo: {nombre_archivo_reg} | Notas: {reporte_texto}",
                        sintomas,
                        response.text,
                        estado="PENDIENTE"
                    )
                    
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo o conectar con la IA: {e}")

    # CHAT CONTINUO DE SEGUIMIENTO
    if st.session_state.diagnostico_generado:
        st.markdown("---")
        st.subheader("💬 Chat de Preguntas Técnicas y Pruebas")
        st.info("💡 Haz preguntas específicas sobre mediciones o cómo probar un sensor en particular.")

        for mensaje in st.session_state.chat_history[1:]:
            rol = "🤖 IA Técnico" if mensaje["role"] == "model" else "👨‍🔧 Tú"
            with st.chat_message(mensaje["role"]):
                st.write(f"**{rol}:**")
                for part in mensaje["parts"]:
                    if isinstance(part, str):
                        st.write(part)

        pregunta_usuario = st.chat_input("Escribe tu duda técnica aquí...")
        
        if pregunta_usuario:
            st.session_state.chat_history.append({"role": "user", "parts": [pregunta_usuario]})
            
            try:
                with st.spinner("Generando respuesta técnica..."):
                    chat_sesion = modelo_ia.start_chat(history=[
                        {"role": m["role"], "parts": [p for p in m["parts"] if isinstance(p, str)]} 
                        for m in st.session_state.chat_history[:-1]
                    ])
                    respuesta = chat_sesion.send_message(pregunta_usuario)
                    
                    st.session_state.chat_history.append({"role": "model", "parts": [respuesta.text]})
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Ocurrió un error en el chat: {e}")

# ------------------------------------------------------------
# PESTAÑA 2: CONFIRMAR LA SOLUCIÓN
# ------------------------------------------------------------
with tab2:
    st.header("✅ Registrar Solución Confirmada")
    st.write("Guarda el resultado real cuando entregues el vehículo para que la IA aprenda qué solucionó el problema.")
    
    todos_los_casos = obtener_historial()
    casos_pendientes = [c for c in todos_los_casos if c[9] == 'PENDIENTE']
    
    if not casos_pendientes:
        st.success("🎉 No hay diagnósticos pendientes por reparar.")
    else:
        opciones = {f"ID: {c[0]} | {c[2]} ({c[1]})": c[0] for c in casos_pendientes}
        seleccion = st.selectbox("Selecciona el vehículo reparado:", list(opciones.keys()))
        caso_id = opciones[seleccion]
        
        pruebas_hechas = st.text_area("🔧 Pruebas físicas realizadas:", placeholder="Ej: Se midió señal con osciloscopio y faltaba la masa de la ECU.")
        solucion_real = st.text_area("✔️ Solución Real / Pieza Cambiada:", placeholder="Ej: Se reparó línea de arnés sulfatada en el conector X1.")
        resultado_final = st.selectbox("Estado final:", ["Reparado con éxito", "Cliente no autorizó", "Falla intermitente resuelta"])
        
        if st.button("💾 Guardar Solución en la Memoria"):
            if not solucion_real.strip():
                st.warning("Escribe cuál fue la solución para que la IA la guarde.")
            else:
                actualizar_caso_confirmado(caso_id, pruebas_hechas, solucion_real, resultado_final)
                st.success("✅ ¡Caso resuelto y guardado en la memoria del taller!")
                st.rerun()

# ------------------------------------------------------------
# PESTAÑA 3: HISTORIAL DEL TALLER
# ------------------------------------------------------------
with tab3:
    st.header("📚 Historial y Aprendizaje del Taller")
    
    casos_exitosos = obtener_casos_confirmados()
    if not casos_exitosos:
        st.info("Aún no has registrado ningún caso resuelto como 'CONFIRMADO'.")
    else:
        for caso in casos_exitosos:
            with st.expander(f"⭐ CONFIRMADO: {caso[2]} - {caso[1]}"):
                st.write(f"**Síntomas:** {caso[3]}")
                st.write(f"**Pruebas Realizadas:** {caso[5]}")
                st.write(f"**Solución Confirmada:** {caso[6]}")
                st.write(f"**Resultado:** {caso[7]}")
                st.markdown("---")
                st.write("**Análisis inicial de la IA:**")
                st.markdown(caso[4])
