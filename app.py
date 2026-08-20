import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
import os

st.set_page_config(
    page_title="Asistente Automotriz - Gadiel",
    page_icon="🚗",
    layout="centered"
)

# ============================================================
# 1. BASE DE DATOS
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
# 2. CONFIGURACIÓN DE LA API Y MODELO (USANDO TU LLAVE)
# ============================================================
with st.sidebar:
    st.subheader("Configuración")
    # Borramos cualquier lectura de secretos y te pedimos la llave manualmente para evitar errores
    api_key_input = st.text_input("Ingresa tu Gemini API Key:", type="password")

if api_key_input:
    try:
        genai.configure(api_key=api_key_input)
        # Usamos el modelo 1.5-flash para máxima compatibilidad con tu llave
        modelo_ia = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Error al configurar la IA: {e}")
        st.stop()
else:
    st.warning("⚠️ Pega tu API Key en la barra lateral izquierda para continuar.")
    st.stop()

if "mensajes" not in st.session_state:
    st.session_state.mensajes = [
        {"role": "model", "content": "¡Qué tal, Gadiel! Sube tu PDF, foto o escribe la falla y te armo el plan de diagnóstico."}
    ]

# ============================================================
# 3. INTERFAZ DE CHAT
# ============================================================
st.title("🚗 Asistente Automotriz de Gadiel")

pestana_chat, pestana_confirmar, pestana_historial = st.tabs(["💬 Chat", "✅ Registrar Solución", "📚 Historial"])

with pestana_chat:
    for msg in st.session_state.mensajes:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    archivo_adjunto = st.file_uploader("📎 Adjuntar reporte (PDF o Imagen)", type=["pdf", "png", "jpg", "jpeg"])

    if prompt := st.chat_input("Escribe tu duda..."):
        st.session_state.mensajes.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        try:
            with st.spinner("🧠 Analizando..."):
                contenido_envio = [f"Eres experto en diagnóstico automotriz. Analiza esto: {prompt}"]
                
                if archivo_adjunto:
                    temp_path = f"temp_{archivo_adjunto.name}"
                    with open(temp_path, "wb") as f: f.write(archivo_adjunto.getbuffer())
                    archivo_subido = genai.upload_file(temp_path)
                    contenido_envio.append(archivo_subido)
                    os.remove(temp_path)

                respuesta = modelo_ia.generate_content(contenido_envio)
                st.session_state.mensajes.append({"role": "model", "content": respuesta.text})
                with st.chat_message("model"):
                    st.write(respuesta.text)

                guardar_diagnostico("Consulta", prompt[:100], "Chat", respuesta.text)

        except Exception as e:
            st.error(f"❌ Error al conectar con la IA: {e}")

# ... (Las secciones de pestana_confirmar y pestana_historial siguen igual que antes)
with pestana_confirmar:
    st.header("✅ Registrar Solución")
    todos = obtener_historial()
    pendientes = [c for c in todos if c[9] == 'PENDIENTE']
    if not pendientes: st.success("🎉 Todo al día.")
    else:
        opciones = {f"ID: {c[0]}": c[0] for c in pendientes}
        sel = st.selectbox("Selecciona caso:", list(opciones.keys()))
        cid = opciones[sel]
        pruebas = st.text_area("🔧 Pruebas:")
        sol = st.text_area("✔️ Solución:")
        if st.button("Guardar"):
            actualizar_caso_confirmado(cid, pruebas, sol, "Reparado")
            st.rerun()

with pestana_historial:
    st.header("📚 Casos Exitosos")
    for ex in obtener_casos_confirmados():
        with st.expander(f"Caso #{ex[0]}"):
            st.write(f"**Solución:** {ex[6]}")
