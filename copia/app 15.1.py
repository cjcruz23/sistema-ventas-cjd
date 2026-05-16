import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import tempfile
import os

# 1. CONFIGURACIÓN DE CONEXIÓN
URL_SUPABASE = "https://ipteqcymqujhszahlski.supabase.co"
KEY_SUPABASE = "sb_publishable_5lOnTzxb3XXwZxiKj-QVYw_7GmiIaMD"

@st.cache_resource
def init_connection():
    return create_client(URL_SUPABASE, KEY_SUPABASE)

supabase = init_connection()

st.set_page_config(page_title="Sistema CJ&D - Charles", layout="wide")

# --- FUNCIÓN NÚCLEO: GENERACIÓN DE PDF CONTRATO (3 PÁGINAS) ---
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

    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "CONTRATO DE COMPRAVENTA CON RESERVA DE DOMINIO", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=10)
    pdf.write(5, "VENDEDOR: ")
    pdf.set_font("Arial", 'B', 10); pdf.write(5, "CJ&D SUMINISTROS Y SERVICIOS"); pdf.set_font("Arial", size=10)
    pdf.write(5, f" identificada con NIT. No. 1129571083-1. COMPRADOR: {cliente['nombre'].upper()}, identificado con C.C. No. {cliente['cedula']}.\n")
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "PRIMERA. OBJETO:", ln=True)
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 5, f"El VENDEDOR vende al COMPRADOR, y este adquiere, el siguiente artículo: {datos_venta['producto'].upper()}.")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "SEGUNDA. PRECIO:", ln=True)
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 5, f"El precio de venta acordado es de ${int(datos_venta['monto_total']):,} M/CTE.")
    
    pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "TERCERA. FORMA DE PAGO:", ln=True)
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 5, f"El COMPRADOR pagará una cuota inicial de ${int(datos_venta['cuota_inicial']):,}, cancelada a la firma de este contrato. El saldo se cancelará según el plan de pagos adjunto.")
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

    clausulas_legales = [
        ("CUARTA. RESERVA DE DOMINIO:", "El VENDEDOR se reserva la propiedad y el dominio del artículo descrito en la cláusula primera hasta tanto el COMPRADOR haya cancelado la totalidad del precio pactado, de conformidad con el Artículo 952 del Código de Comercio. En consecuencia, el COMPRADOR no podrá enajenar, gravar, ni disponer del artículo sin autorización previa y escrita del VENDEDOR."),
        ("QUINTA. UBICACIÓN Y RIESGOS:", f"El artículo deberá permanecer en la dirección: {cliente['direccion'].upper()}. El COMPRADOR asume los riesgos de pérdida o deterioro del artículo desde el momento de su entrega."),
        ("SEXTA. CLÁUSULA ACELERATORIA:", "El incumplimiento en el pago de una (1) o más cuotas dará derecho al VENDEDOR a declarar extinguido el plazo y exigir el pago total del saldo pendiente o la restitución inmediata del artículo.")
    ]
    
    for titulo, contenido in clausulas_legales:
        pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, titulo, ln=True)
        pdf.set_font("Arial", size=10); pdf.multi_cell(0, 5, contenido); pdf.ln(2)

    pdf.ln(5)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, f"Para constancia se firma en dos ejemplares a los {fecha_texto}", ln=True, align='L')
    pdf.ln(10)
    pdf.cell(90, 10, "__________________________", 0, 0)
    pdf.cell(90, 10, "__________________________", 0, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(90, 5, "EL VENDEDOR", 0, 0); pdf.cell(90, 5, "EL COMPRADOR", 0, 1)

    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"PAGARÉ No. {num_pagare}", ln=True, align='L'); pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.write(5, f"YO, {cliente['nombre'].upper()}, mayor de edad, identificado como aparece al pie de mi firma, por medio del presente documento declaro que DEBO Y PAGARÉ de manera incondicional, solidaria e indivisible a la orden de ")
    pdf.set_font("Arial", 'B', 10); pdf.write(5, "CJ&D SUMINISTROS Y SERVICIOS"); pdf.set_font("Arial", size=10)
    pdf.write(5, " la suma de: ____________________________________________________________________ ($___________________________). \n\n")
    pdf.multi_cell(0, 5, "El pago de la presente obligación se realizará en Barranquilla, en las fechas estipuladas en el plan de pagos anexo. En caso de mora, se causarán intereses a la tasa máxima legal permitida por la Superintendencia Financiera. Autorizo irrevocablemente al tenedor de este título para declarar extinguido el plazo y exigir el cobro total en caso de incumplimiento.")
    pdf.ln(25)
    pdf.cell(100, 10, "FIRMA: __________________________", 0, 0)
    curr_y = pdf.get_y()
    pdf.rect(120, curr_y - 15, 25, 30) 
    pdf.set_xy(120, curr_y + 16)
    pdf.cell(25, 5, "HUELLA", 0, 0, 'C')

    pdf.add_page()
    agregar_encabezado()
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "CARTA DE INSTRUCCIONES", ln=True, align='C'); pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.write(6, "Señores:\n")
    pdf.set_font("Arial", 'B', 10); pdf.write(6, "CJ&D SUMINISTROS Y SERVICIOS\n"); pdf.set_font("Arial", size=10)
    pdf.write(6, "Ciudad.\n\n")
    pdf.multi_cell(0, 6, f"Yo, {cliente['nombre'].upper()}, mayor de edad, identificado con la C.C. No. {cliente['cedula']}, autorizo expresamente a CJ&D SUMINISTROS Y SERVICIOS para que, haciendo uso de las facultades otorgadas por el artículo 622 del Código de Comercio, proceda a diligenciar los espacios en blanco del PAGARÉ No. {num_pagare} que he suscrito a su favor.\n\nEl título deberá ser llenado bajo las siguientes instrucciones:")
    
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10); pdf.write(6, "1. Monto: "); pdf.set_font("Arial", size=10)
    pdf.write(6, "Será igual al saldo insoluto de la deuda a la fecha de diligenciamiento.\n")
    pdf.set_font("Arial", 'B', 10); pdf.write(6, "2. Fecha de Vencimiento: "); pdf.set_font("Arial", size=10)
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

