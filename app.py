import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime

st.set_page_config(
    page_title="IA Diagnóstico Automotriz",
    page_icon="🚗",
    layout="wide"
)

# ============================================================
# BASE DE DATOS - MEMORIA DEL TALLER
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


# Crear base de datos al iniciar
conectar_db()


# ============================================================
# CONFIGURACIÓN DE GEMINI
# ============================================================

api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    with st.sidebar:
        st.warning("⚠️ No se encontró la API Key en los Secrets de Streamlit.")
        api_key = st.text_input(
            "Ingresa tu Gemini API Key manualmente:",
            type="password"
        )
