import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN DE USUARIOS ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Tabla de reportes
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, fotos TEXT, editado TEXT)''')
    # Tabla de inventario mejorada para registrar entradas con trazabilidad
    cur.execute('''CREATE TABLE IF NOT EXISTS entradas_almacen 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, material TEXT, cantidad REAL, 
                    autoriza TEXT, verificado TEXT, fotos TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        mats = [('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)]
        cur.executemany("INSERT INTO inventario (material, cantidad) VALUES (?,?)", mats)
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
    # --- MENÚ LATERAL ---
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu = st.sidebar.selectbox("Ir a:", ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"])
    
    st.sidebar.divider()
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

    if st.session_state.usuario_actual == "jorge":
        if st.sidebar.button("🗑️ RESETEAR PARA JUNTA", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS reportes")
            cur.execute("DROP TABLE IF EXISTS entradas_almacen")
            cur.execute("DROP TABLE IF EXISTS inventario")
            conn.commit(); conn.close()
            st.rerun()

    # --- SECCIÓN: ENTRADA ALMACÉN REFORZADA ---
    if menu == "Entrada Almacén":
        st.header("📥 Registro de Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        
        col1, col2 = st.columns(2)
        with col1:
            mat_sel = st.selectbox("Material:", mats)
            c_ent = st.number_input("Cantidad que ingresa:", min_value=0.0)
        with col2:
            autorizador = st.text_input("¿Quién autoriza?", placeholder="Nombre del responsable")
            verificado = st.checkbox("✅ Productos verificados y en buen estado")

        st.subheader("📸 Evidencia de Recepción (Máx 5)")
        fotos_entrada = st.file_uploader("Subir fotos de los productos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'], key="fotos_alm")
        
        if st.button("➕ REGISTRAR ENTRADA", use_container_width=True):
            if not autorizador:
                st.error("Por favor, indica quién autoriza la entrada.")
            elif not verificado:
                st.warning("Debes confirmar que los productos fueron verificados.")
            else:
                fotos_list = [base64.b64encode(a.getvalue()).decode() for a in fotos_entrada[:5]]
                fotos_string = "|".join(fotos_list)
                verif_text = "SÍ" if verificado else "NO"
                
                conn = conectar(); cur = conn.cursor()
                # Registramos el historial de la entrada
                cur.execute("INSERT INTO entradas_almacen (fecha, material, cantidad, autoriza, verificado, fotos) VALUES (?,?,?,?,?,?)",
                            (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), mat_sel, c_ent, autorizador, verif_text, fotos_string))
                # Actualizamos el stock actual
                cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (c_ent, mat_sel))
                conn.commit(); conn.close()
                st.success(f"Entrada registrada: {c_ent} unidades de {mat_sel} añadidas al stock.")

    # --- SECCIÓN: REPORTAR AVANCE ---
    elif menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        st.info(f"👷 **Operador:** {st.session_state.usuario_actual.capitalize()}")
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
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual.capitalize(), tra, act, ava, fotos_string, "Original"))
            conn.commit(); conn.close()
            st.success("¡Reporte guardado!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock Actual")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df_inv)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_r = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, editado FROM reportes ORDER BY id DESC", conn)
        df_e = pd.read_sql_query("SELECT fecha, material, cantidad, autoriza, verificado FROM entradas_almacen ORDER BY id DESC", conn)
        conn.close()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_r.to_excel(writer, index=False, sheet_name='Bitácora_Avances')
            df_e.to_excel(writer, index=False, sheet_name='Historial_Entradas')
        
        st.download_button("📥 DESCARGAR EXCEL DE CONTROL", output.getvalue(), "Control_Obra.xlsx", use_container_width=True)