import glob
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Invernadero IoT", layout="wide")
st.title("Monitoreo de Invernadero — Datos InfluxDB")

archivos_csv = sorted(glob.glob("*.csv"))

if not archivos_csv:
    st.warning("No se encontraron archivos .csv en esta carpeta.")
    st.stop()

seleccion = st.selectbox("Selecciona un archivo CSV", archivos_csv)

df = pd.read_csv(seleccion, comment="#")

st.subheader("Vista previa de datos")
st.dataframe(df.head(50), use_container_width=True)

if {"_time", "_field", "_value"}.issubset(df.columns):
    df["_time"] = pd.to_datetime(df["_time"], errors="coerce")
    df["_value"] = pd.to_numeric(df["_value"], errors="coerce")
    df = df.dropna(subset=["_time", "_value"])

    variables = sorted(df["_field"].dropna().unique())
    if variables:
        var_elegida = st.selectbox("Variable a graficar", variables)
        filtrado = df[df["_field"] == var_elegida].sort_values("_time")

        c1, c2, c3 = st.columns(3)
        c1.metric("Promedio", f"{filtrado['_value'].mean():.2f}")
        c2.metric("Mínimo", f"{filtrado['_value'].min():.2f}")
        c3.metric("Máximo", f"{filtrado['_value'].max():.2f}")

        st.line_chart(filtrado.set_index("_time")["_value"])
else:
    cols_num = df.select_dtypes(include="number").columns.tolist()
    if cols_num:
        elegidas = st.multiselect("Columnas numéricas", cols_num, default=cols_num[:3])
        if elegidas:
            st.line_chart(df[elegidas])