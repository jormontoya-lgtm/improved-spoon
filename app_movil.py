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
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, fotos TEXT, editado TEXT)''')
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
            st.error("Credenciales incorrectas")
else:
    # --- MENÚ LATERAL ---
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu = st.sidebar.selectbox("Ir a:", ["Reportar Avance", "Entrada Almacén", "Editar (24h)", "Ver Inventario", "Exportar"])
    
    st.sidebar.divider()
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

    if st.session_state.usuario_actual == "jorge":
        if st.sidebar.button("🗑️ RESETEAR PARA JUNTA", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS reportes")
            cur.execute("DROP TABLE IF EXISTS inventario")
            conn.commit(); conn.close()
            st.rerun()

    # --- SECCIONES ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        # Mostramos quién está reportando de forma visible
        st.info(f"👷 **Operador:** {st.session_state.usuario_actual.capitalize()}")
        
        tra = st.text_input("Tramo")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        
        mat_afectado = "N/A"
        if act == "Tubería": mat_afectado = 'Tubo PVC 4"'
        elif act == "Relleno": mat_afectado = "Cemento (Sacos)"

        ava = st.number_input("Avance (m/pzas)", min_value=0.0, step=0.1)
        
        st.subheader("📸 Evidencias (Máx 5)")
        archivos = st.file_uploader("Subir fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            fotos_list = [base64.b64encode(a.getvalue()).decode() for a in archivos[:5]]
            fotos_string = "|".join(fotos_list)
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, fotos, editado) VALUES (?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual.capitalize(), tra, act, ava, fotos_string, "Original"))
            if mat_afectado != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_afectado))
            conn.commit(); conn.close()
            st.success("¡Reporte guardado!")

    elif menu == "Entrada Almacén":
        st.header("📥 Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        m_sel = st.selectbox("Material:", mats)
        c_ent = st.number_input("Cantidad:", min_value=0.0)
        if st.button("➕ AGREGAR", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (c_ent, m_sel))
            conn.commit(); conn.close()
            st.success("Inventario actualizado")

    elif menu == "Ver Inventario":
        st.header("📦 Stock")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_r = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, editado, fotos FROM reportes ORDER BY id DESC", conn)
        conn.close()
        if not df_r.empty:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_r.drop(columns=['fotos']).to_excel(writer, index=False, sheet_name='Bitácora')
            st.download_button("📥 DESCARGAR EXCEL", output.getvalue(), "Reporte.xlsx", use_container_width=True)
            
            for _, row in df_r.head(5).iterrows():
                with st.expander(f"{row['fecha']} - {row['actividad']} ({row['operador']})"):
                    st.write(f"**Avance:** {row['avance']}m")
                    if row['fotos']:
                        try:
                            lista_f = row['fotos'].split("|")
                            cols = st.columns(len(lista_f))
                            for i, f in enumerate(lista_f): cols[i].image(base64.b64decode(f))
                        except: pass