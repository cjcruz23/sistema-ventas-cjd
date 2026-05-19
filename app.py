import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import tempfile
import os
import plotly.express as px
from streamlit_drawable_canvas import st_canvas 
from PIL import Image
import socket 
import requests
import urllib.parse
import json

# 1. CONFIGURACIÓN DE CONEXIÓN
URL_SUPABASE = st.secrets["URL_SUPABASE"]
KEY_SUPABASE = st.secrets["KEY_SUPABASE"]

@st.cache_resource
def init_connection():
    return create_client(URL_SUPABASE, KEY_SUPABASE)

supabase = init_connection()

st.set_page_config(page_title="Sistema CJ&D - Charles", layout="wide")

# --- CONTROL DE ESTADO ---
if 'venta_finalizada' not in st.session_state:
    st.session_state.venta_finalizada = False
if 'pdf_path' not in st.session_state:
    st.session_state.pdf_path = None
if 'recaudo_finalizado' not in st.session_state:
    st.session_state.recaudo_finalizado = False
if 'pdf_recaudo_path' not in st.session_state:
    st.session_state.pdf_recaudo_path = None

# Inicializar estados de sesión nativos
if "user_auth" not in st.session_state:
    st.session_state.user_auth = None
if "user_perfil" not in st.session_state:
    st.session_state.user_perfil = None

# ============================================================
# --- CAPA DE PERSISTENCIA NATIVA POR URL (SOLUCIÓN AL F5) ---
# ============================================================
# Si el session_state se borró por F5, verificamos si quedó el token en la URL
if st.session_state.user_auth is None and "token" in st.query_params:
    token_url = st.query_params["token"]
    try:
        # Rehidratamos el perfil consultando directamente a Supabase con el ID de la URL
        perfil_recuperado = supabase.table("perfiles").select("*, sedes(nombre)").eq("id", token_url).single().execute()
        if perfil_recuperado.data:
            st.session_state.user_auth = {"id": token_url}
            st.session_state.user_perfil = perfil_recuperado.data
    except Exception:
        # Si el token es inválido o expiró, limpiamos los parámetros
        st.query_params.clear()

# --- LÓGICA DE LOGIN ---
def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return response
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

