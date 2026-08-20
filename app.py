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
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    api_key = st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    # Usamos gemini-2.5-flash que lee texto, fotos y PDFs de manera excelente
    modelo_ia = genai.GenerativeModel('gemini-2.5-flash')

if "mensajes" not in st.session_state:
    st.session_state.mensajes = [
        {"role": "model", "content": "¡Qué tal, Gadiel! Pega aquí el reporte de tu escáner, sube una foto o escríbeme la falla del carro y te armo el plan de diagnóstico."}
    ]

# ============================================================
# 3. INTERFAZ DE CHAT DIRECTO Y PESTAÑAS SIMPLES
# ============================================================
st.title("🚗 Asistente Automotriz de Gadiel")

pestana_chat, pestana_confirmar, pestana_historial = st.tabs(["💬 Chat de Diagnóstico", "✅ Registrar Solución", "📚 Historial del Taller"])

with pestana_chat:
    # Mostramos los mensajes del chat
    for msg in st.session_state.mensajes:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Permitir adjuntar archivo (PDF o Imagen) directamente junto con el chat
    archivo_adjunto = st.file_uploader("📎 Opcional: Adjunta PDF del escáner o Foto", type=["pdf", "png", "jpg", "jpeg"], key="uploader_chat")

    # Barra de entrada estilo chat abajo
    if prompt := st.chat_input("Escribe tu duda, pega el reporte o describe la falla..."):
        if not api_key:
            st.error("❌ Falta configurar la API Key.")
        else:
            # Agregamos el mensaje del usuario a la vista
            st.session_state.mensajes.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            try:
                with st.spinner("🧠 Analizando..."):
                    # Cargar memoria de casos pasados para darle contexto a la IA
                    casos_reales = obtener_casos_confirmados()
                    contexto_experiencia = ""
                    if casos_reales:
                        contexto_experiencia = "\n--- EXPERIENCIA PREVIA CONFIRMADA EN ESTE TALLER ---\n"
                        for caso in casos_reales[:5]:
                            contexto_experiencia += f"- Vehículo: {caso[2]} | Síntomas: {caso[3]} | Solución Real: {caso[6]}\n"

                    # Construir el contenido para la IA
                    contenido_envio = [f"""
                    Eres un Máster en Diagnóstico Automotriz y asistente técnico experto para Gadiel.
                    Usa esta experiencia previa del taller si es relevante:
                    {contexto_experiencia}

                    Mensaje / Reporte del usuario:
                    {prompt}
                    """]

                    # Si adjuntó un archivo (PDF o foto), lo procesamos
                    if archivo_adjunto is not None:
                        temp_path = f"temp_{archivo_adjunto.name}"
                        with open(temp_path, "wb") as f:
                            f.write(archivo_adjunto.getbuffer())
                        
                        archivo_subido_ia = genai.upload_file(temp_path)
                        contenido_envio.append(archivo_subido_ia)
                        
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                    # Generar respuesta con el modelo
                    respuesta = modelo_ia.generate_content(contenido_envio)
                    respuesta_texto = respuesta.text

                    st.session_state.mensajes.append({"role": "model", "content": respuesta_texto})
                    with st.chat_message("model"):
                        st.write(respuesta_texto)

                    # Guardar un registro rápido en la base de datos de pendientes
                    guardar_diagnostico(
                        vehiculo="Revisar en chat",
                        reporte=prompt[:500],
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
