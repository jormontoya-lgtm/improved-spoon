import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
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

# Función para obtener la hora real de tu zona (México -6)
def obtener_hora_local():
    return (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M:%S")

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
        archivo_foto = st.camera_input("Tomar foto")
        
        foto_base64 = ""
        if archivo_foto:
            foto_base64 = base64.b64encode(archivo_foto.getvalue()).decode()

        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            fecha_local = obtener_hora_local()
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (operador, tramo, actividad, avance, fecha, foto) VALUES (?,?,?,?,?,?)", 
                        (ope, tra, act, ava, fecha_local, foto_base64))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success(f"¡Guardado correctamente a las {fecha_local}!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Bodega")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_reportes = pd.read_sql_query("SELECT * FROM reportes ORDER BY id DESC", conn)
        df_inv = pd.read_sql_query("SELECT * FROM inventario", conn)
        # Resumen de consumo
        df_consumo = pd.read_sql_query("SELECT actividad, SUM(avance) as total FROM reportes GROUP BY actividad", conn)
        conn.close()
        
        # --- GENERAR EXCEL CON 3 HOJAS ---
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Quitamos la foto para que el Excel no sea gigante y no falle el móvil
            df_rep_sin_foto = df_reportes.drop(columns=['foto']) if 'foto' in df_reportes.columns else df_reportes
            df_rep_sin_foto.to_excel(writer, index=False, sheet_name='Reportes Diarios')
            df_inv.to_excel(writer, index=False, sheet_name='Stock Actual')
            df_consumo.to_excel(writer, index=False, sheet_name='Consumo Acumulado')
        
        st.download_button(
            label="📥 DESCARGAR EXCEL (3 HOJAS)",
            data=output.getvalue(),
            file_name=f"SGO_Reporte_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        st.divider()
        st.subheader("📸 Evidencia en Sistema")
        for _, row in df_reportes.head(10).iterrows(): # Mostramos los últimos 10
            with st.expander(f"Reporte: {row['fecha']} - {row['actividad']}"):
                st.write(f"**Operador:** {row['operador']} | **Tramo:** {row['tramo']} | **Avance:** {row['avance']}m")
                if row.get('foto') and len(str(row['foto'])) > 100:
                    st.image(base64.b64decode(row['foto']), use_container_width=True)
                else:
                    st.caption("Sin foto")