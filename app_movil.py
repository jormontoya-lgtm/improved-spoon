import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import base64
from docx import Document # Necesitarás instalar: pip install python-docx

# --- CONFIGURACIÓN ---
USUARIOS_PERMITIDOS = {"Jorge": "1234", "supervisor": "obra2026"}
STOCK_MINIMO = 20 

st.set_page_config(page_title="SGO-H Pro", layout="centered")

def conectar():
    conn = sqlite3.connect("sistema_obra.db")
    cur = conn.cursor()
    # Tabla de reportes
    cur.execute('''CREATE TABLE IF NOT EXISTS reportes 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, operador TEXT, 
                    tramo TEXT, actividad TEXT, material TEXT, avance REAL, 
                    observaciones TEXT, fotos TEXT, editado TEXT)''')
    # Tabla de entradas
    cur.execute('''CREATE TABLE IF NOT EXISTS entradas_almacen 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, material TEXT, cantidad REAL, 
                    autoriza TEXT, verificado TEXT, fotos TEXT)''')
    # Tabla de inventario
    cur.execute('''CREATE TABLE IF NOT EXISTS inventario 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, material TEXT, cantidad REAL)''')
    # NUEVA: Tabla de Logs de actividad
    cur.execute('''CREATE TABLE IF NOT EXISTS logs 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, usuario TEXT, accion TEXT)''')
    
    cur.execute("SELECT COUNT(*) FROM inventario")
    if cur.fetchone()[0] == 0:
        mats = [('Tubo PVC 2"', 100), ('Tubo PVC 4"', 100), ('Tubo PVC 6"', 100), 
                ('Tubo PVC 8"', 100), ('Tubo PVC 10"', 100), ('Tubo PVC 12"', 100),
                ('Cemento (Sacos)', 100), ('Varilla 1/2', 100)]
        cur.executemany("INSERT INTO inventario (material, cantidad) VALUES (?,?)", mats)
    conn.commit()
    return conn

