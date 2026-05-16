import streamlit as st
try:
    from fpdf import FPDF
    import pandas as pd
    from supabase import create_client
    st.success("✅ Todas las librerías están instaladas correctamente.")
except ImportError as e:
    st.error(f"❌ Falta una librería: {e}")

st.write("Si ves este mensaje, el motor de Streamlit está operativo.")