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
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_f))
            conn.commit(); conn.close()
            registrar_log(st.session_state.usuario_actual, f"Reporte en {tra}")
            st.success("¡Reporte guardado!")

    elif menu == "Entrada Almacén":
        st.header("📥 Entrada Almacén")
        with st.form("form_ent"):
            mat_e = st.selectbox("Material:", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 6"', 'Tubo PVC 8"', 'Tubo PVC 10"', 'Tubo PVC 12"', 'Cemento (Sacos)', 'Varilla 1/2'])
            cant_e = st.number_input("Cantidad:", min_value=0.1)
            aut_e = st.text_input("Autoriza:")
            ver_e = st.text_input("Verifica:")
            enviar_e = st.form_submit_button("REGISTRAR")
            if enviar_e:
                conn = conectar(); cur = conn.cursor()
                cur.execute("INSERT INTO entradas_almacen (fecha, material, cantidad, autoriza, verificado) VALUES (?,?,?,?,?)",
                            (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), mat_e, cant_e, aut_e, ver_e))
                cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (cant_e, mat_e))
                conn.commit(); conn.close()
                registrar_log(st.session_state.usuario_actual, f"Entrada: {cant_e} de {mat_e}")
                st.success("Stock actualizado")

    elif menu == "Ver Inventario":
        st.header("📦 Stock Actual")
        conn = conectar(); df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn); conn.close()
        
        # Alerta Stock Bajo
        bajos = df_inv[df_inv['cantidad'] < STOCK_MINIMO]
        if not bajos.empty:
            st.error("⚠️ MATERIAL BAJO MÍNIMO")
            st.markdown('<audio src="https://www.soundjay.com/buttons/beep-01a.mp3" autoplay></audio>', unsafe_allow_html=True)
        
        def resaltar(val):
            return 'background-color: #ff4b4b; color: white' if val < STOCK_MINIMO else ''
        
        st.dataframe(df_inv.style.applymap(resaltar, subset=['cantidad']), use_container_width=True)

    elif menu == "Exportar":
        st.header("📊 Exportar Datos")
        conn = conectar()
        df_r = pd.read_sql_query("SELECT * FROM reportes", conn)
        df_i = pd.read_sql_query("SELECT * FROM inventario", conn)
        df_logs = pd.read_sql_query("SELECT * FROM logs", conn)
        conn.close()

        fecha_str = obtener_hora_local().strftime("%Y-%m-%d")

        # Excel
        out_ex = BytesIO()
        with pd.ExcelWriter(out_ex, engine='openpyxl') as wr:
            df_r.drop(columns=['fotos']).to_excel(wr, index=False, sheet_name='Reportes')
            df_r[df_r['material'] != "N/A"][['fecha', 'material', 'avance', 'tramo']].to_excel(wr, index=False, sheet_name='Disposicion')
        st.download_button("📥 DESCARGAR EXCEL", out_ex.getvalue(), f"Reporte_{fecha_str}.xlsx")

        # Word Logs
        doc = Document(); doc.add_heading('Logs de Actividad', 0)
        for _, r in df_logs.iterrows(): doc.add_paragraph(f"{r['fecha']} - {r['usuario']}: {r['accion']}")
        out_wd = BytesIO(); doc.save(out_wd)
        st.download_button("📄 EXPORTAR LOGS (WORD)", out_wd.getvalue(), f"Logs_{fecha_str}.docx")