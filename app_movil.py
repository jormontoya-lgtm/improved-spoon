import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}
st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, fotos TEXT, editado TEXT)''')
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

    # --- LÓGICA DE SECCIONES ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte de Obra")
        st.info(f"👷 **Operador:** {st.session_state.usuario_actual.capitalize()}")
        tra = st.text_input("Tramo")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        ava = st.number_input("Avance (m/pzas)", min_value=0.0, step=0.1)
        
        # Descuento automático de inventario
        mat_afectado = "N/A"
        if act == "Tubería": mat_afectado = 'Tubo PVC 4"'
        elif act == "Relleno": mat_afectado = "Cemento (Sacos)"

        archivos = st.file_uploader("📸 Fotos de evidencia (Máx 5)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            fotos_list = [base64.b64encode(a.getvalue()).decode() for a in archivos[:5]]
            fotos_string = "|".join(fotos_list)
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, fotos, editado) VALUES (?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.usuario_actual.capitalize(), tra, act, ava, fotos_string, "Original"))
            if mat_afectado != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_afectado))
            conn.commit(); conn.close()
            st.success("¡Reporte y Stock actualizados!")

    elif menu == "Entrada Almacén":
        st.header("📥 Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        
        m_sel = st.selectbox("Material:", mats)
        c_ent = st.number_input("Cantidad:", min_value=0.0)
        aut = st.text_input("¿Quién autoriza?")
        verif = st.checkbox("✅ ¿Material verificado?")
        fotos_e = st.file_uploader("📸 Foto de remisión/material", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

        if st.button("➕ REGISTRAR ENTRADA", use_container_width=True):
            f_str = "|".join([base64.b64encode(a.getvalue()).decode() for a in fotos_e[:5]])
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO entradas_almacen (fecha, material, cantidad, autoriza, verificado, fotos) VALUES (?,?,?,?,?,?)",
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), m_sel, c_ent, aut, "SÍ" if verif else "NO", f_str))
            cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (c_ent, m_sel))
            conn.commit(); conn.close()
            st.success("Entrada registrada con éxito.")

    elif menu == "Ver Inventario":
        st.header("📦 Stock Actual en Bodega")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material as 'Material', cantidad as 'Existencia' FROM inventario", conn)
        conn.close()
        st.dataframe(df_inv, use_container_width=True)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro para Socios")
        conn = conectar()
        df_r = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, editado, fotos FROM reportes ORDER BY id DESC", conn)
        df_e = pd.read_sql_query("SELECT fecha, material, cantidad, autoriza, verificado FROM entradas_almacen ORDER BY id DESC", conn)
        df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        
        # EXCEL CON 3 HOJAS (Aquí corregimos lo que faltaba)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if not df_r.empty:
                df_r.drop(columns=['fotos']).to_excel(writer, index=False, sheet_name='Bitácora_Avances')
            if not df_e.empty:
                df_e.to_excel(writer, index=False, sheet_name='Historial_Entradas')
            df_inv.to_excel(writer, index=False, sheet_name='STOCK_ACTUAL')
        
        st.download_button("📥 DESCARGAR REPORTE COMPLETO", output.getvalue(), "Control_SGO_H.xlsx", use_container_width=True)
        
        # Visualización de fotos en la App (Trazabilidad visual)
        st.divider()
        st.subheader("👁️ Vista Previa de Evidencias")
        for _, row in df_r.head(5).iterrows():
            with st.expander(f"Reporte {row['fecha']} - {row['actividad']}"):
                if row['fotos']:
                    imgs = row['fotos'].split("|")
                    c = st.columns(len(imgs))
                    for i, img in enumerate(imgs): c[i].image(base64.b64decode(img))