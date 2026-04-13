import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN DE USUARIOS ---
USUARIOS_PERMITIDOS = {"Jorge": "1234", "supervisor": "obra2026"}

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
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
            st.error("Credenciales incorrectas")
else:
    # --- MENÚ LATERAL (SIDEBAR) ---
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    
    # Selectbox de navegación
    menu = st.sidebar.selectbox("Ir a:", ["Reportar Avance", "Editar (24h)", "Ver Inventario", "Exportar"])
    
    st.sidebar.divider()
    
    # BOTÓN DE CERRAR SESIÓN (Siempre visible si estás logueado)
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
        st.rerun()

    # BOTÓN DE RESET TOTAL (Solo para Jorge)
    if st.session_state.usuario_actual == "jorge":
        st.sidebar.divider()
        if st.sidebar.button("🗑️ RESETEAR PARA JUNTA", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS reportes")
            cur.execute("DROP TABLE IF EXISTS inventario")
            conn.commit(); conn.close()
            st.sidebar.success("Base de datos eliminada.")
            st.rerun()

    # --- CONTENIDO PRINCIPAL ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        tra = st.text_input("Tramo")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        ava = st.number_input("Avance (m/pzas)", min_value=0.0, step=0.1)
        
        st.subheader("📸 Evidencias (Máx 5)")
        archivos = st.file_uploader("Subir fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            fotos_list = [base64.b64encode(a.getvalue()).decode() for a in archivos[:5]]
            fotos_string = "|".join(fotos_list)
            
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, fotos, editado) VALUES (?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual, tra, act, ava, fotos_string, "Original"))
            conn.commit(); conn.close()
            st.success("¡Reporte guardado con éxito!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Almacén")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        if df_inv.empty:
            st.info("El inventario está vacío. Usa 'Entrada Almacén' o el botón de Reset.")
        else:
            st.table(df_inv)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, editado, fotos FROM reportes ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.drop(columns=['fotos']).to_excel(writer, index=False, sheet_name='Bitácora')
            
            st.download_button("📥 DESCARGAR EXCEL", output.getvalue(), f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)

            st.divider()
            for _, row in df.head(10).iterrows():
                with st.expander(f"{row['fecha']} - {row['actividad']}"):
                    st.write(f"**Avance:** {row['avance']}m | **Trazabilidad:** {row['editado']}")
                    if row['fotos']:
                        try:
                            lista_f = row['fotos'].split("|")
                            cols = st.columns(len(lista_f))
                            for i, f_data in enumerate(lista_f):
                                cols[i].image(base64.b64decode(f_data), use_container_width=True)
                        except:
                            st.caption("No se pudieron cargar las imágenes de este registro.")
        else:
            st.write("No hay reportes registrados todavía.")