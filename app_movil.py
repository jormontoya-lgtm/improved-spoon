import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN ---
USUARIOS_PERMITIDOS = {"jorge": "1234", "supervisor": "obra2026"}
STOCK_MINIMO = 20 

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Agregamos la columna 'observaciones' a la tabla de reportes
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, material TEXT, avance REAL, 
                    observaciones TEXT, fotos TEXT, editado TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS entradas_almacen 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, material TEXT, cantidad REAL, 
                    autoriza TEXT, verificado TEXT, fotos TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        mats = [('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), ('Tubo PVC 6"', 100), 
                ('Tubo PVC 8"', 100), ('Tubo PVC 10"', 100), ('Tubo PVC 12"', 100),
                ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)]
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

    if menu == "Reportar Avance":
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
        
        # --- NUEVO CAMPO DE OBSERVACIONES ---
        obs = st.text_area("🗒️ Observaciones o Aclaraciones", placeholder="Ej: Retraso por lluvia, cruce con fibra óptica no detectado, etc.")
        
        archivos = st.file_uploader("📸 Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            f_str = "|".join([base64.b64encode(a.getvalue()).decode() for a in archivos[:5]])
            conn = conectar(); cur = conn.cursor()
            # Guardamos las observaciones en la consulta SQL
            cur.execute("""INSERT INTO reportes 
                           (fecha, operador, tramo, actividad, material, avance, observaciones, fotos, editado) 
                           VALUES (?,?,?,?,?,?,?,?,?)""", 
                        (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), 
                         st.session_state.usuario_actual.capitalize(), tra, act, mat_f, ava, obs, f_str, "Original"))
            
            if mat_f != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_f))
            conn.commit(); conn.close()
            st.success("¡Reporte y observaciones guardados!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Tiempo Real")
        conn = conectar(); df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn); conn.close()
        st.dataframe(df_inv, use_container_width=True)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        # Incluimos observaciones en la descarga de Excel
        df_r = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, material, avance, observaciones FROM reportes ORDER BY id DESC", conn)
        df_e = pd.read_sql_query("SELECT fecha, material, cantidad, autoriza FROM entradas_almacen ORDER BY id DESC", conn)
        df_i = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()

        if df_r.empty and df_e.empty:
            st.warning("No hay datos para exportar.")
        else:
            st.markdown(f"**Generado por:** {st.session_state.usuario_actual.capitalize()}")
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_r.to_excel(writer, index=False, sheet_name='Bitácora_Con_Obs')
                df_e.to_excel(writer, index=False, sheet_name='Entradas')
                df_i.to_excel(writer, index=False, sheet_name='Inventario_Final')
            
            st.download_button("📥 DESCARGAR EXCEL COMPLETO", output.getvalue(), "Reporte_SGO_H_Final.xlsx", use_container_width=True)
            
            # Mostrar las observaciones también en la App para revisión rápida
            if not df_r.empty:
                st.subheader("👀 Revisión de Comentarios Recientes")
                for _, row in df_r.head(3).iterrows():
                    if row['observaciones']:
                        st.write(f"**{row['fecha']} ({row['operador']}):** {row['observaciones']}")
                        