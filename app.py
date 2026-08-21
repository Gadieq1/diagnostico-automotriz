import streamlit as st
import sqlite3
from datetime import datetime
from google import genai
from google.genai import types


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="IA Diagnóstico Automotriz",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

MODEL_NAME = "gemini-3.6-flash"
DB_NAME = "memoria_taller.db"


# ============================================================
# ESTILO
# ============================================================

st.markdown("""
<style>

.main {
    background-color: #0e1117;
}

.block-container {
    max-width: 1250px;
    padding-top: 1.5rem;
}

.app-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 0;
}

.app-subtitle {
    color: #9aa4b2;
    font-size: 15px;
    margin-top: 4px;
}

.section-title {
    font-size: 22px;
    font-weight: 700;
    margin-top: 10px;
    margin-bottom: 10px;
}

.info-card {
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #303642;
    background: #171b22;
    margin-bottom: 15px;
}

.status-card {
    padding: 15px;
    border-radius: 12px;
    background: #151a21;
    border: 1px solid #303642;
}

.small-text {
    color: #9aa4b2;
    font-size: 13px;
}

div.stButton > button {
    border-radius: 10px;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# BASE DE DATOS
# ============================================================

def conectar_db():
    return sqlite3.connect(DB_NAME)


def crear_tabla():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
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
    conn.close()


crear_tabla()


# ============================================================
# MEMORIA DEL TALLER
# ============================================================

def guardar_diagnostico(
    vehiculo,
    reporte,
    sintomas,
    diagnostico
):
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historial
        (
            fecha,
            vehiculo,
            reporte_ediag,
            sintomas,
            diagnostico_ia,
            estado
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        vehiculo,
        reporte,
        sintomas,
        diagnostico,
        "Pendiente"
    ))

    conn.commit()
    conn.close()


def obtener_casos_confirmados():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            fecha,
            vehiculo,
            sintomas,
            diagnostico_ia,
            pruebas_realizadas,
            solucion_confirmada,
            resultado_reparacion
        FROM historial
        WHERE estado = 'Confirmado'
        ORDER BY id DESC
        LIMIT 20
    """)

    resultados = cursor.fetchall()
    conn.close()

    return resultados


def obtener_casos_similares(texto):
    """
    Busca casos anteriores usando palabras importantes.
    No es entrenamiento del modelo: es memoria externa
    del taller que se vuelve a enviar como contexto.
    """

    conn = conectar_db()
    cursor = conn.cursor()

    palabras = [
        p.strip(".,:;()[]").lower()
        for p in texto.split()
        if len(p.strip(".,:;()[]")) >= 4
    ]

    resultados = []

    for palabra in palabras[:12]:

        cursor.execute("""
            SELECT
                vehiculo,
                sintomas,
                diagnostico_ia,
                pruebas_realizadas,
                solucion_confirmada,
                resultado_reparacion
            FROM historial
            WHERE estado = 'Confirmado'
            AND (
                LOWER(vehiculo) LIKE ?
                OR LOWER(sintomas) LIKE ?
                OR LOWER(diagnostico_ia) LIKE ?
                OR LOWER(solucion_confirmada) LIKE ?
            )
            LIMIT 5
        """, (
            f"%{palabra}%",
            f"%{palabra}%",
            f"%{palabra}%",
            f"%{palabra}%"
        ))

        encontrados = cursor.fetchall()

        for caso in encontrados:
            if caso not in resultados:
                resultados.append(caso)

    conn.close()

    return resultados[:8]


def confirmar_caso(
    caso_id,
    pruebas,
    solucion,
    resultado
):
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE historial
        SET
            pruebas_realizadas = ?,
            solucion_confirmada = ?,
            resultado_reparacion = ?,
            estado = 'Confirmado'
        WHERE id = ?
    """, (
        pruebas,
        solucion,
        resultado,
        caso_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# GEMINI
# ============================================================

def obtener_cliente():

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = None

    if not api_key:
        st.error(
            "⚠️ No encontré GEMINI_API_KEY en Secrets."
        )
        st.stop()

    return genai.Client(api_key=api_key)


client = obtener_cliente()


# ============================================================
# PROMPT PRINCIPAL
# ============================================================

SYSTEM_PROMPT = """
Eres una IA especializada en diagnóstico automotriz para un técnico
que trabaja con escáner automotriz.

Tu función NO es simplemente decir qué pieza cambiar.

Debes ayudar al técnico a encontrar la causa real.

Analiza:

