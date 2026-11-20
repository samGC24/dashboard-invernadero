import glob
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Invernadero IoT", layout="wide")
st.title("Monitoreo de Invernadero")

archivos_csv = sorted(glob.glob("*.csv"))

if not archivos_csv:
    st.warning("No se encontraron archivos .csv en esta carpeta.")
    st.stop()

seleccion = st.selectbox("Selecciona un archivo CSV", archivos_csv)

df = pd.read_csv(seleccion, comment="#")

st.subheader("Vista previa de datos")
st.dataframe(df.head(50), use_container_width=True)

# Detectar columna de tiempo si existe
posibles_tiempo = ["time", "_time", "timestamp", "fecha"]
col_tiempo = next((c for c in posibles_tiempo if c in df.columns), None)

if col_tiempo:
    df[col_tiempo] = pd.to_datetime(df[col_tiempo], errors="coerce")

# Caso 1: formato largo de InfluxDB (_time, _field, _value)
if {"_time", "_field", "_value"}.issubset(df.columns):
    df["_value"] = pd.to_numeric(df["_value"], errors="coerce")
    df = df.dropna(subset=["_time", "_value"])

    variables = sorted(df["_field"].dropna().unique())
    if variables:
        var_elegida = st.selectbox("Variable a graficar", variables)
        filtrado = df[df["_field"] == var_elegida].sort_values("_time")

        st.subheader(f"Resumen de {var_elegida}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Promedio", f"{filtrado['_value'].mean():.2f}")
        c2.metric("Mínimo", f"{filtrado['_value'].min():.2f}")
        c3.metric("Máximo", f"{filtrado['_value'].max():.2f}")

        st.line_chart(filtrado.set_index("_time")["_value"])

# Caso 2: formato ancho como time + humedad / temperatura / etc.
else:
    cols_num = []
    for c in df.columns:
        if c == col_tiempo:
            continue
        convertida = pd.to_numeric(df[c], errors="coerce")
        if convertida.notna().sum() > 0:
            df[c] = convertida
            cols_num.append(c)

    if cols_num:
        var_elegida = st.selectbox("Variable a graficar", cols_num)
        datos_var = df[[col_tiempo, var_elegida]].dropna(subset=[var_elegida]) if col_tiempo else df[[var_elegida]].dropna()

        if col_tiempo:
            datos_var = datos_var.dropna(subset=[col_tiempo]).sort_values(col_tiempo)

        if not datos_var.empty:
            st.subheader(f"Resumen de {var_elegida}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Promedio", f"{datos_var[var_elegida].mean():.2f}")
            c2.metric("Mínimo", f"{datos_var[var_elegida].min():.2f}")
            c3.metric("Máximo", f"{datos_var[var_elegida].max():.2f}")

            if col_tiempo:
                st.line_chart(datos_var.set_index(col_tiempo)[var_elegida])
            else:
                st.line_chart(datos_var[var_elegida])
        else:
            st.info("No hay valores numéricos válidos para graficar en esta variable.")
    else:
        st.info("No se detectaron columnas numéricas para graficar.")
