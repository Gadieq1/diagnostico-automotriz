import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime

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
# 2. CONFIGURACIÓN DE LA API Y MODELO CLÁSICO
# ============================================================

api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    with st.sidebar:
        st.warning("⚠️ No se encontró la API Key en los Secrets de Streamlit.")
        api_key = st.text_input("Ingresa tu Gemini API Key manualmente:", type="password")

if api_key:
    # AQUÍ ES DONDE SE CONFIGURA Y LLAMA A LA IA OFICIALMENTE
    genai.configure(api_key=api_key)
    # Usamos gemini-2.5-flash porque es el modelo estable y rápido
    modelo_ia = genai.GenerativeModel('gemini-2.5-flash')

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "diagnostico_generado" not in st.session_state:
    st.session_state.diagnostico_generado = False

# ============================================================
# 3. INTERFAZ Y PESTAÑAS
# ============================================================

st.title("🚗 Asistente de Diagnóstico Automotriz y Memoria de Taller")

tab1, tab2, tab3 = st.tabs([
    "🔍 Nuevo Diagnóstico y Chat", 
    "✅ Confirmar Solución / Caso Real", 
    "📚 Base de Conocimientos del Taller"
])

# ------------------------------------------------------------
# PESTAÑA 1: NUEVO DIAGNÓSTICO
# ------------------------------------------------------------
with tab1:
    st.write("Pega el reporte de **Ediag**. La IA extraerá los datos, relacionará códigos y fallas y te dará un plan de diagnóstico.")
    
    vehiculo_info = st.text_input("🚗 Vehículo (Marca, Modelo, Año, Motor):", placeholder="Ej: Nissan Versa 2018 1.6L")
    reporte = st.text_area("📋 Reporte del Escáner (Ediag):", height=180, placeholder="Pega aquí el reporte completo de Ediag...")
    sintomas = st.text_area("💬 Síntomas adicionales / Notas:", height=90, placeholder="Ej: Tiembla en ralentí, pierde potencia en subidas...")

    if st.button("🔍 Analizar e Iniciar Diagnóstico", type="primary"):
        if not api_key:
            st.error("❌ Falta la API Key. Por favor verifícala en los Secrets de Streamlit.")
        elif not reporte.strip():
            st.warning("⚠️ Copia y pega un reporte del escáner para poder analizarlo.")
        else:
            try:
                # Cargar historial del taller para aprendizaje continuo
                casos_reales = obtener_casos_confirmados()
                contexto_experiencia = ""
                if casos_reales:
                    contexto_experiencia = "\n--- EXPERIENCIA PREVIA CONFIRMADA EN ESTE TALLER ---\n"
                    for caso in casos_reales[:5]:
                        contexto_experiencia += f"- Vehículo: {caso[2]} | Síntomas: {caso[3]} | Solución Real: {caso[6]}\n"

                prompt_inicial = f"""
                Eres un Máster en Diagnóstico Automotriz y asistente técnico de taller.
                Analiza el reporte del escáner tomando en cuenta la experiencia previa de reparaciones reales en este taller.
                
                {contexto_experiencia}
                
                --- DATOS DEL VEHÍCULO ---
                {vehiculo_info if vehiculo_info else "Extraer del reporte si está disponible."}
                
                --- REPORTE EDIAG ---
                {reporte}
                
                --- SÍNTOMAS ---
                {sintomas if sintomas else "Ninguno reportado."}
                
                Por favor estructura la respuesta así:
                1. **Información del Vehículo:** Datos identificados.
                2. **Resumen de Módulos y Códigos DTC:** Agrupados técnicamente.
                3. **Causa Raíz Probable:** Relación entre códigos y falla real.
                4. **Diagrama / Esquema de Pines (Texto):** Esquema de pines de sensores/actuadores involucrados.
                5. **Plan de Pruebas con Multímetro/Osciloscopio:** Valores esperados de voltaje, resistencia y señales.
                """
                
                with st.spinner("🧠 Analizando reporte y buscando en la memoria del taller..."):
                    # >>> AQUÍ ES EXACTAMENTE DONDE SE MANDA LLAMAR A LA IA <<<
                    response = modelo_ia.generate_content(prompt_inicial)
                    
                    st.session_state.chat_history = [
                        {"role": "user", "parts": [prompt_inicial]},
                        {"role": "model", "parts": [response.text]}
                    ]
                    st.session_state.diagnostico_generado = True
                    
                    guardar_diagnostico(
                        vehiculo_info if vehiculo_info else "No especificado",
                        reporte,
                        sintomas,
                        response.text,
                        estado="PENDIENTE"
                    )
                    
            except Exception as e:
                st.error(f"❌ Error al conectar con la IA: {e}")

    # CHAT CONTINUO DE SEGUIMIENTO
    if st.session_state.diagnostico_generado:
        st.markdown("---")
        st.subheader("💬 Chat de Preguntas Técnicas y Pruebas")
        st.info("💡 Haz preguntas específicas sobre mediciones o cómo probar un sensor en particular.")

        for mensaje in st.session_state.chat_history[1:]:
            rol = "🤖 IA Técnico" if mensaje["role"] == "model" else "👨‍🔧 Tú"
            with st.chat_message(mensaje["role"]):
                st.write(f"**{rol}:**")
                st.write(mensaje["parts"][0])

        pregunta_usuario = st.chat_input("Escribe tu duda técnica aquí...")
        
        if pregunta_usuario:
            st.session_state.chat_history.append({"role": "user", "parts": [pregunta_usuario]})
            
            try:
                with st.spinner("Generando respuesta técnica..."):
                    # Convertimos el historial al formato compatible con la librería clásica
                    chat_sesion = modelo_ia.start_chat(history=[
                        {"role": m["role"], "parts": m["parts"]} for m in st.session_state.chat_history[:-1]
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
