import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime
import base64 # Para manejar la foto como texto

st.set_page_config(page_title="SGO-H Móvil", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    # Aseguramos que existan las columnas de fecha y foto
    try:
        conn.execute("ALTER TABLE reportes ADD COLUMN fecha TEXT")
    except: pass
    try:
        conn.execute("ALTER TABLE reportes ADD COLUMN foto TEXT")
    except: pass
    return conn

st.title("🚧 SGO-H: Supervisión con Fotos")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    user = st.text_input("Usuario")
    passw = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if user == "jorge" and passw == "1234":
            st.session_state.autenticado = True
            st.rerun()
        else: st.error("Credenciales incorrectas")
else:
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Ver Inventario", "Exportar"])

    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        ope = st.text_input("Operador", value="García")
        tra = st.text_input("Tramo", value="Tramo A")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        
        # Lógica de materiales
        mat = "N/A"
        if act == "Tubería":
            mat = st.selectbox("Diámetro", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 8"', 'Tubo PVC 12"'])
        elif act == "Relleno": mat = "Cemento (Sacos)"
        elif act == "Armado": mat = "Varilla 1/2"

        ava = st.number_input("Cantidad/Avance (m)", min_value=0.0, step=1.0)

        # NUEVO: Botón para subir o tomar foto
        archivo_foto = st.camera_input("Tomar foto de la evidencia")
        
        foto_base64 = ""
        if archivo_foto:
            # Convertimos la foto a texto para guardarla en la BD
            bytes_data = archivo_foto.getvalue()
            foto_base64 = base64.b64encode(bytes_data).decode()

        if st.button("Guardar Reporte e Imagen"):
            fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (operador, tramo, actividad, avance, fecha, foto) VALUES (?,?,?,?,?,?)", 
                        (ope, tra, act, ava, fecha_actual, foto_base64))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success(f"¡Reporte guardado con éxito!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Bodega")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Reporte con Evidencia")
        conn = conectar()
        df_reportes = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, foto FROM reportes ORDER BY id DESC", conn)
        conn.close()
        
        for index, row in df_reportes.iterrows():
            with st.expander(f"Reporte: {row['fecha']} - {row['actividad']}"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Operador:** {row['operador']}")
                    st.write(f"**Tramo:** {row['tramo']}")
                    st.write(f"**Avance:** {row['avance']} m")
                with col2:
                    if row['foto']:
                        # Mostramos la foto guardada
                        img_data = base64.b64decode(row['foto'])
                        st.image(img_data, caption="Evidencia", use_container_width=True)
                    else:
                        st.write("Sin foto")

        # Botón de Excel (Nota: El Excel no guarda las imágenes, solo los datos)
        # ... (Aquí va la misma lógica del Excel que ya teníamos)