# --- PANTALLA DE LOGIN ---
if st.session_state.user_auth is None:
    st.title("🔐 Acceso CJ&D Suministros")
    with st.form("login_form"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")
        
        if submit:
            res = login_user(email, password)
            if res and res.user:
                # Consultar perfil con el join de sedes
                try:
                    perfil = supabase.table("perfiles").select("*, sedes(nombre)").eq("id", res.user.id).single().execute()
                    
                    if perfil.data:
                        st.session_state.user_auth = {"id": res.user.id, "email": res.user.email}
                        st.session_state.user_perfil = perfil.data
                        
                        # INYECTAMOS EL TOKEN EN LA URL (Persiste al F5)
                        st.query_params["token"] = res.user.id
                        
                        st.success(f"Bienvenido, {perfil.data.get('nombre_vendedor', 'Usuario')}")
                        st.rerun()
                    else:
                        st.error("Perfil no encontrado en la base de datos de administración.")
                        st.session_state.user_auth = None
                except Exception as e:
                    st.error(f"Error al recuperar perfil: {e}")
                    st.session_state.user_auth = None
    st.stop() 

# --- VARIABLES GLOBALES DE SESIÓN (POST-LOGIN) ---
user_data = st.session_state.user_perfil

# Ajuste de nombres de variables para los bloques de negocio inferiores
es_admin = user_data.get('rol') == 'admin'
mi_sede_id = user_data.get('sede_id')
nombre_sede = user_data['sedes']['nombre'] if user_data.get('sedes') else "Sede General"

# --- INTERFAZ DE USUARIO ---
st.sidebar.markdown(f"### Perfil: {user_data.get('nombre_vendedor', 'Sin nombre')}")
st.sidebar.info(f"📍 **Sede:** {nombre_sede}")
st.sidebar.write(f"Rol: {'Administrador' if es_admin else 'Vendedor'}")

if st.sidebar.button("🚪 Cerrar Sesión"):
    # Limpiamos los parámetros de la URL de forma definitiva
    st.query_params.clear()
    
    # Limpiar estado del servidor
    st.session_state.user_auth = None
    st.session_state.user_perfil = None
    st.rerun()

st.divider()
    
# --- FUNCIONES DE APOYO ---
def generar_pdf_contrato(datos_venta, plan_pagos, cliente, id_venta, ruta_firma_cliente=None, metadatos=None):
    # --- PROCESAMIENTO AVANZADO: FILTRO DE COLOR PARA ELIMINAR FONDO GRIS ---
    ruta_limpia_cliente = None
    if ruta_firma_cliente:
        img_original = Image.open(ruta_firma_cliente).convert("RGBA")
        fondo_blanco = Image.new("RGBA", img_original.size, (255, 255, 255, 255))
        img_fusión = Image.alpha_composite(fondo_blanco, img_original).convert("L") 
        img_limpia = img_fusión.point(lambda p: 255 if p > 200 else p)
        img_final = img_limpia.convert("RGB")
        temp_limpia = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img_final.save(temp_limpia.name, "PNG")
        ruta_limpia_cliente = temp_limpia.name

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    num_pagare = 1000 + id_venta 
    fecha_hoy = datetime.now()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    fecha_texto = f"{fecha_hoy.day} días del mes de {meses[fecha_hoy.month - 1]} de {fecha_hoy.year}"

    # --- SUB-FUNCIÓN ACTUALIZADA: EVIDENCIA DEBAJO DE LA FIRMA ---
    def estampar_evidencia_digital():
        if metadatos:
            pdf.ln(2)
            pdf.set_font("Arial", 'I', 7)
            texto_evidencia = f"Evidencia Digital: IP {metadatos['ip']} | Timestamp: {metadatos['timestamp']} | ID Venta: {id_venta} | CJ&D Suministros"
            pdf.cell(0, 5, texto_evidencia, 0, 1, 'L')

    def agregar_encabezado():
        if os.path.exists("logo.png"):
            pdf.image("logo.png", x=10, y=8, w=30)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(0, 5, "SISTEMA DE GESTIÓN ADMINISTRATIVA - CJ&D", ln=True, align='R')
        pdf.ln(12)

    # --- PÁGINA 1: CONTRATO ---
    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "CONTRATO DE COMPRAVENTA CON RESERVA DE DOMINIO", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    pdf.write(5, "VENDEDOR: ")
    pdf.set_font("Arial", 'B', 10)
    pdf.write(5, "CJ&D SUMINISTROS Y SERVICIOS")
    pdf.set_font("Arial", size=10)
    pdf.write(5, f" identificada con NIT. No. 1129571083-1. COMPRADOR: {cliente['nombre'].upper()}, identificado con C.C. No. {cliente['cedula']}.\n")
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "PRIMERA. OBJETO:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"El VENDEDOR vende al COMPRADOR, y este adquiere, el siguiente artículo: {datos_venta['producto'].upper()}.")
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "SEGUNDA. PRECIO:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"El precio de venta acordado es de ${int(datos_venta['monto_total']):,} M/CTE.")
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "TERCERA. FORMA DE PAGO:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"El COMPRADOR pagará una cuota inicial de ${int(datos_venta['cuota_inicial']):,}, cancelada a la firma de este contrato. El saldo se cancelará según el plan de pagos adjunto.")
    pdf.ln(2)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.set_x(45) 
    pdf.cell(30, 7, "Cuota", 1, 0, 'C')
    pdf.cell(50, 7, "Fecha de Pago", 1, 0, 'C')
    pdf.cell(40, 7, "Valor Cuota", 1, 1, 'C')
    pdf.set_font("Arial", size=9)
    for _, fila in plan_pagos.iterrows():
        pdf.set_x(45)
        pdf.cell(30, 7, f"{fila['Cuota']}a", 1, 0, 'C')
        pdf.cell(50, 7, str(fila['Fecha Vencimiento']), 1, 0, 'C')
        pdf.cell(40, 7, f"$ {int(fila['Monto']):,}", 1, 1, 'R')
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "CUARTA. RESERVA DE DOMINIO:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, "El VENDEDOR se reserva la propiedad y el dominio del artículo descrito en la cláusula primera hasta tanto el COMPRADOR haya cancelado la totalidad del precio pactado, de conformidad con el Artículo 952 del Código de Comercio.")
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "QUINTA. UBICACIÓN Y RIESGOS:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"El artículo deberá permanecer en la dirección: {cliente['direccion'].upper()}.")
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "SEXTA. CLÁUSULA ACELERATORIA:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, "El incumplimiento dará derecho al VENDEDOR a exigir el pago total o la restitución.")
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, f"Para constancia se firma a los {fecha_texto}", ln=True, align='L')
    pdf.ln(25) 
    curr_y_firma = pdf.get_y()
    if os.path.exists("firma.png"):
        pdf.image("firma.png", x=20, y=curr_y_firma - 18, w=30)
    if ruta_limpia_cliente:
        pdf.image(ruta_limpia_cliente, x=115, y=curr_y_firma - 18, w=45) 
    pdf.cell(90, 10, "__________________________", 0, 0)
    pdf.cell(90, 10, "__________________________", 0, 1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 5, "EL VENDEDOR", 0, 0)
    pdf.cell(90, 5, "EL COMPRADOR", 0, 1)
    
    estampar_evidencia_digital() # Evidencia debajo de firmas en Hoja 1

    # --- PÁGINA 2: PAGARÉ ---
    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"PAGARÉ No. {num_pagare}", ln=True, align='L')
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"YO, {cliente['nombre'].upper()}, identificado con C.C. No. {cliente['cedula']}, DEBO Y PAGARÉ de manera incondicional a la orden de CJ&D SUMINISTROS Y SERVICIOS la suma pactada.")
    pdf.ln(30)
    curr_y_p = pdf.get_y()
    if ruta_limpia_cliente:
        pdf.image(ruta_limpia_cliente, x=20, y=curr_y_p - 18, w=45)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    pdf.rect(120, curr_y_p - 15, 25, 30) 
    pdf.set_xy(120, curr_y_p + 16)
    pdf.cell(25, 5, "HUELLA", 0, 1, 'C')
    
    pdf.set_x(10) # Reset x para alinear evidencia al margen
    estampar_evidencia_digital() # Evidencia debajo de firma/huella en Hoja 2

    # --- PÁGINA 3: CARTA DE INSTRUCCIONES ---
    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "CARTA DE INSTRUCCIONES", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, f"Yo, {cliente['nombre'].upper()}, autorizo a CJ&D SUMINISTROS Y SERVICIOS para diligenciar los espacios del PAGARÉ No. {num_pagare}.")
    pdf.ln(30)
    curr_y_c = pdf.get_y()
    if ruta_limpia_cliente:
        pdf.image(ruta_limpia_cliente, x=20, y=curr_y_c - 18, w=45)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    pdf.rect(120, curr_y_c - 15, 25, 30) 
    pdf.set_xy(120, curr_y_c + 16)
    pdf.cell(25, 5, "HUELLA", 0, 1, 'C')
    
    pdf.set_x(10) # Reset x para alinear evidencia al margen
    estampar_evidencia_digital() # Evidencia debajo de firma/huella en Hoja 3

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        return tmp.name
 