def registrar_log(usuario, accion):
    conn = conectar(); cur = conn.cursor()
    cur.execute("INSERT INTO logs (fecha, usuario, accion) VALUES (?,?,?)", 
                (obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S"), usuario, accion))
    conn.commit(); conn.close()

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
            registrar_log(u, "Inicio de Sesión")
            st.rerun()
else:
    st.sidebar.title(f"👤 {st.session_state.usuario_actual.capitalize()}")
    menu_opciones = ["Reportar Avance", "Entrada Almacén", "Ver Inventario", "Exportar"]
    if st.session_state.usuario_actual == "jorge":
        menu_opciones.insert(1, "Panel de Control Jorge")
    
    menu = st.sidebar.selectbox("Ir a:", menu_opciones)
    
    if st.sidebar.button("🔴 Cerrar Sesión", use_container_width=True):
        registrar_log(st.session_state.usuario_actual, "Cierre de Sesión")
        st.session_state.autenticado = False
        st.rerun()

    # --- VISTA ESPECIFICA PARA JORGE ---
    if menu == "Panel de Control Jorge":
        st.header("📋 Historial de Avances (Orden Cronológico)")
        conn = conectar()
        df_jorge = pd.read_sql_query("SELECT fecha, operador, tramo, actividad, material, avance FROM reportes ORDER BY fecha DESC", conn)
        conn.close()
        st.dataframe(df_jorge, use_container_width=True)

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
        obs = st.text_area("🗒️ Observaciones", placeholder="Detalles imprevistos...")
        archivos = st.file_uploader("📸 Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        if st.button("💾 GUARDAR REPORTE", use_container_width=True):
            f_str = "|".join([base64.b64encode(a.getvalue()).decode() for a in archivos[:5]])
            conn = conectar(); cur = conn.cursor()
            fecha_hoy = obtener_hora_local().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""INSERT INTO reportes 
                           (fecha, operador, tramo, actividad, material, avance, observaciones, fotos, editado) 
                           VALUES (?,?,?,?,?,?,?,?,?)""", 
                        (fecha_hoy, st.session_state.usuario_actual.capitalize(), tra, act, mat_f, ava, obs, f_str, "Original"))
            
            if mat_f != "N/A":
                cur.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE material = ?", (ava, mat_f))
            conn.commit(); conn.close()
            registrar_log(st.session_state.usuario_actual, f"Reporte guardado en {tra}")
            st.success("¡Reporte guardado con éxito!")

    elif menu == "Ver Inventario":
        st.header("📦 Stock Actual")
        conn = conectar()
        df_inv = pd.read_sql_query("SELECT material, cantidad FROM inventario", conn)
        conn.close()

        # --- LÓGICA DE ALERTA ---
        materiales_bajos = df_inv[df_inv['cantidad'] < STOCK_MINIMO]
        
        if not materiales_bajos.empty:
            # 1. Mostrar advertencia en rojo
            st.error(f"⚠️ ¡ATENCIÓN! Hay {len(materiales_bajos)} materiales por debajo del stock mínimo ({STOCK_MINIMO}).")
            
            # 2. Emitir sonido (HTML5 Audio)
            # Nota: Algunos navegadores bloquean el "Autoplay" si no hay interacción previa.
            sonido_url = "https://www.soundjay.com/buttons/beep-01a.mp3"
            st.markdown(f'<audio src="{sonido_url}" autoplay></audio>', unsafe_allow_html=True)

        # --- ESTILO DE TABLA ---
        def resaltar_bajo_stock(val):
            color = 'background-color: #ff4b4b; color: white' if val < STOCK_MINIMO else ''
            return color

        # Aplicamos el estilo solo a la columna 'cantidad'
        df_estilado = df_inv.style.applymap(resaltar_bajo_stock, subset=['cantidad'])
        
        st.dataframe(df_estilado, use_container_width=True)

    elif menu == "Exportar":
        st.header("📊 Reporte Maestro")
        conn = conectar()
        df_r = pd.read_sql_query("SELECT * FROM reportes ORDER BY id DESC", conn)
        df_i = pd.read_sql_query("SELECT * FROM inventario", conn)
        df_logs = pd.read_sql_query("SELECT * FROM logs ORDER BY id DESC", conn)
        conn.close()

        # 1. EXCEL CON FECHA Y DETALLE DE APLICACIÓN
        output = BytesIO()
        fecha_archivo = obtener_hora_local().strftime("%Y-%m-%d")
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_r.drop(columns=['fotos']).to_excel(writer, index=False, sheet_name='Bitácora_General')
            # Vista de disposición de material (Filtra solo lo que usó material)
            df_uso = df_r[df_r['material'] != "N/A"][['fecha', 'material', 'avance', 'tramo']]
            df_uso.to_excel(writer, index=False, sheet_name='Uso_Materiales')
            df_i.to_excel(writer, index=False, sheet_name='Stock_Actual')
        
        st.download_button(
            label="📥 DESCARGAR EXCEL",
            data=output.getvalue(),
            file_name=f"Reporte_Obra_{fecha_archivo}.xlsx",
            use_container_width=True
        )

        # 2. EXPORTAR LOGS A WORD
        st.subheader("📝 Registro de Actividad")
        doc = Document()
        doc.add_heading('Registro de Actividad de Usuarios', 0)
        table = doc.add_table(rows=1, cols=3)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Fecha'
        hdr_cells[1].text = 'Usuario'
        hdr_cells[2].text = 'Acción'

        for _, row in df_logs.iterrows():
            row_cells = table.add_row().cells
            row_cells[0].text = str(row['fecha'])
            row_cells[1].text = str(row['usuario'])
            row_cells[2].text = str(row['accion'])

        doc_io = BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        
        st.download_button(
            label="📄 EXPORTAR LOGS A WORD",
            data=doc_io,
            file_name=f"Log_Actividad_{fecha_archivo}.docx",
            use_container_width=True
        )