# --- FUNCIÓN: GENERACIÓN DE RECIBO DE CAJA PROFESIONAL ---
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

# --- INTERFAZ ---
st.sidebar.title("Administración CJ&D")
menu = ["Registrar Cliente", "Nueva Venta", "Historial de Ventas", "Control de Cartera"]
choice = st.sidebar.selectbox("Acción", menu)

if choice == "Registrar Cliente":
    st.header("Registro de Nuevos Clientes")
    with st.form("cli_form"):
        c1, c2 = st.columns(2)
        with c1:
            n = st.text_input("Nombre Completo"); c_cc = st.text_input("Cédula")
        with c2:
            d = st.text_input("Dirección de Residencia"); t = st.text_input("Teléfono")
        if st.form_submit_button("Guardar Cliente"):
            if n and c_cc:
                supabase.table("clientes").insert({"nombre": n, "cedula": c_cc, "direccion": d, "telefono": t}).execute()
                st.success("Cliente guardado exitosamente.")

elif choice == "Nueva Venta":
    st.header("Generar Venta y Registro de Costos")
    res_c = supabase.table("clientes").select("*").execute()
    if res_c.data:
        dict_c = {f"{cli['nombre']} ({cli['cedula']})": cli for cli in res_c.data}
        sel_c = st.selectbox("Seleccione Cliente", list(dict_c.keys()))
        dat_c = dict_c[sel_c]
        
        v1, v2 = st.columns(2)
        with v1:
            art = st.text_input("Artículo/Producto")
            # --- FORMATO MILES: Streamlit aplica separadores automáticamente al perder foco ---
            precio = st.number_input("Precio de Venta Total", min_value=0, step=1000, value=0)
        with v2:
            inic = st.number_input("Cuota Inicial", min_value=0, step=1000, value=0)
            n_cuo = st.number_input("Número de Cuotas", min_value=1, value=5)

        st.subheader("Costos y Gastos Operativos")
        co1, co2, co3, co4 = st.columns(4)
        with co1:
            costo_compra = st.number_input("Costo Compra Artículo", min_value=0, step=1000, value=0)
        with co2:
            transporte = st.number_input("Gasto Transporte", min_value=0, step=1000, value=0)
        with co3:
            papeleria = st.number_input("Gasto Papelería", min_value=0, step=1000, value=0)
        with co4:
            otros_gastos = st.number_input("Otros Gastos", min_value=0, step=1000, value=0)
        
        # --- CÁLCULO DE UTILIDAD ---
        total_egresos = costo_compra + transporte + papeleria + otros_gastos
        utilidad_neta = precio - total_egresos
        
        st.divider()
        m1, m2 = st.columns(2)
        m1.metric("Utilidad Real Estimada", f"${int(utilidad_neta):,}")
        m2.metric("Comisión Socio Operativo (50%)", f"${int(utilidad_neta/2):,}")

        sal = precio - inic
        df_cuo = pd.DataFrame([{"Cuota": i+1, "Fecha Vencimiento": (datetime.now() + timedelta(days=(i+1)*15)).date(), "Monto": sal/n_cuo} for i in range(n_cuo)])
        
        st.write("**Proyección del Plan de Pagos:**")
        # --- TABLA CON FORMATO MONEDA IDÉNTICO AL REQUERIDO ---
        st.dataframe(df_cuo, 
                     column_config={
                         "Monto": st.column_config.NumberColumn("Monto", format="$ %,.0f")
                     }, 
                     hide_index=True, 
                     use_container_width=True)
        
        if st.button("Finalizar Venta y Descargar Contrato"):
            v_ins = supabase.table("ventas").insert({
                "cliente_id": dat_c['id'], 
                "producto": art, 
                "monto_total": precio, 
                "cuota_inicial": inic, 
                "fecha_venta": str(datetime.now().date()),
                "costo_compra": costo_compra,
                "gasto_transporte": transporte,
                "gasto_papeleria": papeleria,
                "gasto_otros": otros_gastos
            }).execute()
            
            v_id = v_ins.data[0]['id']
            for _, fila in df_cuo.iterrows():
                supabase.table("plan_pagos").insert({"venta_id": v_id, "numero_cuota": fila['Cuota'], "fecha_vencimiento": str(fila['Fecha Vencimiento']), "monto": fila['Monto']}).execute()
            
            path = generar_pdf_contrato({"producto": art, "monto_total": precio, "cuota_inicial": inic}, df_cuo, dat_c, v_id)
            with open(path, "rb") as f:
                st.download_button("📥 Descargar Contrato Legal (3 Páginas)", f, file_name=f"Contrato_{dat_c['cedula']}.pdf")
    else: st.warning("No hay clientes registrados.")

