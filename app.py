import streamlit as st
from google import genai
from google.genai import types
import sqlite3
from datetime import datetime

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="IA Diagnóstico Automotriz - Gadiel",
    page_icon="🚗",
    layout="wide"
)

MODEL_NAME = "gemini-3.6-flash"
DB_NAME = "memoria_taller.db"


# ============================================================
# BASE DE DATOS
# ============================================================

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


def guardar_diagnostico(
    vehiculo,
    reporte,
    sintomas,
    diagnostico,
    pruebas="",
    solucion="Pendiente de confirmación",
    resultado="",
    estado="PENDIENTE"
):
    conn = conectar_db()
    c = conn.cursor()

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        INSERT INTO historial (
            fecha,
            vehiculo,
            reporte_ediag,
            sintomas,
            diagnostico_ia,
            pruebas_realizadas,
            solucion_confirmada,
            resultado_reparacion,
            estado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fecha_actual,
        vehiculo,
        reporte,
        sintomas,
        diagnostico,
        pruebas,
        solucion,
        resultado,
        estado
    ))

    conn.commit()
    conn.close()


def obtener_historial():
    conn = conectar_db()
    c = conn.cursor()

    c.execute("""
        SELECT
            id,
            fecha,
            vehiculo,
            reporte_ediag,
            sintomas,
            diagnostico_ia,
            pruebas_realizadas,
            solucion_confirmada,
            resultado_reparacion,
            estado
        FROM historial
        ORDER BY id DESC
    """)

    datos = c.fetchall()
    conn.close()

    return datos


def obtener_casos_confirmados():
    conn = conectar_db()
    c = conn.cursor()

    c.execute("""
        SELECT
            id,
            fecha,
            vehiculo,
            sintomas,
            diagnostico_ia,
            pruebas_realizadas,
            solucion_confirmada,
            resultado_reparacion
        FROM historial
        WHERE estado = 'CONFIRMADO'
        ORDER BY id DESC
    """)

    datos = c.fetchall()
    conn.close()

    return datos


def actualizar_caso_confirmado(
    caso_id,
    pruebas,
    solucion,
    resultado
):
    conn = conectar_db()
    c = conn.cursor()

    c.execute("""
        UPDATE historial
        SET
            pruebas_realizadas = ?,
            solucion_confirmada = ?,
            resultado_reparacion = ?,
            estado = 'CONFIRMADO'
        WHERE id = ?
    """, (
        pruebas,
        solucion,
        resultado,
        caso_id
    ))

    conn.commit()
    conn.close()


conectar_db()


# ============================================================
# API GEMINI
# ============================================================

api_key = st.secrets.get("GEMINI_API_KEY", "")

if not api_key:

    with st.sidebar:
        st.warning("⚠️ No se encontró GEMINI_API_KEY.")

        api_key = st.text_input(
            "Gemini API Key",
            type="password"
        )

if api_key:

    try:
        client = genai.Client(api_key=api_key)

        api_disponible = True

    except Exception as e:

        api_disponible = False

        st.error(
            f"❌ No se pudo iniciar Gemini: {e}"
        )

else:

    api_disponible = False


# ============================================================
# SESSION STATE
# ============================================================

if "diagnostico_generado" not in st.session_state:
    st.session_state.diagnostico_generado = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "contenido_actual" not in st.session_state:
    st.session_state.contenido_actual = []

if "vehiculo_actual" not in st.session_state:
    st.session_state.vehiculo_actual = "No identificado"

if "reporte_actual" not in st.session_state:
    st.session_state.reporte_actual = ""

if "sintomas_actuales" not in st.session_state:
    st.session_state.sintomas_actuales = ""


# ============================================================
# TÍTULO
# ============================================================

st.title("🚗 Asistente de Diagnóstico Automotriz de Gadiel")

st.caption(
    "Análisis de reportes Ediag + fotografías + síntomas + "
    "experiencia real del taller"
)


# ============================================================
# PESTAÑAS
# ============================================================

