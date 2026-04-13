import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN DE USUARIOS ---
USUARIOS_PERMITIDOS = {
    "jorge": "1234",
    "supervisor1": "obra2026",
    "bodega": "almacen99"
}

st.set_page_config(page_title="SGO-H Móvil", layout="centered")

# --- FUNCIÓN DE BASE DE DATOS AUTOCURATIVA ---
def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Crea tabla de reportes si no existe
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    operador TEXT, tramo TEXT, actividad TEXT, 
                    avance REAL, fecha TEXT, foto TEXT)''')
    # Crea tabla de inventario si no existe
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    material TEXT, cantidad REAL)''')
    
    # Si la tabla de inventario está vacía, llenamos el stock inicial
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        materiales_iniciales = [
            ('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), 
            ('Tubo PVC 8"', 100), ('Tubo PVC 12"', 100),
            ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)
        ]
        cur.executemany("INSERT INTO inventario (material, cantidad) VALUES (?,?)", materiales_iniciales)
    
    conn.commit()
    return conn

def obtener_hora_local():
    return (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M:%S")

st.title("🚧 SGO-H: Supervisión")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("Inicio de Sesión")
    user_i = st.text_input("Usuario")
    pass_i = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if user_i in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[user_i] == pass_i:
            st.session_state.autenticado = True
            st.session_state.usuario_actual = user_i
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
else:
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"])
    
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

    # --- LÓGICA DE LAS SECCIONES ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        ope = st.text_input("Operador", value=st.session_state.usuario_actual.capitalize())
        tra = st.text_input("Tramo", value="Tramo A")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        
        mat = "N/A"
        if act == "Tubería":
            mat = st.selectbox("Diámetro", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 8"', 'Tubo PVC 12"'])
        elif act == "Relleno": mat = "Cemento (Sacos)"
        elif act == "Armado": mat = "Varilla 1/2"

        ava = st.number_input("Cantidad/Avance", min_value=0.0, step=1.0)
        subir_f = st.checkbox("📸 Añadir foto")
        foto_b64 = ""
        if subir_f:
            foto = st.camera_input("Capturar")
            if foto: foto_b64 = base64.b64encode(foto.getvalue()).decode()

        if st.button("💾 GUARDAR", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (operador, tramo, actividad, avance, fecha, foto) VALUES (?,?,?,?,?,?)", 
                        (ope, tra, act, ava, obtener_hora_local(), foto_b64))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success("¡Guardado!")

    elif menu == "Entrada Almacén":
        st.header("📥 Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        m_sel = st.selectbox("Material:", mats)
        c_ent = st.number_input("Cantidad:", min_value=0.0)
        if st.button("➕ SUMAR", use_container_width=True):
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
        df_r = pd.read_sql_query("SELECT * FROM reportes ORDER BY id DESC", conn)
        df_i = pd.read_sql_query("SELECT * FROM inventario", conn)
        conn.close()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_r_excel = df_r.drop(columns=['foto']) if 'foto' in df_r.columns else df_r
            df_r_excel.to_excel(writer, index=False, sheet_name='Reportes')
            df_i.to_excel(writer, index=False, sheet_name='Stock')
        
        st.download_button("📥 DESCARGAR EXCEL", output.getvalue(), "Reporte_Limpio.xlsx", use_container_width=True)
        
        st.divider()
        for _, row in df_r.head(10).iterrows():
            with st.expander(f"{row['fecha']} - {row['actividad']}"):
                if row.get('foto') and len(str(row['foto'])) > 100:
                    st.image(base64.b64decode(row['foto']), use_container_width=True)