- códigos DTC
- módulos
- síntomas
- datos del reporte
- fotografías
- diagramas que el usuario proporcione
- voltajes o mediciones mencionadas
- comunicación CAN
- alimentación
- tierras
- fusibles
- relevadores
- sensores
- actuadores
- cableado
- conectores
- historial del vehículo

REGLAS IMPORTANTES:

1. Diferencia entre:
   - código registrado
   - causa probable
   - causa confirmada

2. Nunca afirmes que una pieza está dañada únicamente porque
   apareció un código relacionado con esa pieza.

3. Prioriza pruebas que permitan confirmar o descartar la causa.

4. Cuando sea posible, indica:
   - qué revisar
   - dónde medir
   - qué esperar
   - qué significa cada resultado

5. Si existe una posibilidad de problema de alimentación,
   tierra, fusible, relevador o comunicación, considérala.

6. Si el usuario proporciona una fotografía:
   analiza visualmente componentes, conectores, fusibles,
   daños, etiquetas, números de pieza y cualquier información visible.

7. Si el usuario proporciona un PDF:
   analiza el reporte completo y extrae automáticamente:
   marca, modelo, año, VIN, kilometraje, módulos y DTC.

8. NO inventes diagramas OEM.

9. Si un diagrama no fue proporcionado o verificado,
   dilo claramente.

10. Puedes crear un esquema explicativo sencillo si ayuda,
    pero debes etiquetarlo:

    "ESQUEMA EXPLICATIVO — NO ES DIAGRAMA OEM"

11. Si el usuario solicita un diagrama real de fábrica,
    indica que necesita una fuente técnica/OEM o que el usuario
    proporcione el diagrama para analizarlo.

12. Cuando tengas casos anteriores confirmados del taller,
    utilízalos como referencias, pero no los tomes como verdad
    absoluta.

FORMATO DE RESPUESTA:

## 🚗 Vehículo detectado

## 🔴 Códigos importantes

## 🧠 Qué significan realmente

## 🎯 Causas más probables

Ordena de más probable a menos probable.

## 🧪 Pruebas que yo haría

Da pasos concretos y prácticos.

## 🔌 Alimentación / tierras / comunicación

Indica si deben revisarse.

## 📐 Diagrama

Indica si se necesita un diagrama real.

Si el usuario pide un esquema explicativo,
puedes proporcionarlo en texto.

## ⚠️ No cambiaría esta pieza todavía

Indica qué pieza NO conviene reemplazar sin pruebas.

## ✅ Siguiente paso recomendado

Da la prueba que harías primero.

## 📊 Nivel de confianza

Bajo / Medio / Alto

Explica brevemente por qué.
"""


# ============================================================
# CONVERTIR ARCHIVOS PARA GEMINI
# ============================================================

def preparar_archivos(pdf, imagenes):

    partes = []

    if pdf is not None:

        pdf_bytes = pdf.getvalue()

        partes.append(
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf"
            )
        )

    if imagenes:

        for imagen in imagenes:

            partes.append(
                types.Part.from_bytes(
                    data=imagen.getvalue(),
                    mime_type=imagen.type
                )
            )

    return partes


# ============================================================
# ANALIZAR VEHÍCULO
# ============================================================

def analizar_diagnostico(
    pdf,
    imagenes,
    reporte_texto,
    sintomas
):

    contexto_usuario = f"""
SÍNTOMAS / OBSERVACIONES DEL TÉCNICO:

{sintomas}

REPORTE COPIADO MANUALMENTE:

{reporte_texto}
"""

    casos = obtener_casos_similares(
        contexto_usuario
    )

    memoria = ""

    if casos:

        memoria += """
CASOS CONFIRMADOS ANTERIORES DEL TALLER:

"""

        for i, caso in enumerate(casos, 1):

            vehiculo = caso[0]
            sintomas_caso = caso[1]
            diagnostico = caso[2]
            pruebas = caso[3]
            solucion = caso[4]
            resultado = caso[5]

            memoria += f"""
CASO {i}
Vehículo: {vehiculo}
Síntomas: {sintomas_caso}
Diagnóstico anterior: {diagnostico}
Pruebas realizadas: {pruebas}
Solución confirmada: {solucion}
Resultado: {resultado}

"""

    prompt = f"""
{SYSTEM_PROMPT}

{contexto_usuario}

{memoria}

IMPORTANTE:

El PDF y las fotografías que acompañan este mensaje
forman parte del diagnóstico.

Analízalos directamente.

Si el PDF contiene información del vehículo,
NO me pidas que vuelva a escribir marca, modelo,
año o VIN.

