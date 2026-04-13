import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}
STOCK_MINIMO = 20  # Nivel para generar alerta de compra

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Tabla de reportes (Salidas de material implícitas)
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, fotos TEXT, editado TEXT)''')
    # Tabla de entradas
    cur.execute('''CREATE TABLE IF NOT EXISTS entradas_almacen 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, material TEXT, cantidad REAL, 
                    autoriza TEXT, verificado TEXT, fotos TEXT)''')
    # Tabla de stock
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

    # --- SECCIÓN: REPORTAR AVANCE (SALIDAS) ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte (Salida de Material)")
        st.info(f"👷 **Operador:** {st.session_state.usuario_actual.capitalize()}")
        tra = st.text_input("Tramo")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        ava = st.number_input("Avance / Material usado:", min_value=0.0, step=0.1)
        
        # Lógica de qué material se gasta según la actividad
        mat_f = None
        if act == "Tubería": mat_f = 'Tubo PVC 4"'
        elif act == "Relleno": mat_f = "Cemento (Sacos)"
        elif act == "Armado": mat_f = "Varilla 1/2"

        archivos = st.file_uploader("📸 Evidencias", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR Y DESCUENTAR", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            f_str = "|".join([base64.b64encode(a.getvalue()).decode() for a in archivos[:5]])
            
            # Guardar reporte (que sirve como historial de salida)
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, fotos, editado) VALUES (?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual.capitalize(), tra, act, ava, f_str, "Original"))
            
            # Descontar del inventario
            if mat_f:
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_f))
                st.success(f"Se descontaron {ava} de {mat_f}")
            
            conn.commit(); conn.close()
            st.success("Reporte guardado con éxito.")

    elif menu == "Entrada Almacén":
        st.header("📥 Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        m_sel = st.selectbox("Material:", mats)
        c_ent = st.number_input("Cantidad:", min_value=0.0)
        aut = st.text_input("Autoriza:")
        
        if st.button("➕ REGISTRAR", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO entradas_almacen (fecha, material, cantidad, autoriza, verificado) VALUES (?,?,?,?,?)",
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), m_sel, c_ent, aut, "SÍ"))
            cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (c_ent, m_sel))
            conn.commit(); conn.close()
            st.success("Entrada registrada.")

    elif menu == "Ver Inventario":
        st.header("📦 Estado del Almacén")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material as Material, cantidad as Existencia FROM inventario", conn)
        conn.close()
        
        # Alerta visual en la App
        for _, row in df_inv.iterrows():
            if row['Existencia'] <= STOCK_MINIMO:
                st.warning(f"⚠️ **COMPRAR YA:** {row['Material']} (Solo quedan {row['Existencia']})")
        
        st.table(df_inv)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_avances = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance as cantidad_usada FROM reportes", conn)
        df_entradas = pd.read_sql_query("SELECT fecha, material, cantidad, autoriza FROM entradas_almacen", conn)
        df_stock = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        
        # Crear la alerta en el Excel
        df_stock['Estado'] = df_stock['cantidad'].apply(lambda x: 'COMPRAR' if x <= STOCK_MINIMO else 'OK')

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_avances.to_excel(writer, index=False, sheet_name='Historial_Salidas_Obra')
            df_entradas.to_excel(writer, index=False, sheet_name='Historial_Entradas_Bodega')
            df_stock.to_excel(writer, index=False, sheet_name='STOCK_ACTUAL_ALERTAS')
        
        st.download_button("📥 DESCARGAR CONTROL TOTAL", output.getvalue(), "Control_Obra_SGO.xlsx", use_container_width=True)