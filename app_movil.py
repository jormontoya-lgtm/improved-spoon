import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="SGO-H Móvil", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    try:
        conn.execute("ALTER TABLE reportes ADD COLUMN fecha TEXT")
    except:
        pass 
    return conn

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
            fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            conn = conectar(); cur = conn.cursor()
            cur.execute("INSERT INTO reportes (operador, tramo, actividad, avance, fecha) VALUES (?,?,?,?,?)", 
                        (ope, tra, act, ava, fecha_actual))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success(f"¡Guardado el {fecha_actual}!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock en Bodega")
        conn = conectar()
        df = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df)

    elif menu == "Exportar":
        st.header("📊 Generar Reporte Completo")
        conn = conectar()
        # 1. Hoja de Reportes (ordenada por fecha)
        df_reportes = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance FROM reportes ORDER BY id DESC", conn)
        # 2. Hoja de Inventario Actual
        df_inv = pd.read_sql_query("SELECT * FROM inventario", conn)
        # 3. Hoja de Resumen de Consumo (agrupado)
        df_consumo = pd.read_sql_query("SELECT actividad, SUM(avance) as total_avance FROM reportes GROUP BY actividad", conn)
        conn.close()
        
        st.write("Vista previa de los últimos movimientos:")
        st.dataframe(df_reportes.head(10))

        # Crear el archivo Excel con múltiples hojas en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_reportes.to_excel(writer, index=False, sheet_name='Reportes Diarios')
            df_inv.to_excel(writer, index=False, sheet_name='Stock Actual')
            df_consumo.to_excel(writer, index=False, sheet_name='Resumen Consumos')
        
        st.download_button(
            label="📥 Descargar Reporte Maestro (3 Hojas)",
            data=output.getvalue(),
            file_name=f"SGO_H_Reporte_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )