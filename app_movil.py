import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64
from docx import Document

# --- CONFIGURACIÓN ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}
STOCK_MINIMO = 20 

st.set_page_config(page_title="SGO-H Pro", layout="centered")

# --- FUNCIONES DE BASE DE DATOS Y UTILIDADES ---
def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, material TEXT, avance REAL, 
                    observaciones TEXT, fotos TEXT, editado TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS entradas_almacen 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, material TEXT, cantidad REAL, 
                    autoriza TEXT, verificado TEXT, fotos TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS logs 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, usuario TEXT, accion TEXT)''')
    
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        mats = [('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), ('Tubo PVC 6"', 100), 
                ('Tubo PVC 8"', 100), ('Tubo PVC 10"', 100), ('Tubo PVC 12"', 100),
                ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)]
        cur.executemany("INSERT INTO inventario (material, cantidad) VALUES (?,?)", mats)
    conn.commit()
    return conn

def registrar_log(usuario, accion):
    conn = conectar(); cur = conn.cursor()
    cur.execute("INSERT INTO logs (fecha, usuario, accion) VALUES (?,?,?)", 
                (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), usuario, accion))
    conn.commit(); conn.close()

def obtener_hora_local():
    return (datetime.utcnow() - timedelta(hours=6))

# --- LÓGICA DE AUTENTICACIÓN ---
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
            registrar_log(u, "Inicio de Sesión")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# --- APP PRINCIPAL (USUARIO AUTENTICADO) ---
else:
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    
    menu_opciones = ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"]
    if st.session_state.usuario_actual == "jorge":
        menu_opciones.insert(0, "Panel de Control Jorge")
    
    menu = st.sidebar.selectbox("Ir a:", menu_opciones)
    st.sidebar.divider()

    # Botón de Cerrar Sesión (Único)
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True, key="logout_main"):
        registrar_log(st.session_state.usuario_actual, "Cierre de Sesión")
        st.session_state.autenticado = False
        st.rerun()

    # Botón Resetear (Solo Jorge)
    if st.session_state.usuario_actual == "jorge":
        st.sidebar.divider()
        if st.sidebar.button("🗑️ RESETEAR PARA JUNTA", use_container_width=True, key="reset_admin"):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS reportes")
            cur.execute("DROP TABLE IF EXISTS entradas_almacen")
            cur.execute("DROP TABLE IF EXISTS inventario")
            cur.execute("DROP TABLE IF EXISTS logs")
            conn.commit(); conn.close()
            st.rerun()

    # --- NAVEGACIÓN DE SECCIONES ---

    if menu == "Panel de Control Jorge":
        st.header("📋 Historial de Avances")
        conn = conectar()
        df_jorge = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, material, avance FROM reportes ORDER BY fecha DESC", conn)
        conn.close()
        st.dataframe(df_jorge, use_container_width=True)

    elif menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte de Obra")
        st.info(f"👷 **Operador:** {st.session_state.usuario_actual.capitalize()}")
        tra = st.text_input("Tramo / Ubicación")
        act = st.selectbox("Actividad", ["Excavación", "Instalación de Tubería", "Relleno", "Armado"])
        
        mat_f = "N/A"
        if act == "Instalación de Tubería":
            mat_f = st.selectbox("Diámetro:", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 6"', 'Tubo PVC 8"', 'Tubo PVC 10"', 'Tubo PVC 12"'])
        elif act == "Relleno": mat_f = "Cemento (Sacos)"
        elif act == "Armado": mat_f = "Varilla 1/2"

        ava = st.number_input("Cantidad / Metros:", min_value=0.0, step=0.1)
        obs = st.text_area("🗒️ Observaciones")
        archivos = st.file_uploader("📸 Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            f_str = "|".join([base64.b64encode(a.getvalue()).decode() for a in archivos[:5]])
            conn = conectar(); cur = conn.cursor()
            cur.execute("""INSERT INTO reportes 
                           (fecha, operador, tramo, actividad, material, avance, observaciones, fotos, editado) 
                           VALUES (?,?,?,?,?,?,?,?,?)""", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), 
                         st.session_state.usuario_actual.capitalize(), tra, act, mat_f, ava, obs, f_str, "Original"))
            
            if mat_f != "N/A":
                cur