elif choice == "Historial de Ventas":
    st.header("Auditoría de Ventas e Indicadores")
    hist = supabase.table("ventas").select("*, clientes(*)").order("fecha_venta", desc=True).execute()
    if hist.data:
        for r in hist.data:
            with st.expander(f"{r['fecha_venta']} | {r['clientes']['nombre']} - {r['producto']}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Precio Venta:** ${int(r['monto_total']):,}")
                    st.write(f"**Costo Compra:** ${int(r.get('costo_compra',0)):,}")
                with col_b:
                    otros = r.get('gasto_transporte',0) + r.get('gasto_papeleria',0) + r.get('gasto_otros',0)
                    util = r['monto_total'] - (r.get('costo_compra',0) + otros)
                    st.write(f"**Otros Gastos:** ${int(otros):,}")
                    st.write(f"**Utilidad Neta:** ${int(util):,}")
                
                if st.button("Reimprimir Documentos", key=f"re_{r['id']}"):
                    p_res = supabase.table("plan_pagos").select("*").eq("venta_id", r['id']).execute()
                    df_rec = pd.DataFrame(p_res.data).rename(columns={"numero_cuota": "Cuota", "fecha_vencimiento": "Fecha Vencimiento", "monto": "Monto"})
                    path_re = generar_pdf_contrato({"producto": r['producto'], "monto_total": r['monto_total'], "cuota_inicial": r['cuota_inicial']}, df_rec, r['clientes'], r['id'])
                    with open(path_re, "rb") as f:
                        st.download_button("📥 Descargar Reimpresión", f, file_name=f"Contrato_{r['id']}.pdf", key=f"dl_{r['id']}")

