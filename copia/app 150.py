import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import tempfile
import os
import plotly.express as px

# 1. CONFIGURACIÓN DE CONEXIÓN
URL_SUPABASE = "https://ipteqcymqujhszahlski.supabase.co"
KEY_SUPABASE = "sb_publishable_5lOnTzxb3XXwZxiKj-QVYw_7GmiIaMD"

@st.cache_resource
def init_connection():
    return create_client(URL_SUPABASE, KEY_SUPABASE)

supabase = init_connection()

st.set_page_config(page_title="Sistema CJ&D - Charles", layout="wide")

# --- CONTROL DE ESTADO (PREVENCIÓN DE DUPLICIDAD Y LIMPIEZA) ---
if 'venta_finalizada' not in st.session_state:
    st.session_state.venta_finalizada = False
if 'pdf_path' not in st.session_state:
    st.session_state.pdf_path = None
if 'recaudo_finalizado' not in st.session_state:
    st.session_state.recaudo_finalizado = False
if 'pdf_recaudo_path' not in st.session_state:
    st.session_state.pdf_recaudo_path = None

# --- FUNCIÓN NÚCLEO: GENERACIÓN DE PDF CONTRATO (3 PÁGINAS COMPLETAS) ---
def generar_pdf_contrato(datos_venta, plan_pagos, cliente, id_venta):
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

    # --- PÁGINA 1: CONTRATO DE COMPRAVENTA CON RESERVA DE DOMINIO ---
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
    pdf.multi_cell(0, 5, "El VENDEDOR se reserva la propiedad y el dominio del artículo descrito en la cláusula primera hasta tanto el COMPRADOR haya cancelado la totalidad del precio pactado, de conformidad con el Artículo 952 del Código de Comercio. En consecuencia, el COMPRADOR no podrá enajenar, gravar, ni disponer del artículo sin autorización previa y escrita del VENDEDOR.")
    
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "QUINTA. UBICACIÓN Y RIESGOS:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, f"El artículo deberá permanecer en la dirección: {cliente['direccion'].upper()}. El COMPRADOR asume los riesgos de pérdida o deterioro del artículo desde el momento de su entrega.")
    
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, "SEXTA. CLÁUSULA ACELERATORIA:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, "El incumplimiento en el pago de una (1) o más cuotas dará derecho al VENDEDOR a declarar extinguido el plazo y exigir el pago total del saldo pendiente o la restitución inmediata del artículo.")
    
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, f"Para constancia se firma en dos ejemplares a los {fecha_texto}", ln=True, align='L')
    
    pdf.ln(10)
    pdf.cell(90, 10, "__________________________", 0, 0)
    pdf.cell(90, 10, "__________________________", 0, 1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 5, "EL VENDEDOR", 0, 0)
    pdf.cell(90, 5, "EL COMPRADOR", 0, 1)

    # --- PÁGINA 2: PAGARÉ ---
    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"PAGARÉ No. {num_pagare}", ln=True, align='L')
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.write(5, f"YO, {cliente['nombre'].upper()}, mayor de edad, identificado como aparece al pie de mi firma, por medio del presente documento declaro que DEBO Y PAGARÉ de manera incondicional, solidaria e indivisible a la orden de ")
    pdf.set_font("Arial", 'B', 10)
    pdf.write(5, "CJ&D SUMINISTROS Y SERVICIOS")
    pdf.set_font("Arial", size=10)
    pdf.write(5, " la suma de: ____________________________________________________________________ ($___________________________). \n\n")
    pdf.multi_cell(0, 5, "El pago de la presente obligación se realizará en Barranquilla, en las fechas estipuladas en el plan de pagos anexo. En caso de mora, se causarán intereses a la tasa máxima legal permitida por la Superintendencia Financiera. Autorizo irrevocablemente al tenedor de este título para declarar extinguido el plazo y exigir el cobro total en caso de incumplimiento.")
    
    pdf.ln(25)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    curr_y = pdf.get_y()
    pdf.rect(120, curr_y - 15, 25, 30) 
    pdf.set_xy(120, curr_y + 16)
    pdf.cell(25, 5, "HUELLA", 0, 0, 'C')

    # --- PÁGINA 3: CARTA DE INSTRUCCIONES ---
    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "CARTA DE INSTRUCCIONES", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.write(6, "Señores:\n")
    pdf.set_font("Arial", 'B', 10)
    pdf.write(6, "CJ&D SUMINISTROS Y SERVICIOS\n")
    pdf.set_font("Arial", size=10)
    pdf.write(6, "Ciudad.\n\n")
    pdf.multi_cell(0, 6, f"Yo, {cliente['nombre'].upper()}, mayor de edad, identificado con la C.C. No. {cliente['cedula']}, autorizo expresamente a CJ&D SUMINISTROS Y SERVICIOS para que proceda a diligenciar los espacios en blanco del PAGARÉ No. {num_pagare} que he suscrito a su favor.\n\nEl título deberá ser llenado bajo las siguientes instrucciones:")
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10)
    pdf.write(6, "1. Monto: ")
    pdf.set_font("Arial", size=10)
    pdf.write(6, "Será igual al saldo insoluto de la deuda a la fecha de diligenciamiento.\n")
    pdf.set_font("Arial", 'B', 10)
    pdf.write(6, "2. Fecha de Vencimiento: ")
    pdf.set_font("Arial", size=10)
    pdf.write(6, "Será el día siguiente al incumplimiento de la obligación.\n\nPara constancia de lo anterior, firmo el presente documento.")
    
    pdf.ln(25)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    curr_y_c = pdf.get_y()
    pdf.rect(120, curr_y_c - 15, 25, 30) 
    pdf.set_xy(120, curr_y_c + 16)
    pdf.cell(25, 5, "HUELLA", 0, 0, 'C')

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        return tmp.name