def generar_recibo_caja(cliente, monto, metodo, producto):
    recibo = FPDF()
    recibo.add_page()
    if os.path.exists("logo.png"):
        recibo.image("logo.png", x=160, y=10, w=35)
    recibo.set_font("Arial", 'B', 20)
    recibo.cell(0, 10, "RECIBO DE CAJA", ln=True, align='L')
    recibo.set_font("Arial", size=10)
    recibo.cell(0, 5, "CJ&D SUMINISTROS Y SERVICIOS", ln=True, align='L')
    recibo.ln(10)
    recibo.line(10, recibo.get_y(), 200, recibo.get_y())
    recibo.ln(10)
    datos = [
        ("FECHA:", datetime.now().strftime('%Y-%m-%d')),
        ("CLIENTE:", cliente['nombre'].upper()),
        ("IDENTIFICACIÓN:", cliente['cedula']),
        ("VALOR:", f"${int(monto):,}"),
        ("MÉTODO:", metodo),
        ("CONCEPTO:", f"Abono a: {producto.upper()}")
    ]
    for label, value in datos:
        recibo.set_font("Arial", 'B', 12)
        recibo.cell(40, 10, label, 0)
        recibo.set_font("Arial", size=12)
        recibo.cell(0, 10, value, ln=True)
    
    recibo.ln(25) 
    y_pos_inicial = recibo.get_y()
    # Ajuste tamaño firma vendedor en recibo (w=35)
    if os.path.exists("firma.png"):
        recibo.image("firma.png", x=10, y=y_pos_inicial, w=35)
    recibo.line(10, y_pos_inicial + 35, 80, y_pos_inicial + 35)
    recibo.set_font("Arial", 'B', 10)
    recibo.text(10, y_pos_inicial + 40, "Firma Autorizada - CJ&D")
 
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        recibo.output(tmp.name)
        return tmp.name

st.sidebar.title("Administración CJ&D")
menu = ["📊 Tablero de Control", "Registrar Cliente", "Nueva Venta", "Control de Cartera", "Historial de Ventas", "Gestión de Cobranza", "Configuración y Datos"]
choice = st.sidebar.selectbox("Acción", menu)

if choice != "Nueva Venta":
    st.session_state.venta_finalizada = False
    st.session_state.pdf_path = None
if choice != "Control de Cartera":
    st.session_state.recaudo_finalizado = False
    st.session_state.pdf_recaudo_path = None

