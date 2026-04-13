import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN DE USUARIOS ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor1": "obra2026"}

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Tabla con columna para historial de ediciones
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, avance REAL, fotos TEXT, editado TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    conn.commit()
    return conn

def obtener_hora_local():
    return (datetime.utcnow() - timedelta(hours=6))

st.title("🚧 SGO-H: Gestión de Obra")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[u] == p:
            st.session_state.autenticado = True
            st.session_state.usuario_actual = u
            st.rerun()
else:
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Editar Reporte (24h)", "Ver Inventario", "Exportar"])
    
    # --- LOGOUT Y RESET (Solo Jorge) ---
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()
    
    if st.session_state.usuario_actual == "jorge":
        if st.sidebar.button("🗑️ Resetear Datos", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("DELETE FROM reportes"); conn.commit(); conn.close()
            st.rerun()

    # --- SECCIÓN: REPORTAR ---
    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        ope = st.session_state.usuario_actual.capitalize()
        tra = st.text_input("Tramo")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        ava = st.number_input("Avance (m/pzas)", min_value=0.0)
        
        st.write("---")
        st.subheader("📸 Evidencias (Máx 5)")
        archivos = st.file_uploader("Selecciona fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if len(archivos) > 5:
            st.error("Por favor, selecciona máximo 5 imágenes.")
            archivos = archivos[:5]

        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            # Convertimos las fotos a una sola cadena de texto separada por pipes |
            fotos_list = []
            for a in archivos:
                fotos_list.append(base64.b64encode(a.getvalue()).decode())
            fotos_string = "|".join(fotos_list)
            
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, fotos, editado) VALUES (?,?,?,?,?,?,?)", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), ope, tra, act, ava, fotos_string, "Original"))
            conn.commit(); conn.close()
            st.success("Reporte guardado con éxito.")

    # --- SECCIÓN: EDITAR (Trazabilidad 24h) ---
    elif menu == "Editar Reporte (24h)":
        st.header("✏️ Corrección de Errores")
        st.info("Solo se pueden editar registros de las últimas 24 horas.")
        conn = conectar()
        limite_24h = (obtener_hora_local() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        df_edit = pd.read_sql_query(f"SELECT * FROM reportes WHERE fecha > '{limite_24h}'", conn)
        conn.close()

        if not df_edit.empty:
            seleccion = st.selectbox("Selecciona el reporte a corregir", df_edit['id'].tolist(), format_func=lambda x: f"ID: {x} - {df_edit[df_edit['id']==x]['actividad'].values[0]}")
            nuevo_ava = st.number_input("Corregir Avance", value=float(df_edit[df_edit['id']==seleccion]['avance'].values[0]))
            
            if st.button("Actualizar con Trazabilidad"):
                conn = conectar(); cur = conn.cursor()
                nota_edit = f"Editado por {st.session_state.usuario_actual} el {obtener_hora_local().strftime('%H:%M')}"
                cur.execute("UPDATE reportes SET avance = ?, editado = ? WHERE id = ?", (nuevo_ava, nota_edit, seleccion))
                conn.commit(); conn.close()
                st.warning(f"Registro actualizado. Nota: {nota_edit}")
        else:
            st.write("No hay registros recientes para editar.")

    # --- SECCIÓN: EXPORTAR ---
    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df = pd.read_sql_query("SELECT * FROM reportes ORDER BY id DESC", conn)
        conn.close()
        
        # Excel incluye la columna 'editado' para que los socios vean si algo cambió
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.drop(columns=['fotos']).to_excel(writer, index=False, sheet_name='Bitácora')
        
        st.download_button("📥 Descargar Excel con Trazabilidad", output.getvalue(), "SGO_Reporte.xlsx", use_container_width=True)

        for _, row in df.head(10).iterrows():
            with st.expander(f"{row['fecha']} - {row['actividad']} ({row['editado']})"):
                st.write(f"**Operador:** {row['operador']} | **Avance:** {row['avance']}m")
                if row['fotos']:
                    fotos = row['fotos'].split("|")
                    cols = st.columns(len(fotos))
                    for i, f in enumerate(fotos):
                        cols[i].image(base64.b64decode(f), use_container_width=True)