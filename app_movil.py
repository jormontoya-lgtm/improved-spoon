import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime
import base64

# Configuración de página
st.set_page_config(page_title="SGO-H Móvil", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    try:
        conn.execute("ALTER TABLE reportes ADD COLUMN fecha TEXT")
    except: pass
    try:
        conn.execute("ALTER TABLE reportes ADD COLUMN foto TEXT")
    except: pass
    return conn

st.title("🚧 SGO-H: Supervisión")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    user = st.text_input("Usuario")
    passw = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if user == "jorge" and passw == "1234":
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
else:
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Ver Inventario", "Exportar"])

    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        ope = st.text_input("Operador", value="García")
        tra = st.text_input("Tramo", value="Tramo A")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        
        mat = "N/A"
        if act == "Tubería":
            mat = st.selectbox("Diámetro", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 8"', 'Tubo PVC 12"'])
        elif act == "Relleno": mat = "Cemento (Sacos)"
        elif act == "Armado": mat = "Varilla 1/2"

        ava = st.number_input("Cantidad/Avance (m)", min_value=0.0, step=1.0)
        archivo_foto = st.camera_input("Tomar foto de la evidencia")
        
        foto_base64 = ""
        if archivo_foto:
            bytes_data = archivo_foto.getvalue()
            foto_base64 = base64.b64encode(bytes_data).decode()

        if st.button("Guardar Reporte", use_container_width=True):
            fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (operador, tramo, actividad, avance, fecha, foto) VALUES (?,?,?,?,?,?)", 
                        (ope, tra, act, ava, fecha_actual, foto_base64))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success("¡Reporte Guardado!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Bodega")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Reporte y Descarga")
        conn = conectar()
        df_reportes = pd.read_sql_query("SELECT * FROM reportes ORDER BY id DESC", conn)
        df_inv = pd.read_sql_query("SELECT * FROM inventario", conn)
        conn.close()
        
        # --- BOTÓN DE DESCARGA OPTIMIZADO PARA MÓVIL ---
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Quitamos la columna 'foto' para el Excel para que no pese y no falle el móvil
            df_excel = df_reportes.drop(columns=['foto']) if 'foto' in df_reportes.columns else df_reportes
            df_excel.to_excel(writer, index=False, sheet_name='Reportes')
            df_inv.to_excel(writer, index=False, sheet_name='Stock')
        
        st.download_button(
            label="📥 DESCARGAR EXCEL AQUÍ",
            data=output.getvalue(),
            file_name=f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        st.divider()
        st.write("### Evidencia Fotográfica")
        
        for index, row in df_reportes.iterrows():
            with st.expander(f"📅 {row['fecha']} - {row['actividad']}"):
                st.write(f"**Tramo:** {row['tramo']} | **Avance:** {row['avance']}m")
                # Verificación de foto
                foto_data = row.get('foto')
                if foto_data and len(str(foto_data)) > 100:
                    try:
                        img_bytes = base64.b64decode(foto_data)
                        st.image(img_bytes, use_container_width=True)
                    except:
                        st.info("Imagen no disponible")
                else:
                    st.caption("Sin foto de evidencia")