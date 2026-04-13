import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}
STOCK_MINIMO = 20 

st.set_page_config(page_title="SGO-H Pro: Control de Tubería", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, material TEXT, avance REAL, fotos TEXT, editado TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS entradas_almacen 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, material TEXT, cantidad REAL, 
                    autoriza TEXT, verificado TEXT, fotos TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        # Listado completo de materiales con diámetros específicos
        mats = [
            ('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), 
            ('Tubo PVC 6"', 100), ('Tubo PVC 8"', 100),
            ('Tubo PVC 10"', 100), ('Tubo PVC 12"', 100),
            ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)
        ]
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
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu = st.sidebar.selectbox("Ir a:", ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"])
    
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

    # --- SECCIÓN: REPORTAR AVANCE ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte de Obra")
        st.info(f"👷 **Operador:** {st.session_state.usuario_actual.capitalize()}")
        tra = st.text_input("Tramo / Ubicación")
        act = st.selectbox("Actividad", ["Excavación", "Instalación de Tubería", "Relleno", "Armado"])
        
        mat_f = "N/A"
        if act == "Instalación de Tubería":
            mat_f = st.selectbox("Selecciona el Diámetro:", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 6"', 'Tubo PVC 8"', 'Tubo PVC 10"', 'Tubo PVC 12"'])
        elif act == "Relleno": mat_f = "Cemento (Sacos)"
        elif act == "Armado": mat_f = "Varilla 1/2"

        ava = st.number_input("Cantidad / Metros lineales:", min_value=0.0, step=0.1)
        archivos = st.file_uploader("📸 Evidencias", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR Y DESCONTAR", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            f_str = "|".join([base64.b64encode(a.getvalue()).decode() for a in archivos[:5]])
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, material, avance, fotos, editado) VALUES (?,?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual.capitalize(), tra, act, mat_f, ava, f_str, "Original"))
            
            if mat_f != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_f))
            conn.commit(); conn.close()
            st.success(f"Reporte guardado. Se descontaron {ava}m de {mat_f}")

    # --- SECCIÓN: ENTRADA ALMACÉN ---
    elif menu == "Entrada Almacén":
        st.header("📥 Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        
        m_sel = st.selectbox("Material / Diámetro:", mats)
        c_ent = st.number_input("Cantidad que ingresa:", min_value=0.0)
        aut = st.text_input("Quién autoriza:")
        verif = st.checkbox("✅ ¿Material verificado?")
        
        if st.button("➕ REGISTRAR ENTRADA", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO entradas_almacen (fecha, material, cantidad, autoriza, verificado) VALUES (?,?,?,?,?)",
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), m_sel, c_ent, aut, "SÍ"))
            cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (c_ent, m_sel))
            conn.commit(); conn.close()
            st.success(f"Stock de {m_sel} actualizado.")

    # --- SECCIÓN: VER INVENTARIO ---
    elif menu == "Ver Inventario":
        st.header("📦 Inventario por Diámetros")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material as 'Descripción', cantidad as 'Stock Actual' FROM inventario", conn)
        conn.close()
        
        for _, row in df_inv.iterrows():
            if row['Stock Actual'] <= STOCK_MINIMO:
                st.error(f"🚨 **ALERTA DE COMPRA:** {row['Descripción']} bajo del mínimo!")
        
        st.dataframe(df_inv, use_container_width=True)

    # --- SECCIÓN: EXPORTAR ---
    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_avances = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, material, avance FROM reportes", conn)
        df_entradas = pd.read_sql_query("SELECT fecha, material, cantidad, autoriza FROM entradas_almacen", conn)
        df_stock = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_avances.to_excel(writer, index=False, sheet_name='Historial_Salidas_Obra')
            df_entradas.to_excel(writer, index=False, sheet_name='Historial_Entradas_Bodega')
            df_stock.to_excel(writer, index=False, sheet_name='STOCK_ACTUAL')
        
        st.download_button("📥 DESCARGAR REPORTE EXCEL", output.getvalue(), "Control_Total_Obra.xlsx", use_container_width=True)