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
# 2. CONFIGURACIÓN DE LA API Y MODELO
# ============================================================

if "api_key" not in st.session_state:
    st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.subheader("Configuración")
    st.session_state.api_key = st.text_input("Ingresa tu Gemini API Key:", value=st.session_state.api_key, type="password")

if st.session_state.api_key:
    try:
        genai.configure(api_key=st.session_state.api_key)
        modelo_ia = genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"Error al configurar la IA: {e}")
else:
    st.warning("⚠️ Por favor ingresa tu API Key en la barra lateral izquierda para continuar.")
    st.stop()

# ============================================================
# 3. INTERFAZ DE CHAT Y PESTAÑAS
# ============================================================
st.title("🚗 Asistente Automotriz de Gadiel")

pestana_chat, pestana_confirmar, pestana_historial = st.tabs(["💬 Chat de Diagnóstico", "✅ Registrar Solución", "📚 Historial del Taller"])

with pestana_chat:
    for msg in st.session_state.mensajes:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Ajustado para que el explorador móvil acepte documentos/PDFs y fotos libremente
    archivo_adjunto = st.file_uploader(
        "📎 Adjuntar reporte (PDF o Imagen)", 
        type=["pdf", "png", "jpg", "jpeg", "application/pdf"], 
        key="uploader_chat"
    )

    if prompt := st.chat_input("Escribe tu duda o describe la falla..."):
        if not api_key:
            st.error("❌ Falta configurar la API Key.")
        else:
            texto_usuario = prompt if prompt else "Analiza el archivo adjunto."
            st.session_state.mensajes.append({"role": "user", "content": texto_usuario})
            with st.chat_message("user"):
                st.write(texto_usuario)

            try:
                with st.spinner("🧠 Analizando..."):
                    casos_reales = obtener_casos_confirmados()
                    contexto_experiencia = ""
                    if casos_reales:
                        contexto_experiencia = "\n--- EXPERIENCIA PREVIA CONFIRMADA EN ESTE TALLER ---\n"
                        for caso in casos_reales[:5]:
                            contexto_experiencia += f"- Vehículo: {caso[2]} | Síntomas: {caso[3]} | Solución Real: {caso[6]}\n"

                    contenido_envio = [f"""
                    Eres un Máster en Diagnóstico Automotriz y asistente técnico experto para Gadiel.
                    Usa esta experiencia previa del taller si es relevante:
                    {contexto_experiencia}

                    Mensaje / Reporte del usuario:
                    {texto_usuario}
                    """]

                    if archivo_adjunto is not None:
                        temp_path = f"temp_{archivo_adjunto.name}"
                        with open(temp_path, "wb") as f:
                            f.write(archivo_adjunto.getbuffer())
                        
                        archivo_subido_ia = genai.upload_file(temp_path)
                        contenido_envio.append(archivo_subido_ia)
                        
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                    respuesta = modelo_ia.generate_content(contenido_envio)
                    respuesta_texto = respuesta.text

                    st.session_state.mensajes.append({"role": "model", "content": respuesta_texto})
                    with st.chat_message("model"):
                        st.write(respuesta_texto)

                    guardar_diagnostico(
                        vehiculo="Revisar en chat",
                        reporte=texto_usuario[:500],
                        sintomas="Consulta por chat",
                        diagnostico=respuesta_texto,
                        estado="PENDIENTE"
                    )

            except Exception as e:
                st.error(f"❌ Error: {e}")

with pestana_confirmar:
    st.header("✅ Registrar Solución Confirmada")
    todos = obtener_historial()
    pendientes = [c for c in todos if c[9] == 'PENDIENTE']
    
    if not pendientes:
        st.success("🎉 No hay casos pendientes por cerrar.")
    else:
        opciones = {f"ID: {c[0]} - {c[1]}": c[0] for c in pendientes}
        sel = st.selectbox("Selecciona el caso:", list(opciones.keys()))
        cid = opciones[sel]
        
        pruebas_f = st.text_area("🔧 Pruebas físicas que hiciste:")
        sol_real = st.text_area("✔️ Solución real / Qué fallaba:")
        
        if st.button("Guardar en la Memoria del Taller"):
            if sol_real.strip():
                actualizar_caso_confirmado(cid, pruebas_f, sol_real, "Reparado")
                st.success("¡Guardado con éxito!")
                st.rerun()
            else:
                st.warning("Escribe la solución real.")

with pestana_historial:
    st.header("📚 Casos Exitosos Anteriores")
    exitos = obtener_casos_confirmados()
    if not exitos:
        st.info("Aún no hay casos confirmados.")
    else:
        for ex in exitos:
            with st.expander(f"Caso #{ex[0]} - {ex[1]}"):
                st.write(f"**Solución:** {ex[6]}")
                st.write(f"**Pruebas:** {ex[5]}")
