import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN DE USUARIOS ---
USUARIOS_PERMITIDOS = {
    "jorge": "1234",
    "socio": "obra2026", "Julie": "123456", "Gerardo": "123456", "Diego": "123456"  # Puedes crear un usuario para ellos
}

st.set_page_config(page_title="SGO-H Móvil", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, foto TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        materiales = [('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)]
        cur.executemany("INSERT INTO inventario (material, cantidad) VALUES (?,?)", materiales)
    conn.commit()
    return conn

def obtener_hora_local():
    return (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M:%S")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🚧 SGO-H: Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[u] == p:
            st.session_state.autenticado = True
            st.session_state.usuario_actual = u
            st.rerun()
else:
    # --- MENÚ Y BOTÓN DE LIMPIEZA ---
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"])
    
    # BOTÓN DE LIMPIEZA EXCLUSIVO PARA JORGE
    if st.session_state.usuario_actual == "jorge":
        st.sidebar.divider()
        if st.sidebar.button("🗑️ RESETEAR APP (BORRAR PRUEBAS)", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DELETE FROM reportes") # Borra los 3 registros de prueba
            cur.execute("UPDATE inventario SET cantidad = 100") # Reinicia stock
            conn.commit(); conn.close()
            st.toast("✅ Aplicación reseteada para la presentación")
            st.rerun()

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
        if act == "Tubería": mat = st.selectbox("Material", ['Tubo PVC 2"', 'Tubo PVC 4"'])
        elif act == "Relleno": mat = "Cemento (Sacos)"
        ava = st.number_input("Cantidad/Avance", min_value=0.0, step=0.1)
        subir = st.checkbox("📸 Foto de evidencia")
        f_b64 = ""
        if subir:
            foto = st.camera_input("Capturar")
            if foto: f_b64 = base64.b64encode(foto.getvalue()).decode()
        
        if st.button("💾 GUARDAR", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, foto) VALUES (?,?,?,?,?,?)", 
                        (obtener_hora_local(), ope, tra, act, ava, f_b64))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success("¡Registro guardado!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock Actual")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_r = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, foto FROM reportes ORDER BY id DESC", conn)
        df_i = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if not df_r.empty:
                df_r.drop(columns=['foto']).to_excel(writer, index=False, sheet_name='Reportes')
            df_i.to_excel(writer, index=False, sheet_name='Inventario')
        
        st.download_button("📥 DESCARGAR EXCEL", output.getvalue(), f"SGO_H_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)
        
        for _, row in df_r.head(5).iterrows():
            with st.expander(f"{row['fecha']} - {row['actividad']}"):
                st.write(f"**Avance:** {row['avance']}m")
                if row['foto']: st.image(base64.b64decode(row['foto']), use_container_width=True)