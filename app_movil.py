import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64

# --- CONFIGURACIÓN DE USUARIOS ---
USUARIOS_PERMITIDOS = {
    "jorge": "1234",
    "supervisor1": "obra2026",
    "bodega": "almacen99"
}

st.set_page_config(page_title="SGO-H Móvil", layout="centered")

# --- BASE DE DATOS MEJORADA ---
def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Creamos la tabla con TODAS las columnas necesarias desde el inicio
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    fecha TEXT,
                    operador TEXT, 
                    tramo TEXT, 
                    actividad TEXT, 
                    avance REAL, 
                    foto TEXT)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    material TEXT, cantidad REAL)''')
    
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        materiales_iniciales = [
            ('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), 
            ('Tubo PVC 8"', 100), ('Tubo PVC 12"', 100),
            ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)
        ]
        cur.executemany("INSERT INTO inventario (material, cantidad) VALUES (?,?)", materiales_iniciales)
    
    conn.commit()
    return conn

def obtener_hora_local():
    # Ajuste para México/Querétaro
    return (datetime.utcnow() - timedelta(hours=6)).strftime("%d/%m/%Y %H:%M:%S")

st.title("🚧 SGO-H: Supervisión")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("Inicio de Sesión")
    user_i = st.text_input("Usuario")
    pass_i = st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if user_i in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[user_i] == pass_i:
            st.session_state.autenticado = True
            st.session_state.usuario_actual = user_i
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
else:
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu = st.sidebar.selectbox("Menú", ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"])
    
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

    if menu == "Reportar Avance":
        st.header("📝 Nuevo Reporte")
        ope = st.text_input("Operador", value=st.session_state.usuario_actual.capitalize())
        tra = st.text_input("Tramo", value="Tramo A")
        act = st.selectbox("Actividad", ["Excavación", "Tubería", "Relleno", "Armado"])
        
        mat = "N/A"
        if act == "Tubería":
            mat = st.selectbox("Diámetro", ['Tubo PVC 2"', 'Tubo PVC 4"', 'Tubo PVC 8"', 'Tubo PVC 12"'])
        elif act == "Relleno": mat = "Cemento (Sacos)"
        elif act == "Armado": mat = "Varilla 1/2"

        # Cambiamos a float para que acepte decimales si es necesario
        ava = st.number_input("Cantidad/Avance (m o pzas)", min_value=0.0, step=0.1, format="%.2f")
        
        subir_f = st.checkbox("📸 Añadir foto de evidencia")
        foto_b64 = ""
        if subir_f:
            foto = st.camera_input("Capturar")
            if foto: foto_b64 = base64.b64encode(foto.getvalue()).decode()

        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            fecha_actual = obtener_hora_local()
            conn = conectar(); cur = conn.cursor()
            # Insertamos en el orden correcto de la tabla
            cur.execute("INSERT INTO reportes (fecha, operador, tramo, actividad, avance, foto) VALUES (?,?,?,?,?,?)", 
                        (fecha_actual, ope, tra, act, ava, foto_b64))
            if mat != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat))
            conn.commit(); conn.close()
            st.success(f"¡Guardado con éxito a las {fecha_actual}!")

    elif menu == "Entrada Almacén":
        st.header("📥 Entrada de Material")
        conn = conectar()
        mats = pd.read_sql_query("SELECT material FROM inventario", conn)['material'].tolist()
        conn.close()
        m_sel = st.selectbox("Material que ingresa:", mats)
        c_ent = st.number_input("Cantidad:", min_value=0.0, step=1.0)
        if st.button("➕ SUMAR AL STOCK", use_container_width=True):
            conn = conectar(); cur = conn.cursor()
            cur.execute("UPDATE inventario SET cantidad = cantidad + ? WHERE material = ?", (c_ent, m_sel))
            conn.commit(); conn.close()
            st.success("Inventario actualizado")

    elif menu == "Ver Inventario":
        st.header("📦 Stock Actual")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        st.table(df_inv)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        # Jalamos todo ordenado por el ID más reciente
        df_r = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, avance, foto FROM reportes ORDER BY id DESC", conn)
        df_i = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()
        
        # --- PREPARACIÓN DE EXCEL ---
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # En el Excel queremos ver la fecha y el avance
            if not df_r.empty:
                df_excel = df_r.drop(columns=['foto'])
                df_excel.to_excel(writer, index=False, sheet_name='Reportes Diarios')
            df_i.to_excel(writer, index=False, sheet_name='Inventario')
        
        st.download_button(
            label="📥 DESCARGAR REPORTE EXCEL",
            data=output.getvalue(),
            file_name=f"SGO_H_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        st.divider()
        st.subheader("📸 Últimos Reportes con Foto")
        for _, row in df_r.head(10).iterrows():
            with st.expander(f"{row['fecha']} - {row['actividad']} ({row['avance']}m)"):
                st.write(f"**Operador:** {row['operador']} | **Tramo:** {row['tramo']}")
                if row.get('foto') and len(str(row['foto'])) > 100:
                    st.image(base64.b64decode(row['foto']), use_container_width=True)
                else:
                    st.caption("Sin evidencia fotográfica")