tab1, tab2, tab3 = st.tabs([
    "🔍 Nuevo Diagnóstico",
    "✅ Confirmar Solución",
    "📚 Memoria del Taller"
])


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader("🔍 Nuevo Diagnóstico")

    st.write(
        "Sube el reporte del escáner, agrega fotografías si las tienes "
        "y describe los síntomas. La IA analizará todo junto."
    )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    pdf = st.file_uploader(
        "📄 Reporte del escáner en PDF",
        type=["pdf"],
        help="Puedes subir directamente el PDF generado por Ediag."
    )

    # --------------------------------------------------------
    # IMÁGENES
    # --------------------------------------------------------

    fotos = st.file_uploader(
        "📷 Fotografías del vehículo / diagnóstico",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],
        accept_multiple_files=True,
        help=(
            "Puedes subir fotos del tablero, códigos, fusibles, "
            "conectores, piezas, módulos, etc."
        )
    )

    # --------------------------------------------------------
    # TEXTO ADICIONAL
    # --------------------------------------------------------

    sintomas = st.text_area(
        "💬 Síntomas / Lo que observaste",
        height=130,
        placeholder=(
            "Ejemplo:\n"
            "- No enciende\n"
            "- El tablero no prende\n"
            "- La transmisión golpea\n"
            "- No funcionan direccionales\n"
            "- El cliente dice que empezó después de cambiar la batería"
        )
    )

    # --------------------------------------------------------
    # REPORTE MANUAL OPCIONAL
    # --------------------------------------------------------

    with st.expander(
        "📝 Opcional: pegar reporte manualmente"
    ):

        reporte_manual = st.text_area(
            "Reporte del escáner",
            height=180,
            placeholder=(
                "Si no tienes el PDF, también puedes pegar aquí "
                "el reporte del Ediag."
            )
        )

    # --------------------------------------------------------
    # BOTÓN
    # --------------------------------------------------------

    if st.button(
        "🧠 Analizar y comenzar diagnóstico",
        type="primary",
        use_container_width=True
    ):

        if not api_disponible:

            st.error(
                "❌ Primero configura GEMINI_API_KEY."
            )

        elif not pdf and not reporte_manual.strip() and not fotos:

            st.warning(
                "⚠️ Sube un PDF, una foto o pega un reporte."
            )

        else:

            try:

                # ====================================================
                # CASOS REALES PREVIOS
                # ====================================================

                casos_reales = obtener_casos_confirmados()

                contexto_experiencia = ""

                if casos_reales:

                    contexto_experiencia = """
                    
--- EXPERIENCIA REAL CONFIRMADA DEL TALLER ---

Utiliza estos casos únicamente como referencia.
NO asumas que la falla actual es igual.

"""

                    for caso in casos_reales[:10]:

                        contexto_experiencia += f"""
Caso #{caso[0]}
Vehículo: {caso[2]}
Síntomas: {caso[3]}
Pruebas realizadas: {caso[5]}
Solución confirmada: {caso[6]}
Resultado: {caso[7]}

"""

                # ====================================================
                # PROMPT PRINCIPAL
                # ====================================================

                prompt = f"""

Eres un especialista MASTER en diagnóstico automotriz,
electricidad automotriz, electrónica automotriz,
CAN BUS, módulos de control, sensores, actuadores,
sistemas ABS, SRS, BCM, ECM/PCM, TCM e inmovilizadores.

Estás ayudando a un técnico automotriz llamado Gadiel.

Tu función NO es simplemente decir qué pieza cambiar.

Tu función es ayudar a encontrar la CAUSA REAL de la falla.

Analiza TODOS los elementos disponibles:

1. Reporte del escáner.
2. Códigos DTC.
3. Datos del vehículo encontrados en el reporte.
4. Síntomas escritos por el técnico.
5. Fotografías.
6. Experiencia previa confirmada del taller.

{contexto_experiencia}

--- SÍNTOMAS / OBSERVACIONES ACTUALES ---

{sintomas if sintomas.strip() else "No especificados."}


REGLAS IMPORTANTES:

- No inventes información.
- Si algo no puede determinarse, dilo claramente.
- Diferencia entre código y causa.
- Un DTC NO significa automáticamente que la pieza esté dañada.
- Considera alimentación, tierra, fusibles, relevadores,
  cableado, conectores, comunicación CAN y módulos.
- Prioriza las pruebas más rápidas y económicas.
- No recomiendes cambiar piezas sin una prueba que lo justifique.
- Si una fotografía muestra algo relevante, descríbelo.
- Si una fotografía no permite confirmar algo, dilo.
- Si hay varias causas posibles, ordénalas por probabilidad.
- Explica qué prueba puede confirmar o descartar cada causa.


ENTREGA EL DIAGNÓSTICO CON ESTA ESTRUCTURA:

# 🚗 IDENTIFICACIÓN DEL VEHÍCULO

Extrae del reporte:

- Marca
- Modelo
- Año
- Motor
- VIN
- Kilometraje

Si algún dato no aparece, indica "No encontrado".

# 🚨 PROBLEMAS PRINCIPALES

Explica los problemas más importantes encontrados.

# 🔴 CÓDIGOS IMPORTANTES

Para cada DTC:

- Código
- Módulo
- Qué significa
- Qué NO significa
- Posibles causas

# 🧠 DIAGNÓSTICO PROBABLE

Ordena las causas de mayor a menor probabilidad.

# 🔧 PLAN DE DIAGNÓSTICO

Dame pruebas concretas en orden.

Para cada prueba indica:

1. Qué revisar.
2. Dónde revisarlo.
3. Qué herramienta utilizar.
4. Qué valor o comportamiento esperar.
5. Qué significa si está bien.
6. Qué significa si está mal.

# 📷 ANÁLISIS DE FOTOGRAFÍAS

Si hay fotos:

- Explica qué observas.
- Señala posibles daños.
- Indica qué NO puede confirmarse solamente con la foto.

# ⚡ ALIMENTACIÓN Y TIERRAS

Si el problema pudiera estar relacionado con alimentación:

- Fusibles
- Relevadores
- B+
- IGN
- Tierras
- Conectores

indícalo.

# 🔌 COMUNICACIÓN

Si existen códigos de comunicación:

- Identifica los módulos involucrados.
- Considera CAN BUS.
- Explica qué comprobar primero.

# 🧪 PRUEBA MÁS IMPORTANTE

Dime cuál es la PRIMERA prueba que debería hacer el técnico
antes de comprar o cambiar una pieza.

# ⚠️ NIVEL DE CONFIRMACIÓN

Clasifica el diagnóstico como:

🟢 Alta confianza
🟡 Confianza media
🔴 Hipótesis

Explica por qué.

# 👨‍🔧 RESUMEN PARA GADIEL

Termina diciéndome exactamente:

"Empieza por ______."

y después explica el siguiente paso dependiendo del resultado.

"""


                # ====================================================
                # CONTENIDO MULTIMODAL
                # ====================================================

                contenido = []

                contenido.append(prompt)

                # PDF
                if pdf:

                    contenido.append(
                        types.Part.from_bytes(
                            data=pdf.getvalue(),
                            mime_type="application/pdf"
                        )
                    )

                # Reporte manual
                if reporte_manual.strip():

                    contenido.append(
                        f"""

--- REPORTE PEGADO MANUALMENTE ---

{reporte_manual}

"""
                    )

                # Fotos
                if fotos:

                    for foto in fotos:

                        contenido.append(
                            types.Part.from_bytes(
                                data=foto.getvalue(),
                                mime_type=foto.type
                            )
                        )


                # ====================================================
                # GEMINI
                # ====================================================

                with st.spinner(
                    "🧠 Analizando reporte, fotografías y síntomas..."
                ):

                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contenido
                    )

                diagnostico = response.text

                # ====================================================
                # GUARDAR SESIÓN
                # ====================================================

                st.session_state.diagnostico_generado = True

                st.session_state.chat_history = [
                    {
                        "role": "model",
                        "text": diagnostico
                    }
                ]

                st.session_state.contenido_actual = contenido

                st.session_state.reporte_actual = (
                    reporte_manual
                    if reporte_manual.strip()
                    else "Reporte proporcionado mediante PDF."
                )

                st.session_state.sintomas_actuales = sintomas

                # Intentar extraer identificación básica
                vehiculo_detectado = "Extraído del reporte"

                st.session_state.vehiculo_actual = vehiculo_detectado

                guardar_diagnostico(
                    vehiculo_detectado,
                    st.session_state.reporte_actual,
                    sintomas,
                    diagnostico,
                    estado="PENDIENTE"
                )

                st.success(
                    "✅ Diagnóstico generado y guardado en la memoria."
                )

            except Exception as e:

                st.error(
                    f"❌ Error durante el diagnóstico: {e}"
                )


    # ========================================================
    # MOSTRAR DIAGNÓSTICO
    # ========================================================

    if st.session_state.diagnostico_generado:

        st.markdown("---")

        st.subheader("🤖 Diagnóstico")

        if st.session_state.chat_history:

            st.markdown(
                st.session_state.chat_history[0]["text"]
            )

        # ====================================================
        # CHAT
        # ====================================================

        st.markdown("---")

        st.subheader(
            "💬 Chat técnico con la IA"
        )

        st.write(
            "Puedes seguir preguntando sobre el mismo vehículo."
        )

        for mensaje in st.session_state.chat_history:

            with st.chat_message(
                "assistant"
                if mensaje["role"] == "model"
                else "user"
            ):

                st.markdown(
                    mensaje["text"]
                )

        pregunta = st.chat_input(
            "Ej: ¿Qué debo medir primero?"
        )

        if pregunta:

            st.session_state.chat_history.append(
                {
                    "role": "user",
                    "text": pregunta
                }
            )

            try:

                # Crear historial para el chat
                historial_chat = []

                for mensaje in st.session_state.chat_history:

                    historial_chat.append(
                        types.Content(
                            role=(
                                "model"
                                if mensaje["role"] == "model"
                                else "user"
                            ),
                            parts=[
                                types.Part.from_text(
                                    text=mensaje["text"]
                                )
                            ]
                        )
                    )

                chat = client.chats.create(
                    model=MODEL_NAME,
                    history=historial_chat
                )

                respuesta = chat.send_message(
                    pregunta
                )

                st.session_state.chat_history.append(
                    {
                        "role": "model",
                        "text": respuesta.text
                    }
                )

                st.rerun()

            except Exception as e:

                st.error(
                    f"❌ Error en el chat: {e}"
                )