Extrae esos datos automáticamente.

Si hay múltiples códigos, priorízalos.

No confundas síntomas con causas confirmadas.
"""

    partes = preparar_archivos(pdf, imagenes)

    contenido = [prompt]

    contenido.extend(partes)

    respuesta = client.models.generate_content(
        model=MODEL_NAME,
        contents=contenido
    )

    return respuesta.text


# ============================================================
# ENCABEZADO
# ============================================================

st.markdown(
    '<div class="app-title">🚗 IA Diagnóstico Automotriz</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="app-subtitle">'
    'Asistente de diagnóstico para escáner, reportes, fotos y casos reales del taller'
    '</div>',
    unsafe_allow_html=True
)

st.divider()


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3 = st.tabs([
    "🔎 Nuevo diagnóstico",
    "✅ Confirmar reparación",
    "🧠 Memoria del taller"
])


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.markdown(
        '<div class="section-title">📋 Información del vehículo</div>',
        unsafe_allow_html=True
    )

    st.info(
        "💡 Ya no necesitas escribir manualmente marca, modelo o VIN. "
        "Si el PDF del Ediag contiene esos datos, la IA los extraerá."
    )

    col1, col2 = st.columns(2)

    with col1:

        pdf = st.file_uploader(
            "📄 Reporte PDF del Ediag",
            type=["pdf"],
            key="pdf_reporte"
        )

        if pdf:
            st.success(
                f"PDF cargado: {pdf.name}"
            )

    with col2:

        imagenes = st.file_uploader(
            "📷 Fotos del vehículo / componentes",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp"
            ],
            accept_multiple_files=True,
            key="imagenes"
        )

        if imagenes:

            st.success(
                f"{len(imagenes)} fotografía(s) cargada(s)"
            )

    st.markdown("### 📝 También puedes pegar información")

    reporte_texto = st.text_area(
        "Reporte o datos adicionales",
        placeholder=(
            "Si tienes texto del reporte, códigos DTC, "
            "datos del escáner, etc., puedes pegarlos aquí..."
        ),
        height=150
    )

    sintomas = st.text_area(
        "🔧 Síntomas / lo que encontró el cliente",
        placeholder=(
            "Ejemplo:\n"
            "No enciende.\n"
            "Golpea la transmisión.\n"
            "No funcionan vidrios.\n"
            "No prende tablero."
        ),
        height=120
    )

    st.markdown("### 📐 Diagramas")

    diagrama_tipo = st.selectbox(
        "¿Qué necesitas?",
        [
            "No necesito diagrama todavía",
            "Diagrama de arranque",
            "Diagrama de bomba de gasolina",
            "Diagrama de ventiladores",
            "Diagrama ABS",
            "Diagrama transmisión",
            "Diagrama BCM",
            "Diagrama CAN BUS",
            "Diagrama A/C",
            "Diagrama de vidrios eléctricos",
            "Otro"
        ]
    )

    st.caption(
        "⚠️ La IA no inventará un diagrama OEM. "
        "Si necesitas uno real de fábrica, deberá provenir de documentación "
        "técnica legítima o ser proporcionado por ti."
    )

    if st.button(
        "🚀 ANALIZAR VEHÍCULO",
        type="primary",
        use_container_width=True
    ):

        if (
            pdf is None
            and not imagenes
            and not reporte_texto.strip()
            and not sintomas.strip()
        ):

            st.warning(
                "Agrega un PDF, una foto, texto o síntomas."
            )

        else:

            with st.spinner(
                "🔎 Analizando reporte, imágenes y síntomas..."
            ):

                try:

                    resultado = analizar_diagnostico(
                        pdf,
                        imagenes,
                        reporte_texto,
                        sintomas
                    )

                    st.session_state["ultimo_diagnostico"] = resultado

                    guardar_diagnostico(
                        "Detectado automáticamente por IA",
                        reporte_texto,
                        sintomas,
                        resultado
                    )

                except Exception as e:

                    st.error(
                        f"❌ Error al analizar: {e}"
                    )

    if "ultimo_diagnostico" in st.session_state:

        st.divider()

        st.markdown(
            "## 🧠 Diagnóstico de la IA"
        )

        st.markdown(
            st.session_state["ultimo_diagnostico"]
        )

        st.divider()

        st.markdown(
            "### 💬 ¿Quieres preguntarle algo sobre este diagnóstico?"
        )

        pregunta = st.chat_input(
            "Ejemplo: ¿qué medirías primero?"
        )

        if pregunta:

            historial = st.session_state.setdefault(
                "chat_diagnostico",
                []
            )

            historial.append(
                {
                    "role": "user",
                    "content": pregunta
                }
            )

            contexto = f"""
{SYSTEM_PROMPT}

