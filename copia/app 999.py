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

# 1. CONFIGURACIÓN DE CONEXIÓN
URL_SUPABASE = "https://ipteqcymqujhszahlski.supabase.co"
KEY_SUPABASE = "sb_publishable_5lOnTzxb3XXwZxiKj-QVYw_7GmiIaMD"

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

# --- FUNCIÓN NÚCLEO ACTUALIZADA ---
def generar_pdf_contrato(datos_venta, plan_pagos, cliente, id_venta, ruta_firma_cliente=None, metadatos=None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    num_pagare = 1000 + id_venta 
    fecha_hoy = datetime.now()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    fecha_texto = f"{fecha_hoy.day} días del mes de {meses[fecha_hoy.month - 1]} de {fecha_hoy.year}"

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
        pdf.image("firma.png", x=20, y=curr_y_firma - 18, w=45)

    if ruta_firma_cliente:
        pdf.image(ruta_firma_cliente, x=115, y=curr_y_firma - 18, w=45) 

    pdf.cell(90, 10, "__________________________", 0, 0)
    pdf.cell(90, 10, "__________________________", 0, 1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 5, "EL VENDEDOR", 0, 0)
    pdf.cell(90, 5, "EL COMPRADOR", 0, 1)

    if metadatos:
        pdf.ln(8)
        pdf.set_font("Arial", 'I', 7)
        pdf.cell(0, 5, f"Evidencia Digital: IP {metadatos['ip']} | Timestamp: {metadatos['timestamp']} | ID: {id_venta}", 0, 1, 'R')

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
    if ruta_firma_cliente:
        pdf.image(ruta_firma_cliente, x=20, y=curr_y_p - 18, w=45)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    pdf.rect(120, curr_y_p - 15, 25, 30) 
    pdf.set_xy(120, curr_y_p + 16)
    pdf.cell(25, 5, "HUELLA", 0, 0, 'C')

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
    if ruta_firma_cliente:
        pdf.image(ruta_firma_cliente, x=20, y=curr_y_c - 18, w=45)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    pdf.rect(120, curr_y_c - 15, 25, 30) 
    pdf.set_xy(120, curr_y_c + 16)
    pdf.cell(25, 5, "HUELLA", 0, 0, 'C')

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
    if os.path.exists("firma.png"):
        recibo.image("firma.png", x=10, y=y_pos_inicial, w=50)
    recibo.line(10, y_pos_inicial + 35, 80, y_pos_inicial + 35)
    recibo.set_font("Arial", 'B', 10)
    recibo.text(10, y_pos_inicial + 40, "Firma Autorizada - CJ&D")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        recibo.output(tmp.name)
        return tmp.name

st.sidebar.title("Administración CJ&D")
menu = ["📊 Tablero de Control", "Registrar Cliente", "Nueva Venta", "Control de Cartera", "Historial de Ventas"]
choice = st.sidebar.selectbox("Acción", menu)

if choice != "Nueva Venta":
    st.session_state.venta_finalizada = False
    st.session_state.pdf_path = None
if choice != "Control de Cartera":
    st.session_state.recaudo_finalizado = False
    st.session_state.pdf_recaudo_path = None

if choice == "📊 Tablero de Control":
    st.header("Análisis Financiero y Auditoría de Mora")
    v_res = supabase.table("ventas").select("*").execute()
    p_res = supabase.table("plan_pagos").select("*").execute()
    if v_res.data and p_res.data:
        df_v = pd.DataFrame(v_res.data); df_p = pd.DataFrame(p_res.data)
        total_v = df_v['monto_total'].sum()
        total_costos_op = df_v['costo_compra'].sum() + df_v['gasto_transporte'].sum() + df_v['gasto_papeleria'].sum() + df_v['gasto_otros'].sum()
        utilidad = total_v - total_costos_op
        recaudado = df_p['pagado'].sum() + df_v['cuota_inicial'].sum()
        calle = total_v - recaudado
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas Totales", f"${int(total_v):,}")
        c2.metric("Costos Totales", f"${int(total_costos_op):,}") 
        c3.metric("Capital en Calle", f"${int(calle):,}", delta_color="inverse")
        c4.metric("Efectivo Recaudado", f"${int(recaudado):,}")
        
        st.divider()
        st.metric("Utilidad Bruta Proyectada", f"${int(utilidad):,}")
        
        st.subheader("📈 Rendimiento de Ventas Mensuales")
        df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta'])
        df_v_trend = df_v.set_index('fecha_venta').resample('ME')['monto_total'].sum().reset_index()
        df_v_trend['Mes'] = df_v_trend['fecha_venta'].dt.strftime('%B %Y')
        fig = px.line(df_v_trend, x='Mes', y='monto_total', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("Inicie operaciones para visualizar estadísticas.")

elif choice == "Registrar Cliente":
    st.header("Registro de Nuevos Clientes")
    with st.form("cli_form"):
        c1, c2 = st.columns(2)
        with c1: n = st.text_input("Nombre Completo"); c_cc = st.text_input("Cédula")
        with c2: d = st.text_input("Dirección de Residencia"); t = st.text_input("Teléfono")
        if st.form_submit_button("Guardar Cliente"):
            if n and c_cc:
                supabase.table("clientes").insert({"nombre": n, "cedula": c_cc, "direccion": d, "telefono": t}).execute()
                st.success("Cliente guardado exitosamente.")

elif choice == "Nueva Venta":
    st.header("Generar Venta y Registro de Costos")
    if st.session_state.get('venta_finalizada'):
        st.success("✅ Venta registrada correctamente.")
        with open(st.session_state.pdf_path, "rb") as f:
            st.download_button("📥 DESCARGAR CONTRATO (3 PÁGINAS)", f, file_name="Contrato_Legal_CJD.pdf", type="primary")
        if st.button("Registrar Nueva Venta"):
            st.session_state.venta_finalizada = False; st.session_state.pdf_path = None; st.rerun()
    else:
        res_c = supabase.table("clientes").select("*").execute()
        if res_c.data:
            dict_c = {f"{cli['nombre']} ({cli['cedula']})": cli for cli in res_c.data}
            sel_c = st.selectbox("Seleccione Cliente", list(dict_c.keys())); dat_c = dict_c[sel_c]
            v1, v2, v3 = st.columns(3)
            with v1: art = st.text_input("Artículo/Producto"); precio = st.number_input("Precio Venta Total", min_value=0, step=1000)
            with v2: inic = st.number_input("Cuota Inicial", min_value=0, step=1000); n_cuo = st.number_input("Número de Cuotas", min_value=1, value=5)
            with v3: fecha_v = st.date_input("Fecha Real de la Venta", value=datetime.now().date())
            st.subheader("Costos y Gastos Operativos")
            co1, co2, co3, co4 = st.columns(4)
            c_comp = co1.number_input("Costo Compra", min_value=0); c_tran = co2.number_input("Transporte", min_value=0)
            c_pape = co3.number_input("Papelería", min_value=0); c_otro = co4.number_input("Otros Gastos", min_value=0)
            sal = precio - inic
            df_cuo = pd.DataFrame([{"Cuota": i+1, "Fecha Vencimiento": (fecha_v + timedelta(days=(i+1)*15)), "Monto": sal/n_cuo} for i in range(n_cuo)])
            st.dataframe(df_cuo, use_container_width=True, hide_index=True)
            if st.button("Finalizar y Registrar Venta", type="primary"):
                if precio > 0 and art:
                    v_ins = supabase.table("ventas").insert({"cliente_id": dat_c['id'], "producto": art, "monto_total": precio, "cuota_inicial": inic, "fecha_venta": str(fecha_v), "costo_compra": c_comp, "gasto_transporte": c_tran, "gasto_papeleria": c_pape, "gasto_otros": c_otro}).execute()
                    v_id = v_ins.data[0]['id']
                    for _, fila in df_cuo.iterrows():
                        supabase.table("plan_pagos").insert({"venta_id": v_id, "numero_cuota": fila['Cuota'], "fecha_vencimiento": str(fila['Fecha Vencimiento']), "monto": fila['Monto']}).execute()
                    st.session_state.pdf_path = generar_pdf_contrato({"producto": art, "monto_total": precio, "cuota_inicial": inic}, df_cuo, dat_c, v_id)
                    st.session_state.venta_finalizada = True; st.rerun()

elif choice == "Control de Cartera":
    st.header("Gestión de Recaudo")
    if st.session_state.get('recaudo_finalizado'):
        st.success("✅ Recaudo procesado.")
        with open(st.session_state.pdf_recaudo_path, "rb") as f:
            st.download_button("📥 DESCARGAR RECIBO", f, file_name="Recibo_Caja_CJD.pdf", type="primary")
        if st.button("Otro Recaudo"):
            st.session_state.recaudo_finalizado = False; st.session_state.pdf_recaudo_path = None; st.rerun()
    else:
        res = supabase.table("ventas").select("*, clientes(*)").execute()
        if res.data:
            opciones = {f"{v['clientes']['nombre']} - {v['producto']}": v for v in res.data}
            seleccion = st.selectbox("Seleccione Venta", list(opciones.keys()))
            v_sel = opciones[seleccion]

            # --- CÁLCULOS DE UTILIDAD Y AUDITORÍA ---
            total_egresos = (
                v_sel.get('costo_compra', 0) + 
                v_sel.get('gasto_transporte', 0) + 
                v_sel.get('gasto_papeleria', 0) + 
                v_sel.get('gasto_otros', 0)
            )
            utilidad_neta = v_sel['monto_total'] - total_egresos
            margen = (utilidad_neta / v_sel['monto_total']) * 100 if v_sel['monto_total'] > 0 else 0

            c_ut1, c_ut2, c_ut3 = st.columns(3)
            c_ut1.metric("Egresos Totales", f"${total_egresos:,}")
            c_ut2.success(f"Utilidad Real: ${utilidad_neta:,}")
            c_ut3.info(f"Margen: {round(margen, 1)}%")

            st.write("---")

            cuotas = supabase.table("plan_pagos").select("*").eq("venta_id", v_sel['id']).order("numero_cuota").execute()
            df_car = pd.DataFrame(cuotas.data)
            
            # Formato visual de moneda para la tabla
            df_visual = df_car[["numero_cuota", "fecha_vencimiento", "monto", "pagado", "estado"]].copy()
            df_visual['monto'] = df_visual['monto'].apply(lambda x: f"${int(x):,}")
            df_visual['pagado'] = df_visual['pagado'].apply(lambda x: f"${int(x):,}")
            st.dataframe(df_visual, use_container_width=True, hide_index=True)
            
            c_r1, c_r2 = st.columns(2)
            with c_r1: monto_abono = st.number_input("Valor Abono", min_value=0)
            with c_r2: metodo = st.selectbox("Método", ["Efectivo", "Nequi", "Daviplata", "Transferencia"])
            
            if st.button("Procesar Recibo", type="primary"):
                if monto_abono > 0:
                    supabase.table("pagos").insert({"venta_id": v_sel['id'], "monto": monto_abono, "metodo_pago": metodo, "fecha_pago": str(datetime.now().date())}).execute()
                    r = monto_abono
                    for _, c in df_car.iterrows():
                        if r <= 0: break
                        falta = c['monto'] - (c.get('pagado') or 0)
                        if falta > 0:
                            apli = min(r, falta)
                            nuevo = (c.get('pagado') or 0) + apli
                            supabase.table("plan_pagos").update({"pagado": nuevo, "estado": 'Cancelada' if nuevo >= c['monto'] else 'Abonada'}).eq("id", c['id']).execute()
                            r -= apli
                    st.session_state.pdf_recaudo_path = generar_recibo_caja(v_sel['clientes'], monto_abono, metodo, v_sel['producto'])
                    st.session_state.recaudo_finalizado = True; st.rerun()

elif choice == "Historial de Ventas":
    st.header("Auditoría de Ventas y Firma de Contratos")
    hist = supabase.table("ventas").select("*, clientes(*)").order("fecha_venta", desc=True).execute()
    for r in hist.data:
        with st.expander(f"{r['fecha_venta']} | {r['clientes']['nombre']} - {r['producto']}"):
            c_h1, c_h2 = st.columns([1, 1])
            with c_h1:
                st.write(f"**Venta:** ${int(r['monto_total']):,} | **Costo:** ${int(r['costo_compra']):,}")
                
                if st.button(f"🔗 Generar Enlace Remoto #{r['id']}", key=f"rem_{r['id']}"):
                    link_remoto = f"https://cjd-firma-digital.streamlit.app/?id={r['id']}" 
                    st.success("Enlace generado exitosamente:")
                    st.code(f"Link para WhatsApp: {link_remoto}")
                
                if st.button(f"Reimprimir Contrato Sin Firma #{r['id']}", key=f"re_{r['id']}"):
                    p_p = supabase.table("plan_pagos").select("*").eq("venta_id", r['id']).order("numero_cuota").execute()
                    df_p_p = pd.DataFrame(p_p.data).rename(columns={"numero_cuota": "Cuota", "fecha_vencimiento": "Fecha Vencimiento", "monto": "Monto"})
                    path_dup = generar_pdf_contrato(r, df_p_p, r['clientes'], r['id'])
                    with open(path_dup, "rb") as f_dup:
                        st.download_button("Descargar PDF", f_dup, file_name=f"Contrato_CJD_{r['id']}.pdf")
            
            with c_h2:
                st.subheader("🖋️ Formalizar con Firma (Presencial)")
                canvas_id = f"canvas_v7_{r['id']}_{r['fecha_venta'].replace('-', '')}"
                
                canvas_result = st_canvas(
                    fill_color="rgba(255, 255, 255, 0)",
                    stroke_width=3,
                    stroke_color="#000000",
                    background_color="#eeeeee",
                    height=150,
                    width=400,
                    drawing_mode="freedraw",
                    key=canvas_id,
                    update_streamlit=True
                )
                
                if st.button(f"Generar Contrato Firmado #{r['id']}", key=f"f_btn_{r['id']}"):
                    if canvas_result.image_data is not None:
                        img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        datas = img.getdata()
                        newData = []
                        for item in datas:
                            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                                newData.append((255, 255, 255, 0))
                            else:
                                newData.append(item)
                        img.putdata(newData)

                        metadatos_audit = {
                            "ip": socket.gethostbyname(socket.gethostname()),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_firma:
                            img.save(tmp_firma.name)
                            
                            p_p = supabase.table("plan_pagos").select("*").eq("venta_id", r['id']).order("numero_cuota").execute()
                            df_p_p = pd.DataFrame(p_p.data).rename(columns={"numero_cuota": "Cuota", "fecha_vencimiento": "Fecha Vencimiento", "monto": "Monto"})
                            
                            path_firmado = generar_pdf_contrato(r, df_p_p, r['clientes'], r['id'], ruta_firma_cliente=tmp_firma.name, metadatos=metadatos_audit)
                            
                            with open(path_firmado, "rb") as f_f:
                                st.download_button("📥 DESCARGAR CONTRATO FIRMADO", f_f, file_name=f"Contrato_Final_{r['id']}.pdf", type="primary")

st.sidebar.caption(f"Ing. Charles | Auditoría CJ&D © {datetime.now().year}")