# ============================================================
# TAB 2
# ============================================================

with tab2:

    st.header(
        "✅ Registrar Solución Confirmada"
    )

    st.write(
        "Aquí registras lo que realmente encontraste y reparaste."
    )

    todos = obtener_historial()

    pendientes = [
        c for c in todos
        if c[9] == "PENDIENTE"
    ]

    if not pendientes:

        st.success(
            "🎉 No hay diagnósticos pendientes."
        )

    else:

        opciones = {
            f"ID {c[0]} | {c[2]} | {c[1]}": c[0]
            for c in pendientes
        }

        seleccion = st.selectbox(
            "🚗 Selecciona el caso reparado:",
            list(opciones.keys())
        )

        caso_id = opciones[seleccion]

        caso_actual = next(
            c for c in pendientes
            if c[0] == caso_id
        )

        with st.expander(
            "👁️ Ver diagnóstico que dio la IA"
        ):

            st.markdown(
                caso_actual[5]
            )

        pruebas_hechas = st.text_area(
            "🔧 Pruebas realizadas",
            placeholder=(
                "Ejemplo: Medí alimentación al BCM, "
                "revisé tierra y comprobé continuidad..."
            )
        )

        solucion_real = st.text_area(
            "✔️ Solución real / Pieza cambiada",
            placeholder=(
                "Ejemplo: Fusible F12 abierto. "
                "Se reemplazó y regresaron las funciones."
            )
        )

        resultado_final = st.selectbox(
            "🏁 Resultado final:",
            [
                "Reparado con éxito",
                "No se encontró la falla",
                "Cliente no autorizó",
                "Requiere reparación adicional"
            ]
        )

        if st.button(
            "💾 Guardar solución en la memoria",
            type="primary"
        ):

            if not solucion_real.strip():

                st.warning(
                    "⚠️ Escribe la solución real."
                )

            else:

                actualizar_caso_confirmado(
                    caso_id,
                    pruebas_hechas,
                    solucion_real,
                    resultado_final
                )

                st.success(
                    "✅ Caso confirmado y guardado."
                )

                st.rerun()


# ============================================================
# TAB 3
# ============================================================

with tab3:

    st.header(
        "📚 Memoria del Taller"
    )

    casos = obtener_casos_confirmados()

    if not casos:

        st.info(
            "Todavía no tienes reparaciones confirmadas."
        )

    else:

        st.success(
            f"🧠 Hay {len(casos)} casos confirmados "
            "en la memoria del taller."
        )

        for caso in casos:

            with st.expander(
                f"⭐ {caso[2]} — {caso[1]}"
            ):

                st.markdown(
                    f"### ✔️ Solución real\n{caso[6]}"
                )

                st.markdown(
                    f"### 🔧 Pruebas realizadas\n"
                    f"{caso[5] if caso[5] else 'No registradas'}"
                )

                st.markdown(
                    f"### 🏁 Resultado\n{caso[7]}"
                )

                st.markdown(
                    "### 🤖 Diagnóstico original de la IA"
                )

                st.markdown(
                    caso[4]
                )
