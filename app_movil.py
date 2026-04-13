import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- USUARIOS ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Estructura definitiva
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, fotos TEXT, editado TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    conn.commit()
    return conn

def obtener_hora_local():
    return (datetime.utcnow() - timedelta(hours=6))

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🚧 Acceso SGO-H")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[u] == p:
            st.session_state.autenticado = True
            st.session_state.usuario_actual = u
            st.rerun()
else:
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Editar (24h)", "Ver Inventario", "Exportar"])
    
    # BOTÓN DE RESET (Solo Jorge) - Úsalo para limpiar antes de la junta
    if st.session_state.usuario_actual == "jorge":
        st.sidebar.divider()
        if st.sidebar.button("🗑️ BORRAR TODO PARA JUNTA"):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS reportes")
            cur.execute("DROP TABLE IF EXISTS inventario")
            conn.commit(); conn.close()
            st.success("App reseteada. Recarga la página.")
            st.rerun()

    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        tra = st.text_input("Tramo")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        ava = st.number_input("Avance (m/pzas)", min_value=0.0)
        
        st.subheader("📸 Evidencias (Máx 5)")
        archivos = st.file_uploader("Subir fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR", use_container_width=True):
            fotos_list = [base64.b64encode(a.getvalue()).decode() for a in archivos[:5]]
            fotos_string = "|".join(fotos_list)
            
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, fotos, editado) VALUES (?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual, tra, act, ava, fotos_string, "Original"))
            conn.commit(); conn.close()
            st.success("¡Reporte guardado!")

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df = pd.read_sql_query("SELECT * FROM reportes ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.drop(columns=['fotos']).to_excel(writer, index=False, sheet_name='Bitácora')
            st.download_button("📥 Descargar Excel", output.getvalue(), "Reporte.xlsx", use_container_width=True)

            for _, row in df.head(10).iterrows():
                with st.expander(f"{row['fecha']} - {row['actividad']}"):
                    st.write(f"**Avance:** {row['avance']}m | **Estado:** {row['editado']}")
                    if row['fotos']:
                        # Manejo de errores para fotos viejas o vacías
                        try:
                            lista_f = row['fotos'].split("|")
                            cols = st.columns(len(lista_f))
                            for i, f_data in enumerate(lista_f):
                                if len(f_data) > 10:
                                    cols[i].image(base64.b64decode(f_data), use_container_width=True)
                        except:
                            st.warning("Error al cargar imágenes de este registro")