# --- FUNCIÓN: GENERACIÓN DE RECIBO DE CAJA ---
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

# --- INTERFAZ PRINCIPAL ---
st.sidebar.title("Administración CJ&D")
menu = ["📊 Tablero de Control", "Registrar Cliente", "Nueva Venta", "Control de Cartera", "Historial de Ventas"]
choice = st.sidebar.selectbox("Acción", menu)

# Limpieza de estados si se navega fuera de los módulos específicos
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
        total_v = df_v['monto_total'].sum(); total_c = df_v['costo_compra'].sum() + df_v['gasto_transporte'].sum() + df_v['gasto_papeleria'].sum() + df_v['gasto_otros'].sum()
        utilidad = total_v - total_c; recaudado = df_p['pagado'].sum() + df_v['cuota_inicial'].sum(); calle = total_v - recaudado
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas Totales", f"${int(total_v):,}"); c2.metric("Utilidad Proyectada", f"${int(utilidad):,}")
        c3.metric("Capital en Calle", f"${int(calle):,}", delta_color="inverse"); c4.metric("Efectivo Recaudado", f"${int(recaudado):,}")
        st.divider()
        st.subheader("📈 Rendimiento de Ventas Mensuales (Tendencia)")
        df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta'])
        df_v_trend = df_v.set_index('fecha_venta').resample('ME')['monto_total'].sum().reset_index()
        df_v_trend['Mes'] = df_v_trend['fecha_venta'].dt.strftime('%B %Y')
        fig = px.line(df_v_trend, x='Mes', y='monto_total', title="Evolución de Ingresos CJ&D", labels={'monto_total': 'Ventas ($)', 'Mes': 'Periodo'}, markers=True)
        fig.update_traces(line_color='#1f77b4', line_width=3, marker=dict(size=10, symbol='circle'))
        fig.update_layout(hovermode="x unified", xaxis_tickangle=-45)
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
        st.success("✅ Venta registrada correctamente en la base de datos.")
        with open(st.session_state.pdf_path, "rb") as f:
            st.download_button("📥 DESCARGAR CONTRATO (3 PÁGINAS)", f, file_name="Contrato_Legal_CJD.pdf", type="primary")
        if st.button("Registrar Nueva Venta (Limpiar Campos)"):
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
        st.success("✅ Recaudo procesado y guardado.")
        with open(st.session_state.pdf_recaudo_path, "rb") as f:
            st.download_button("📥 DESCARGAR RECIBO DE CAJA", f, file_name="Recibo_Caja_CJD.pdf", type="primary")
        if st.button("Registrar Otro Recaudo"):
            st.session_state.recaudo_finalizado = False; st.session_state.pdf_recaudo_path = None; st.rerun()
    else:
        res = supabase.table("ventas").select("*, clientes(*)").execute()
        if res.data:
            opciones = {f"{v['clientes']['nombre']} - {v['producto']}": v for v in res.data}
            v_sel = opciones[st.selectbox("Seleccione Venta", list(opciones.keys()))]
            
            # --- RESUMEN FINANCIERO DE LA VENTA (AUDITORÍA REINCORPORADA) ---
            r1, r2, r3, r4 = st.columns(4)
            costos_v = v_sel['costo_compra'] + v_sel['gasto_transporte'] + v_sel['gasto_papeleria'] + v_sel['gasto_otros']
            r1.metric("Total Venta", f"${int(v_sel['monto_total']):,}")
            r2.metric("Total Costos", f"${int(costos_v):,}")
            r3.metric("Utilidad", f"${int(v_sel['monto_total'] - costos_v):,}")
            
            cuotas = supabase.table("plan_pagos").select("*").eq("venta_id", v_sel['id']).order("numero_cuota").execute()
            df_car = pd.DataFrame(cuotas.data)
            saldo_actual = df_car['monto'].sum() - df_car['pagado'].sum()
            r4.metric("Saldo Pendiente", f"${int(saldo_actual):,}", delta_color="inverse")
            
            st.dataframe(df_car[["numero_cuota", "fecha_vencimiento", "monto", "pagado", "estado"]], use_container_width=True, hide_index=True)
            
            c_r1, c_r2 = st.columns(2)
            with c_r1: monto_abono = st.number_input("Valor del Abono", min_value=0)
            with c_r2: metodo = st.selectbox("Método de Pago", ["Efectivo", "Nequi", "Daviplata", "Transferencia"])
            
            if st.button("Procesar y Generar Recibo", type="primary"):
                if monto_abono > 0:
                    supabase.table("pagos").insert({"venta_id": v_sel['id'], "monto": monto_abono, "metodo_pago": metodo, "fecha_pago": str(datetime.now().date())}).execute()
                    r = monto_abono
                    for _, c in df_car.iterrows():
                        if r <= 0: break
                        ya = c.get('pagado') or 0
                        falta = c['monto'] - ya
                        if falta > 0:
                            apli = min(r, falta)
                            nuevo = ya + apli
                            supabase.table("plan_pagos").update({"pagado": nuevo, "estado": 'Cancelada' if nuevo >= c['monto'] else 'Abonada'}).eq("id", c['id']).execute()
                            r -= apli
                    st.session_state.pdf_recaudo_path = generar_recibo_caja(v_sel['clientes'], monto_abono, metodo, v_sel['producto'])
                    st.session_state.recaudo_finalizado = True; st.rerun()

elif choice == "Historial de Ventas":
    st.header("Auditoría de Ventas")
    hist = supabase.table("ventas").select("*, clientes(*)").order("fecha_venta", desc=True).execute()
    for r in hist.data:
        with st.expander(f"{r['fecha_venta']} | {r['clientes']['nombre']} - {r['producto']}"):
            st.write(f"Venta: ${int(r['monto_total']):,} | Costo: ${int(r['costo_compra']):,}")

st.sidebar.caption(f"Ing. Charles | Auditoría CJ&D © {datetime.now().year}")