if choice == "📊 Tablero de Control":
    st.header("Análisis Financiero y Auditoría de Mora")
    
    # --- AJUSTE DE SEGURIDAD EN CONSULTAS ---
    # Si es administrador, descarga todo. Si es operativo, filtra por su sede_id.
    if es_admin:
        v_res = supabase.table("ventas").select("*, sedes(nombre)").execute()
        p_res = supabase.table("plan_pagos").select("*, ventas!inner(sede_id)").execute()
    else:
        v_res = supabase.table("ventas").select("*, sedes(nombre)").eq("sede_id", mi_sede_id).execute()
        p_res = supabase.table("plan_pagos").select("*, ventas!inner(sede_id)").eq("ventas.sede_id", mi_sede_id).execute()
        
    if v_res.data and p_res.data:
        df_v = pd.DataFrame(v_res.data)
        df_p = pd.DataFrame(p_res.data)
        
        # --- CÁLCULOS ORIGINALES PRESERVADOS ---
        total_v = df_v['monto_total'].sum()
        total_costos_op = (df_v['costo_compra'].sum() + 
                           df_v['gasto_transporte'].sum() + 
                           df_v['gasto_papeleria'].sum() + 
                           df_v['gasto_otros'].sum())
        utilidad = total_v - total_costos_op
        recaudado = df_p['pagado'].sum() + df_v['cuota_inicial'].sum()
        calle = total_v - recaudado
        
        # --- INTERFAZ DE MÉTRICAS PRINCIPALES ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas Totales", f"${int(total_v):,}")
        c2.metric("Costos Totales", f"${int(total_costos_op):,}") 
        c3.metric("Capital en Calle", f"${int(calle):,}", delta_color="inverse")
        c4.metric("Efectivo Recaudado", f"${int(recaudado):,}")
        
        st.divider()
        st.metric("Utilidad Bruta Proyectada", f"${int(utilidad):,}")
        
        # --- NUEVA SECCIÓN: CONSOLIDADO DISCRIMINADO POR SEDES (SOLO PARA ADMIN) ---
        if es_admin:
            st.subheader("🏢 Consolidado y Distribución por Sedes")
            
            # Extraemos el nombre de la sede desde la relación del JSON
            df_v['Sede'] = df_v['sedes'].apply(lambda x: x['nombre'] if isinstance(x, dict) else "Sede General")
            
            # Agrupamos y discriminamos con Pandas conservando tus fórmulas exactas por fila
            df_sedes = df_v.groupby('Sede').agg(
                Ventas_Totales=('monto_total', 'sum'),
                Costo_Compra=('costo_compra', 'sum'),
                Transporte=('gasto_transporte', 'sum'),
                Papeleria=('gasto_papeleria', 'sum'),
                Otros=('gasto_otros', 'sum'),
                Iniciales=('cuota_inicial', 'sum')
            ).reset_index()
            
            # Replicamos tus ecuaciones operativas a nivel de fila agrupada
            df_sedes['Costos_Totales'] = df_sedes['Costo_Compra'] + df_sedes['Transporte'] + df_sedes['Papeleria'] + df_sedes['Otros']
            df_sedes['Utilidad_Proyectada'] = df_sedes['Ventas_Totales'] - df_sedes['Costos_Totales']
            
            # Formateo visual impecable para la auditoría del Administrador
            df_sedes_visual = df_sedes[['Sede', 'Ventas_Totales', 'Costos_Totales', 'Utilidad_Proyectada']].copy()
            for col in ['Ventas_Totales', 'Costos_Totales', 'Utilidad_Proyectada']:
                df_sedes_visual[col] = df_sedes_visual[col].apply(lambda x: f"${int(x):,}")
                
            st.dataframe(df_sedes_visual, use_container_width=True, hide_index=True)
            st.write("---")
            
        # --- GRÁFICA DE RENDIMIENTO ORIGINAL PRESERVADA ---
        st.subheader("📈 Rendimiento de Ventas Mensuales")
        df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta'])
        df_v_trend = df_v.set_index('fecha_venta').resample('ME')['monto_total'].sum().reset_index()
        df_v_trend['Mes'] = df_v_trend['fecha_venta'].dt.strftime('%B %Y')
        fig = px.line(df_v_trend, x='Mes', y='monto_total', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Inicie operaciones para visualizar estadísticas.")

elif choice == "Registrar Cliente":
    st.header("Registro de Nuevos Clientes")
    with st.form("cli_form"):
        c1, c2 = st.columns(2)
        with c1: n = st.text_input("Nombre Completo"); c_cc = st.text_input("Cédula")
        with c2: d = st.text_input("Dirección de Residencia"); t = st.text_input("Teléfono")
        if st.form_submit_button("Guardar Cliente"):
            if n and c_cc:
                
                # -------------------------------------------------------------------------
                # INYECCIÓN SOLICITADA: Extraer el ID del vendedor logueado desde el perfil
                # -------------------------------------------------------------------------
                id_del_vendedor_actual = st.session_state.user_perfil.get('id')
                
                # Se agrega 'vendedor_id' al diccionario de inserción nativo
                # Al retirar la validación previa, se permite la duplicidad int8 por vendedor
                supabase.table("clientes").insert({
                    "nombre": n, 
                    "cedula": c_cc, 
                    "direccion": d, 
                    "telefono": t,
                    "vendedor_id": id_del_vendedor_actual  # 👈 Amarre físico del cliente con el vendedor
                }).execute()
                
                st.success("Cliente guardado exitosamente.")

elif choice == "Nueva Venta":
    st.header("Generar Venta y Registro de Costos")
    # Mostrar la sede en la que se está operando
    st.info(f"Registrando venta para la sede: **{nombre_sede}**")
    
    if st.session_state.get('venta_finalizada'):
        st.success("✅ Venta registrada correctamente.")
        with open(st.session_state.pdf_path, "rb") as f:
            st.download_button("📥 DESCARGAR CONTRATO (3 PÁGINAS)", f, file_name="Contrato_Legal_CJD.pdf", type="primary")
        if st.button("Registrar Nueva Venta"):
            st.session_state.venta_finalizada = False; st.session_state.pdf_path = None; st.rerun()
    else:
        # -------------------------------------------------------------------------
        # CONTROL DE AUDITORÍA: El Admin ve todo, el Vendedor solo lo suyo
        # -------------------------------------------------------------------------
        if es_admin:
            res_c = supabase.table("clientes").select("*").execute()
        else:
            id_del_vendedor_actual = st.session_state.user_perfil.get('id')
            res_c = supabase.table("clientes").select("*").eq("vendedor_id", id_del_vendedor_actual).execute()
            
        if res_c.data:
            dict_c = {f"{cli['nombre']} ({cli['cedula']})": cli for cli in res_c.data}
            
            # -------------------------------------------------------------------------
            # IMPLEMENTACIÓN DEL BUSCADOR REAL (Filtrado dinámico en caliente)
            # -------------------------------------------------------------------------
            busqueda = st.text_input("🔍 Buscar Cliente (Escriba Nombre o Cédula):").lower()
            
            # Filtramos las opciones del diccionario según lo que el usuario digite
            opciones_filtradas = [
                opcion for opcion in dict_c.keys() 
                if busqueda in opcion.lower()
            ]
            
            # Si la búsqueda no arroja resultados, por seguridad mostramos la lista completa para no romper el flujo
            if not opciones_filtradas:
                opciones_filtradas = list(dict_c.keys())
                
            sel_c_input = st.selectbox("Seleccione Cliente", opciones_filtradas)
            dat_c = dict_c[sel_c_input]
            # -------------------------------------------------------------------------
            
            v1, v2, v3 = st.columns(3)
            with v1:
                art = st.text_input("Artículo/Producto"); precio = st.number_input("Precio Venta Total", min_value=0, step=1000)
            with v2:
                inic = st.number_input("Cuota Inicial", min_value=0, step=1000)
                n_cuo = st.number_input("Número de Cuotas", min_value=1, value=5)
            with v3:
                fecha_v = st.date_input("Fecha Real de la Venta", value=datetime.now().date())
            
            st.subheader("Costos y Gastos Operativos")
            co1, co2, co3, co4 = st.columns(4)
            c_comp = co1.number_input("Costo Compra", min_value=0); c_tran = co2.number_input("Transporte", min_value=0)
            c_pape = co3.number_input("Papelería", min_value=0); c_otro = co4.number_input("Otros Gastos", min_value=0)
            
            sal = precio - inic
            df_cuo = pd.DataFrame([{"Cuota": i+1, "Fecha Vencimiento": (fecha_v + timedelta(days=(i+1)*15)), "Monto": sal/n_cuo} for i in range(n_cuo)])
            st.dataframe(df_cuo, use_container_width=True, hide_index=True)
            
            if st.button("Finalizar y Registrar Venta", type="primary"):
                if precio > 0 and art:
                    
                    # -------------------------------------------------------------------------
                    # SOLUCIÓN TÉCNICA: Definición de variable para evitar NameError en local
                    # Extrae el ID del usuario logueado almacenado en el estado de la sesión
                    # -------------------------------------------------------------------------
                    id_del_vendedor_actual = st.session_state.user_perfil.get('id')
                    
                    # Se agrega 'sede_id' al insert de la tabla ventas
                    v_ins = supabase.table("ventas").insert({
                        "cliente_id": dat_c['id'], 
                        "producto": art, 
                        "monto_total": precio, 
                        "cuota_inicial": inic, 
                        "fecha_venta": str(fecha_v), 
                        "costo_compra": c_comp, 
                        "gasto_transporte": c_tran, 
                        "gasto_papeleria": c_pape, 
                        "gasto_otros": c_otro,
                        "vendedor_id": id_del_vendedor_actual,
                        "sede_id": mi_sede_id  # Inyección de la sede del usuario actual
                    }).execute()
                    
                    v_id = v_ins.data[0]['id']
                    
                    for _, fila in df_cuo.iterrows():
                        # Se agrega 'sede_id' al insert del plan de pagos para reportes directos
                        supabase.table("plan_pagos").insert({
                            "venta_id": v_id, 
                            "numero_cuota": fila['Cuota'], 
                            "fecha_vencimiento": str(fila['Fecha Vencimiento']), 
                            "monto": fila['Monto'],
                            "sede_id": mi_sede_id  # Inyección de la sede
                        }).execute()
                        
                    st.session_state.pdf_path = generar_pdf_contrato({"producto": art, "monto_total": precio, "cuota_inicial": inic}, df_cuo, dat_c, v_id)
                    st.session_state.venta_finalizada = True; st.rerun()

elif choice == "Control de Cartera":
    st.header("Gestión de Recaudo y Auditoría de Utilidad")
    st.info(f"Operando en sede: **{nombre_sede}**")
    
    if st.session_state.get('recaudo_finalizado'):
        st.success("✅ Recaudo procesado.")
        with open(st.session_state.pdf_recaudo_path, "rb") as f:
            st.download_button("📥 DESCARGAR RECIBO", f, file_name="Recibo_Caja_CJD.pdf", type="primary")
        if st.button("Otro Recaudo"):
            st.session_state.recaudo_finalizado = False
            st.session_state.pdf_recaudo_path = None
            st.rerun()
    else:
        # --- FILTRO POR SEDE EN LA CONSULTA ---
        query_v = supabase.table("ventas").select("*, clientes(*)")
        
        # Si no es admin, solo ve las ventas de su sede asignada
        if not es_admin:
            query_v = query_v.eq("sede_id", mi_sede_id)
            
        res = query_v.execute()
        
        if res.data:
            # --- BUSCADOR RESTAURADO ---
            opciones = {f"{v['clientes']['nombre']} - {v['producto']} (ID: {v['id']})": v for v in res.data}
            busqueda = st.text_input("🔍 Buscar Cliente o Producto")
            filtered_options = [opt for opt in opciones.keys() if busqueda.lower() in opt.lower()]
            
            if not filtered_options:
                st.warning("No se encontraronコインcidencias.")
                st.stop()
                
            seleccion = st.selectbox("Seleccione la Venta para Recaudo", filtered_options)
            v_sel = opciones[seleccion]
 
            # --- CÁLCULOS DETALLADOS ---
            egresos = (v_sel.get('costo_compra', 0) + v_sel.get('gasto_transporte', 0) + 
                       v_sel.get('gasto_papeleria', 0) + v_sel.get('gasto_otros', 0))
            
            cuotas_res = supabase.table("plan_pagos").select("*").eq("venta_id", v_sel['id']).execute()
            
            # --- CORRECCIÓN DE INTEGRIDAD PARA EVITAR EL KEYERROR ---
            if cuotas_res.data:
                df_recaudo = pd.DataFrame(cuotas_res.data)
                total_parciales = df_recaudo['pagado'].sum()
            else:
                # Si la consulta viene vacía, creamos un DataFrame con las columnas esperadas
                df_recaudo = pd.DataFrame(columns=["id", "numero_cuota", "fecha_vencimiento", "monto", "pagado", "estado"])
                total_parciales = 0
                
            cuota_inicial = v_sel['cuota_inicial']
            total_recaudado = cuota_inicial + total_parciales
            
            saldo_pendiente = v_sel['monto_total'] - total_recaudado
            utilidad_real = v_sel['monto_total'] - egresos
            margen = (utilidad_real / v_sel['monto_total'] * 100) if v_sel['monto_total'] > 0 else 0
            utilidad_socio = utilidad_real * 0.50
 
            # --- INTERFAZ DE MÉTRICAS ---
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Venta", f"${int(v_sel['monto_total']):,}")
            m2.metric("Costo Operativo", f"${int(egresos):,}")
            m3.metric("Recaudado Total", f"${int(total_recaudTotal):,}" if 'total_recaudTotal' in locals() else f"${int(total_recaudado):,}")
            m4.metric("Saldo Pendiente", f"${int(saldo_pendiente):,}", delta_color="inverse")
 
            st.write("---")
            
            u1, u2, u3, u4 = st.columns(4)
            u1.info(f"Recaudo Cuota Inicial: ${int(cuota_inicial):,}")
            u2.info(f"Recaudo Cuotas Parciales: ${int(total_parciales):,}")
            u3.success(f"Utilidad Real: ${int(utilidad_real):,}")
            u4.warning(f"Socio Op. (50%): ${int(utilidad_socio):,}")
            
            st.caption(f"**Margen de Venta:** {round(margen, 2)}%")
 
            # --- TABLA DE CUOTAS PROTEGIDA ---
            st.subheader("Plan de Pagos")
            if not df_recaudo.empty:
                df_visual = df_recaudo[["numero_cuota", "fecha_vencimiento", "monto", "pagado", "estado"]].sort_values("numero_cuota")
                df_visual['monto'] = df_visual['monto'].apply(lambda x: f"${int(x):,}")
                df_visual['pagado'] = df_visual['pagado'].apply(lambda x: f"${int(x):,}")
                st.dataframe(df_visual, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ No se encontraron cuotas generadas para esta venta en la base de datos.")
            
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                monto_abono = st.number_input("Valor Abono", min_value=0)
            with c_r2:
                metodo = st.selectbox("Método", ["Efectivo", "Nequi", "Daviplata", "Transferencia"])
            
            if st.button("Procesar Recibo", type="primary"):
                if monto_abono > 0:
                    # Se inserta el pago asignando la sede actual del operador
                    supabase.table("pagos").insert({
                        "venta_id": v_sel['id'], 
                        "monto": monto_abono, 
                        "metodo_pago": metodo, 
                        "fecha_pago": str(datetime.now().date()),
                        "sede_id": mi_sede_id
                    }).execute()
                    
                    r = monto_abono
                    if not df_recaudo.empty:
                        for _, c in df_recaudo.sort_values("numero_cuota").iterrows():
                            if r <= 0: break
                            falta = c['monto'] - (c.get('pagado') or 0)
                            if falta > 0:
                                apli = min(r, falta)
                                nuevo = (c.get('pagado') or 0) + apli
                                supabase.table("plan_pagos").update({
                                    "pagado": nuevo, 
                                    "estado": 'Cancelada' if nuevo >= c['monto'] else 'Abonada'
                                }).eq("id", c['id']).execute()
                                r -= apli
                     
                    st.session_state.pdf_recaudo_path = generar_recibo_caja(v_sel['clientes'], monto_abono, metodo, v_sel['producto'])
                    st.session_state.recaudo_finalizado = True
                    st.rerun()

elif choice == "Historial de Ventas":
    st.header("Auditoría de Ventas y Firma de Contratos")
    st.info(f"Visualizando registros de la sede: **{nombre_sede}**")
    
    # --- CONSULTA CON FILTRO MULTI-SEDE ---
    query_h = supabase.table("ventas").select("*, clientes(*)")
    
    # Si el perfil no es Administrador, solo recupera ventas de su propia sede
    if not es_admin:
        query_h = query_h.eq("sede_id", mi_sede_id)
        
    hist = query_h.order("fecha_venta", desc=True).execute()
    
    if hist.data:
        # --- BUSCADOR INTEGRADO ---
        opciones_hist = {f"{r['fecha_venta']} | {r['clientes']['nombre']} - {r['producto']} (ID: {r['id']})": r for r in hist.data}
        busqueda_hist = st.text_input("🔍 Buscar en Historial (Nombre, Producto o Fecha)")
        
        filtered_hist = [opt for opt in opciones_hist.keys() if busqueda_hist.lower() in opt.lower()]
        
        if not filtered_hist:
            st.warning("No se encontraron registros que coincidan con la búsqueda.")
        else:
            for seleccion in filtered_hist:
                r = opciones_hist[seleccion]
                with st.expander(seleccion):
                    c_h1, c_h2 = st.columns([1, 1])
                    with c_h1:
                        st.write(f"**Venta:** ${int(r['monto_total']):,} | **Costo:** ${int(r['costo_compra']):,}")
                        
                        # --- SECCIÓN DE CARGA DE DOCUMENTOS SOPORTE ---
                        st.divider()
                        st.subheader("📁 Documentos Soporte")
                        
                        # Visualización del Contrato Firmado (Trazabilidad)
                        if r.get('url_contrato'):
                            st.success("✅ Contrato Digitalizado en Nube")
                            st.link_button("📄 Ver Contrato Oficial", r['url_contrato'], use_container_width=True)
                            st.divider()
 
                        up_doc, up_fac = st.columns(2)
                        
                        with up_doc:
                            file_doc = st.file_uploader(f"Cédula Cliente (ID {r['id']})", type=['pdf', 'jpg', 'png'], key=f"doc_{r['id']}")
                            if file_doc and st.button("Subir Cédula", key=f"btn_doc_{r['id']}"):
                                path_doc = f"cedulas/c_{r['id']}_{file_doc.name}"
                                supabase.storage.from_("soportes").upload(
                                    path=path_doc, 
                                    file=file_doc.getvalue(),
                                    file_options={"content-type": file_doc.type, "upsert": "true"}
                                )
                                supabase.table("ventas").update({"doc_cliente_path": path_doc}).eq("id", r['id']).execute()
                                st.success("Cédula cargada.")
                                st.rerun() 
                            
                            if r.get('doc_cliente_path'):
                                res_url_doc = supabase.storage.from_("soportes").get_public_url(r['doc_cliente_path'])
                                url_doc = res_url_doc if isinstance(res_url_doc, str) else res_url_doc.public_url
                                st.link_button("👁️ Ver Cédula", url_doc)
 
                        with up_fac:
                            file_fac = st.file_uploader(f"Factura Compra (ID {r['id']})", type=['pdf', 'jpg', 'png'], key=f"fac_{r['id']}")
                            if file_fac and st.button("Subir Factura", key=f"btn_fac_{r['id']}"):
                                path_fac = f"facturas/f_{r['id']}_{file_fac.name}"
                                supabase.storage.from_("soportes").upload(
                                    path=str(path_fac), 
                                    file=file_fac.getvalue(),
                                    file_options={"content-type": str(file_fac.type), "upsert": True}
                                )
                                supabase.table("ventas").update({"fac_compra_path": path_fac}).eq("id", r['id']).execute()
                                st.success("Factura cargada.")
                                st.rerun() 
                            
                            if r.get('fac_compra_path'):
                                res_url_fac = supabase.storage.from_("soportes").get_public_url(r['fac_compra_path'])
                                url_fac = res_url_fac if isinstance(res_url_fac, str) else res_url_fac.public_url
                                st.link_button("👁️ Ver Factura", url_fac)
                        
                        st.divider()
                        if st.button(f"🔗 Enlace Firma Remota #{r['id']}", key=f"rem_{r['id']}"):
                            link_remoto = f"https://cjd-firma-digital.streamlit.app/?id={r['id']}"
                            st.success("Enlace listo:")
                            st.code(link_remoto)
                        
                        if st.button(f"Reimprimir Contrato Sin Firma #{r['id']}", key=f"re_{r['id']}"):
                            p_p = supabase.table("plan_pagos").select("*").eq("venta_id", r['id']).order("numero_cuota").execute()
                            df_p_p = pd.DataFrame(p_p.data).rename(columns={"numero_cuota": "Cuota", "fecha_vencimiento": "Fecha Vencimiento", "monto": "Monto"})
                            # Pasamos metadatos como None para la reimpresión sin firma
                            path_dup = generar_pdf_contrato(r, df_p_p, r['clientes'], r['id'], metadatos=None)
                            with open(path_dup, "rb") as f_dup:
                                st.download_button("Descargar PDF", f_dup, file_name=f"Contrato_CJD_{r['id']}.pdf")
                     
                    with c_h2:
                        st.subheader("🖋️ Firma Presencial")
                        # Mantenemos la versión v7 que usted ya tiene operativa
                        canvas_id = f"canvas_v7_{r['id']}_{r['fecha_venta'].replace('-', '')}"
                        canvas_result = st_canvas(fill_color="rgba(255, 255, 255, 0)", stroke_width=3, stroke_color="#000000", background_color="#eeeeee", height=150, width=400, drawing_mode="freedraw", key=canvas_id, update_streamlit=True)
                        
                        if st.button(f"Generar Contrato Firmado #{r['id']}", key=f"f_btn_{r['id']}"):
                            if canvas_result.image_data is not None:
                                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                                
                                # Captura de evidencia para auditoría
                                metadatos_audit = {
                                    "ip": socket.gethostbyname(socket.gethostname()), 
                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_firma:
                                    img.save(tmp_firma.name)
                                    p_p = supabase.table("plan_pagos").select("*").eq("venta_id", r['id']).order("numero_cuota").execute()
                                    df_p_p = pd.DataFrame(p_p.data).rename(columns={"numero_cuota": "Cuota", "fecha_vencimiento": "Fecha Vencimiento", "monto": "Monto"})
                                    
                                    # Generación del PDF (La función ahora estampa la evidencia en todas las hojas)
                                    path_firmado = generar_pdf_contrato(r, df_p_p, r['clientes'], r['id'], ruta_firma_cliente=tmp_firma.name, metadatos=metadatos_audit)
                                    
                                    # --- SUBIDA AUTOMÁTICA ---
                                    nombre_nube = f"contrato_firmado_{r['id']}_{int(datetime.now().timestamp())}.pdf"
                                    with open(path_firmado, "rb") as f_upload:
                                        supabase.storage.from_("contratos").upload(
                                            path=nombre_nube,
                                            file=f_upload,
                                            file_options={"content-type": "application/pdf", "upsert": "true"}
                                        )
                                    
                                    # Obtener URL y guardar en tabla ventas
                                    res_url_nube = supabase.storage.from_("contratos").get_public_url(nombre_nube)
                                    url_final = res_url_nube if isinstance(res_url_nube, str) else res_url_nube.public_url
                                    supabase.table("ventas").update({"url_contrato": url_final}).eq("id", r['id']).execute()
                                    
                                    st.success("✅ Contrato firmado y guardado con evidencia en todas las hojas.")
                                    st.rerun() 
                            else:
                                st.warning("Capture la firma antes de generar.")
    else:
        st.info(f"No hay ventas registradas en la sede {nombre_sede}.")

elif choice == "Gestión de Cobranza":
    st.header("📋 Gestión de Cobranza y Cartera")
    st.info(f"Vencimientos programados para la sede: **{nombre_sede}**")
 
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        dias_futuros = st.slider("Ver vencimientos en los próximos (días):", 1, 60, 7)
    
    hoy = datetime.now().date()
    fecha_limite = hoy + timedelta(days=dias_futuros)
 
    # --- CONSULTA CON FILTRO DE SEDE INTEGRADO ---
    # Traemos los datos necesarios haciendo el join con ventas
    query_cob = supabase.table("plan_pagos").select(
        "id, numero_cuota, fecha_vencimiento, monto, ventas!inner(id, producto, estado, sede_id, clientes(nombre, telefono))"
    ).eq("estado", "Pendiente").gte("fecha_vencimiento", str(hoy)).lte("fecha_vencimiento", str(fecha_limite))

    # Filtro de seguridad: Si no es admin, solo ve su sede
    if not es_admin:
        query_cob = query_cob.eq("ventas.sede_id", mi_sede_id)

    res = query_cob.execute()
 
    if res.data:
        datos_cobranza = []
        for p in res.data:
            # FILTRO DE AUDITORÍA: Solo si la venta no está anulada
            estado_v = p['ventas'].get('estado', 'Activa')
            
            if estado_v != "Anulado":
                datos_cobranza.append({
                    "ID Cuota": p['id'], 
                    "Cliente": p['ventas']['clientes']['nombre'],
                    "Teléfono": p['ventas']['clientes']['telefono'],
                    "Producto": p['ventas']['producto'],
                    "Cuota No.": p['numero_cuota'],
                    "Vencimiento": p['fecha_vencimiento'],
                    "Monto": p['monto']
                })
        
        if datos_cobranza:
            df_cobranza = pd.DataFrame(datos_cobranza)
            
            # --- AJUSTES DE VISUALIZACIÓN ---
            df_mostrar = df_cobranza.copy()
            df_mostrar["Monto"] = df_mostrar["Monto"].apply(lambda x: f"${int(x):,}")
            
            st.dataframe(
                df_mostrar.drop(columns=["ID Cuota"]), 
                use_container_width=True, 
                hide_index=True
            )
 
            st.subheader("🚀 Generador de Recordatorios")
            nombres_clientes = sorted(df_cobranza['Cliente'].unique().tolist())
            cliente_sel = st.selectbox("1. Seleccione un cliente:", nombres_clientes)
 
            if cliente_sel:
                cuotas_cliente = df_cobranza[df_cobranza['Cliente'] == cliente_sel]
                
                if len(cuotas_cliente) > 1:
                    opciones_cuota = cuotas_cliente.apply(
                        lambda r: f"Cuota {r['Cuota No.']} - {r['Producto']} (${int(r['Monto']):,})", axis=1
                    ).tolist()
                    
                    seleccion_indice = st.selectbox(
                        "2. El cliente tiene varias obligaciones. Seleccione cuál recordar:", 
                        range(len(opciones_cuota)), 
                        format_func=lambda x: opciones_cuota[x]
                    )
                    fila = cuotas_cliente.iloc[seleccion_indice]
                else:
                    fila = cuotas_cliente.iloc[0]
 
                monto_f = f"{int(fila['Monto']):,}"
                
                # Mensaje Profesional
                mensaje_tipo = (
                    f"*RECORDATORIO DE PAGO - CJ&D SUMINISTROS Y SERVICIOS*\n\n"
                    f"Cordial saludo, *{fila['Cliente']}*.\n\n"
                    f"Es un gusto saludarle. Nos permitimos recordarle que, de acuerdo con su plan de pagos, "
                    f"su cuota No. *{fila['Cuota No.']}* por concepto de compra de: *{fila['Producto']}*, "
                    f"presenta vencimiento el día: *{fila['Vencimiento']}*.\n\n"
                    f"• *Valor a cancelar:* ${monto_f} M/CTE.\n\n"
                    f"Para su comodidad, puede realizar su pago a través de los siguientes medios:\n"
                    f"*[-] Transferencia Bancaria:* A la llave: *@CJCRUZ*\n"
                    f"*[-] Efectivo:* Al cobrador autorizado.\n\n"
                    f"Una vez realizada la transacción, le agradecemos enviar el comprobante por este medio "
                    f"para formalizar su respectivo recibo de caja.\n\n"
                    f"*CJ&D SUMINISTROS* - Calidad y cumplimiento en cada servicio.\n"
                    f"_Si ya realizó su pago, por favor haga caso omiso a este mensaje._"
                )
 
                st.text_area("Mensaje profesional para enviar:", mensaje_tipo, height=350)
                
                tel_formateado = str(fila['Teléfono']).strip()
                mensaje_codificado = urllib.parse.quote(mensaje_tipo)
                link_wa = f"https://wa.me/57{tel_formateado}?text={mensaje_codificado}"
                
                st.link_button("🚀 Abrir WhatsApp del Cliente", link_wa)
        else:
            st.success(f"No hay cuotas pendientes por vencer en la sede {nombre_sede} para los próximos {dias_futuros} días.")
    else:
        st.success(f"No hay cuotas pendientes por vencer en los próximos {dias_futuros} días.")

elif choice == "Configuración y Datos":
    st.header("⚙️ Gestión de Datos y Configuraciones")
    
    # --- AJUSTE: INICIALIZACIÓN DINÁMICA DE PESTAÑAS SEGÚN ROL ---
    titulos_tabs = ["👤 Maestro de Clientes"]
    if es_admin:
        titulos_tabs.append("📦 Auditoría de Ventas")
        
    tabs = st.tabs(titulos_tabs)
 
    # --- TAB 1: MAESTRO DE CLIENTES (Accesible para todos) ---
    with tabs[0]:
        st.subheader("Edición de Perfiles de Clientes")
        
        # -------------------------------------------------------------------------
        # AJUSTE DE FILTRADO: El Administrador ve todo, el Vendedor solo lo suyo
        # -------------------------------------------------------------------------
        if es_admin:
            res_cli = supabase.table("clientes").select("*").execute()
        else:
            id_del_vendedor_actual = st.session_state.user_perfil.get('id')
            res_cli = supabase.table("clientes").select("*").eq("vendedor_id", id_del_vendedor_actual).execute()
        
        if res_cli.data:
            df_cli = pd.DataFrame(res_cli.data)
            nombres_clientes = sorted(df_cli['nombre'].tolist())
            cliente_a_editar = st.selectbox("Busque el cliente para modificar:", nombres_clientes)
            
            if cliente_a_editar:
                u = df_cli[df_cli['nombre'] == cliente_a_editar].iloc[0]
                with st.form("form_full_cliente"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nuevo_nombre = st.text_input("Nombre Completo:", value=u.get('nombre', ''))
                        nueva_cedula = st.text_input("Identificación / NIT:", value=u.get('cedula', ''))
                    with col2:
                        nuevo_telefono = st.text_input("Teléfono:", value=u.get('telefono', ''))
                        nueva_direccion = st.text_input("Dirección:", value=u.get('direccion', ''))
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        supabase.table("clientes").update({
                            "nombre": nuevo_nombre, 
                            "cedula": nueva_cedula,
                            "telefono": nuevo_telefono, 
                            "direccion": nueva_direccion
                        }).eq("id", u['id']).execute()
                        st.success("Datos actualizados.")
                        st.rerun()
 
    # --- TAB 2: AUDITORÍA DE VENTAS (Protegida estrictamente para el Administrador) ---
    if es_admin:
        with tabs[1]:
            st.subheader("Anulación de Registros por Error")
            search_term = st.text_input("🔍 Buscar venta a anular:")
            
            # Filtramos para no mostrar las que ya están anuladas si desea limpiar la vista
            res_v = supabase.table("ventas").select("*, clientes(nombre)").neq("estado", "Anulado").execute()
            
            if res_v.data:
                ventas_list = []
                for v in res_v.data:
                    cliente_n = v['clientes']['nombre'] if v.get('clientes') else "N/A"
                    producto_n = v.get('producto', 'N/A')
                    valor_raw = v.get('valor') or v.get('monto') or v.get('monto_total') or 0
                    
                    if search_term.lower() in cliente_n.lower() or search_term.lower() in producto_n.lower():
                        ventas_list.append({
                            "id": v['id'],
                            "Info": f"ID: {v['id']} | {cliente_n} | {producto_n} | (${int(valor_raw):,})"
                        })
                
                if ventas_list:
                    df_v = pd.DataFrame(ventas_list)
                    venta_sel_info = st.selectbox("Seleccione la venta para ANULAR:", df_v['Info'].tolist())
                    id_venta_sel = df_v[df_v['Info'] == venta_sel_info]['id'].values[0]
     
                    st.divider()
                    motivo = st.text_area("Indique el motivo de la anulación (Auditoría):")
                    
                    if st.button("🚫 Confirmar Anulación de Venta", type="primary"):
                        if motivo:
                            try:
                                # 1. Anular la Venta
                                supabase.table("ventas").update({"estado": "Anulado", "observaciones": motivo}).eq("id", id_venta_sel).execute()
                                
                                # 2. Anular el Plan de Pagos asociado
                                supabase.table("plan_pagos").update({"estado": "Anulado"}).eq("venta_id", id_venta_sel).execute()
                                 
                                # 3. Anular Pagos/Abonos registrados (si existen)
                                supabase.table("pagos").update({"estado": "Anulado"}).eq("venta_id", id_venta_sel).execute()
                                
                                st.warning(f"La venta ID {id_venta_sel} ha sido marcada como ANULADA.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error en auditoría: {e}")
                        else:
                            st.error("Por favor, escriba un motivo para la anulación.")
                else:
                    st.info("No se encontraron coincidencias para la búsqueda.")
            else:
                st.info("No se encontraron ventas activas.")
st.sidebar.caption(f"Ing. Charles | Auditoría CJ&D © {datetime.now().year}")