elif choice == "Control de Cartera":
    st.header("Gestión de Recaudo")
    busqueda = st.text_input("🔍 Buscar por nombre o cédula")
    ids_clientes = []
    if busqueda:
        res_cli = supabase.table("clientes").select("id").or_(f"nombre.ilike.%{busqueda}%,cedula.ilike.%{busqueda}%").execute()
        ids_clientes = [c['id'] for c in res_cli.data]
    query = supabase.table("ventas").select("*, clientes(*)")
    if busqueda:
        if ids_clientes: query = query.in_("cliente_id", ids_clientes)
        else: query = query.eq("id", -1)
    res = query.execute()
    if res.data:
        opciones = {f"{v['clientes']['nombre']} (CC: {v['clientes']['cedula']}) - {v['producto']}": v for v in res.data}
        sel_venta = st.selectbox("Seleccione la venta", list(opciones.keys()))
        v_sel = opciones[sel_venta]
        
        tab1, tab2 = st.tabs(["Registrar Nuevo Pago", "Histórico de Pagos"])
        with tab1:
            monto_abono = st.number_input("Valor del Abono", min_value=0, step=1000, value=0)
            metodo = st.selectbox("Método de Pago", ["Efectivo", "Nequi", "Daviplata", "Transferencia"])
            if st.button("Registrar y Conciliar"):
                supabase.table("pagos").insert({"venta_id": v_sel['id'], "monto": monto_abono, "metodo_pago": metodo, "fecha_pago": str(datetime.now().date())}).execute()
                resto = monto_abono
                cuotas = supabase.table("plan_pagos").select("*").eq("venta_id", v_sel['id']).order("numero_cuota").execute()
                for cuota in cuotas.data:
                    if resto <= 0: break
                    ya_pagado = cuota.get('pagado') or 0
                    saldo_cuota = cuota['monto'] - ya_pagado
                    if saldo_cuota > 0:
                        aplicado = min(resto, saldo_cuota)
                        nuevo_pagado = ya_pagado + aplicado
                        supabase.table("plan_pagos").update({"pagado": nuevo_pagado, "estado": 'Cancelada' if nuevo_pagado >= cuota['monto'] else 'Abonada'}).eq("id", cuota['id']).execute()
                        resto -= aplicado
                path_recibo = generar_recibo_caja(v_sel['clientes'], monto_abono, metodo, v_sel['producto'])
                with open(path_recibo, "rb") as f:
                    st.download_button("📥 Descargar Recibo", f, file_name="Recibo_Nuevo.pdf")
                st.rerun()
        with tab2:
            pagos_hist = supabase.table("pagos").select("*").eq("venta_id", v_sel['id']).order("fecha_pago", desc=True).execute()
            if pagos_hist.data:
                for p in pagos_hist.data:
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"📅 {p['fecha_pago']} | ${int(p['monto']):,} | {p['metodo_pago']}")
                    if col2.button("Reimprimir", key=f"re_pago_{p['id']}"):
                        path_re = generar_recibo_caja(v_sel['clientes'], p['monto'], p['metodo_pago'], v_sel['producto'])
                        with open(path_re, "rb") as f:
                            st.download_button("📥 Descargar PDF", f, file_name=f"Recibo_Hist_{p['id']}.pdf")
    else: st.info("No se encontraron resultados.")

st.sidebar.caption(f"Ing. Charles | Auditoría CJ&D © {datetime.now().year}")