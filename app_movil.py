import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO

# Configuración de la página
st.set_page_config(page_title="SGO-H Móvil", layout="centered")

def conectar():
    return sqlite3.connect("sistema_obra.db")

st.title("🚧 SGO-H: Supervisión")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    user = st.text_input("Usuario")
    passw = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
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
        elif act == "Relleno":
            mat = "Cemento (Sacos)"
        elif act == "Armado":
            mat = "Varilla 1/2"

        ava = st.number_input("Cantidad/Avance (m)", min_value=0.0, step=1.0)

        if st.button("Guardar Reporte"):
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (operador, tramo, actividad, avance) VALUES (?,?,?,?)", (ope, tra, act, ava))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success(f"¡Guardado! Se descontó de {mat}")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Bodega")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Generar Reporte")
        conn = conectar()
        df_reportes = pd.read_sql_query("SELECT * FROM reportes", conn)
        conn.close()
        
        st.write("Vista previa de reportes:")
        st.dataframe(df_reportes)

        # Lógica para descargar Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_reportes.to_excel(writer, index=False, sheet_name='Reportes')
        
        st.download_button(
            label="📥 Descargar Excel de Reportes",
            data=output.getvalue(),
            file_name="reporte_obra.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        