DIAGNÓSTICO ACTUAL:

{st.session_state["ultimo_diagnostico"]}

PREGUNTA DEL TÉCNICO:

{pregunta}
"""

            try:

                respuesta_chat = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=contexto
                )

                historial.append(
                    {
                        "role": "assistant",
                        "content": respuesta_chat.text
                    }
                )

                for mensaje in historial:

                    if mensaje["role"] == "user":
                        st.chat_message(
                            "user"
                        ).write(
                            mensaje["content"]
                        )

                    else:
                        st.chat_message(
                            "assistant"
                        ).write(
                            mensaje["content"]
                        )

            except Exception as e:

                st.error(
                    f"Error en el chat: {e}"
                )


# ============================================================
# TAB 2
# ============================================================

with tab2:

    st.markdown(
        "## ✅ Confirmar reparación"
    )

    st.info(
        "Aquí es donde la IA aprende de tu experiencia. "
        "Cuando confirmes qué estaba realmente dañado y cómo lo solucionaste, "
        "ese caso quedará guardado en la memoria del taller."
    )

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            fecha,
            vehiculo,
            sintomas,
            diagnostico_ia
        FROM historial
        WHERE estado = 'Pendiente'
        ORDER BY id DESC
    """)

    pendientes = cursor.fetchall()

    conn.close()

    if not pendientes:

        st.success(
            "No tienes diagnósticos pendientes de confirmar."
        )

    else:

        opciones = {}

        for caso in pendientes:

            caso_id = caso[0]

            titulo = (
                f"#{caso_id} | "
                f"{caso[2]} | "
                f"{caso[1]}"
            )

            opciones[titulo] = caso

        seleccionado = st.selectbox(
            "Selecciona el diagnóstico",
            list(opciones.keys())
        )

        caso = opciones[seleccionado]

        st.markdown("### Diagnóstico generado")

        st.markdown(caso[4])

        st.divider()

        pruebas = st.text_area(
            "🧪 ¿Qué pruebas realizaste?",
            placeholder=(
                "Ejemplo:\n"
                "Medí alimentación del módulo.\n"
                "Había 12.4 V.\n"
                "Revisé tierra.\n"
                "Probé continuidad..."
            )
        )

        solucion = st.text_area(
            "🔧 ¿Qué estaba realmente dañado?",
            placeholder=(
                "Ejemplo: fusible F23 abierto."
            )
        )

        resultado = st.text_area(
            "✅ ¿Qué ocurrió después de reparar?",
            placeholder=(
                "Ejemplo: volvió a funcionar el tablero, "
                "los vidrios y desaparecieron los códigos."
            )
        )

        if st.button(
            "💾 CONFIRMAR CASO REAL",
            type="primary",
            use_container_width=True
        ):

            confirmar_caso(
                caso[0],
                pruebas,
                solucion,
                resultado
            )

            st.success(
                "✅ Caso confirmado y guardado en la memoria del taller."
            )

            st.rerun()


# ============================================================
# TAB 3
# ============================================================

with tab3:

    st.markdown(
        "## 🧠 Memoria del taller"
    )

    st.write(
        "Aquí se muestran los casos que tú confirmaste "
        "con una reparación real."
    )

    casos = obtener_casos_confirmados()

    if not casos:

        st.info(
            "Todavía no hay casos confirmados."
        )

    else:

        for i, caso in enumerate(casos, 1):

            vehiculo = caso[1]
            sintomas = caso[2]
            diagnostico = caso[3]
            pruebas = caso[4]
            solucion = caso[5]
            resultado = caso[6]

            with st.expander(
                f"🚗 {vehiculo}"
            ):

                st.write(
                    f"**Síntomas:** {sintomas}"
                )

                st.write(
                    "**Diagnóstico:**"
                )

                st.markdown(
                    diagnostico
                )

                st.write(
                    "**Pruebas realizadas:**"
                )

                st.write(
                    pruebas
                )

                st.write(
                    "**Solución confirmada:**"
                )

                st.success(
                    solucion
                )

                st.write(
                    "**Resultado:**"
                )

                st.write(
                    resultado
                )


# ============================================================
# PIE
# ============================================================

st.divider()

st.caption(
    f"IA Diagnóstico Automotriz • Modelo: {MODEL_NAME}"
)
