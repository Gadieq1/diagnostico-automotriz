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
# 2. CONFIGURACIÓN DE LA API (FORMATO CLÁSICO QUE SÍ FUNCIONABA)
# ============================================================
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    with st.sidebar:
        api_key = st.text_input("Gemini API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    # Modelo clásico estable que acepta tu llave original
    modelo_ia = genai.GenerativeModel('gemini-3.6-flash')

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
# PESTAÑA 1: NUEVO DIAGNÓSTICO
# ------------------------------------------------------------
with tab1:
    st.write("Pega el reporte de tu escáner. La IA analizará los códigos y te dará el plan de diagnóstico.")
    
    vehiculo_info = st.text_input("🚗 Vehículo (Marca, Modelo, Año, Motor):", placeholder="Ej: Nissan Versa 2018 1.6L")
    reporte = st.text_area("📋 Reporte del Escáner:", height=180, placeholder="Pega aquí el reporte completo...")
    sintomas = st.text_area("💬 Síntomas adicionales / Notas:", height=90, placeholder="Ej: Tiembla en ralentí...")

    if st.button("🔍 Analizar e Iniciar Diagnóstico", type="primary"):
        if not api_key:
            st.error("❌ Falta la API Key.")
        elif not reporte.strip():
            st.warning("⚠️ Pega el reporte del escáner.")
        else:
            try:
                casos_reales = obtener_casos_confirmados()
                contexto_experiencia = ""
                if casos_reales:
                    contexto_experiencia = "\n--- EXPERIENCIA PREVIA CONFIRMADA EN ESTE TALLER ---\n"
                    for caso in casos_reales[:5]:
                        contexto_experiencia += f"- Vehículo: {caso[2]} | Síntomas: {caso[3]} | Solución Real: {caso[6]}\n"

                prompt_inicial = f"""
                Eres un Máster en Diagnóstico Automotriz y asistente técnico de taller.
                Analiza el reporte tomando en cuenta la experiencia previa de reparaciones reales en este taller.
                {contexto_experiencia}
                --- DATOS DEL VEHÍCULO ---
                {vehiculo_info if vehiculo_info else "Extraer del reporte."}
                --- REPORTE ---
                {reporte}
                --- SÍNTOMAS ---
                {sintomas if sintomas else "Ninguno."}
                """
                
                with st.spinner("🧠 Analizando reporte..."):
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
                    st.success("¡Diagnóstico generado con éxito!")
            except Exception as e:
                st.error(f"❌ Error al conectar con la IA: {e}")

    if st.session_state.diagnostico_generado:
        st.markdown("---")
        st.subheader("💬 Chat de Preguntas Técnicas")
        for mensaje in st.session_state.chat_history[1:]:
            rol = "🤖 IA" if mensaje["role"] == "model" else "👨‍🔧 Tú"
            with st.chat_message(mensaje["role"]):
                st.write(f"**{rol}:** {mensaje['parts'][0]}")

        pregunta_usuario = st.chat_input("Escribe tu duda técnica...")
        if pregunta_usuario:
            st.session_state.chat_history.append({"role": "user", "parts": [pregunta_usuario]})
            try:
                chat_sesion = modelo_ia.start_chat(history=[
                    {"role": m["role"], "parts": m["parts"]} for m in st.session_state.chat_history[:-1]
                ])
                respuesta = chat_sesion.send_message(pregunta_usuario)
                st.session_state.chat_history.append({"role": "model", "parts": [respuesta.text]})
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error en el chat: {e}")

# ------------------------------------------------------------
# PESTAÑA 2: CONFIRMAR LA SOLUCIÓN
# ------------------------------------------------------------
with tab2:
    st.header("✅ Registrar Solución Confirmada")
    todos = obtener_historial()
    pendientes = [c for c in todos if c[9] == 'PENDIENTE']
    if not pendientes:
        st.success("🎉 No hay diagnósticos pendientes.")
    else:
        opciones = {f"ID: {c[0]} | {c[2]}": c[0] for c in pendientes}
        seleccion = st.selectbox("Vehículo reparado:", list(opciones.keys()))
        caso_id = opciones[seleccion]
        
        pruebas_hechas = st.text_area("🔧 Pruebas realizadas:")
        solucion_real = st.text_area("✔️ Solución Real / Pieza Cambiada:")
        resultado_final = st.selectbox("Estado final:", ["Reparado con éxito", "Cliente no autorizó"])
        
        if st.button("💾 Guardar en la Memoria"):
            if solucion_real.strip():
                actualizar_caso_confirmado(caso_id, pruebas_hechas, solucion_real, resultado_final)
                st.success("¡Guardado!")
                st.rerun()

# ------------------------------------------------------------
# PESTAÑA 3: HISTORIAL
# ------------------------------------------------------------
with tab3:
    st.header("📚 Historial del Taller")
    for caso in obtener_casos_confirmados():
        with st.expander(f"⭐ {caso[2]} - {caso[1]}"):
            st.write(f"**Solución:** {caso[6]}")
