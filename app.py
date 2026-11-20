import glob
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Invernadero IoT — Análisis Operativo", layout="wide")
st.title("Monitoreo y Análisis Operativo de Invernadero")
st.caption("Dashboard en Streamlit Cloud para evaluación de datos históricos de sensores (CSV)")

# Unidades y rangos operativos sugeridos (ajustables en la barra lateral)
UNIDADES_POR_DEFECTO = {
    "humedad": "% HR",
    "humidity": "% HR",
    "temperatura": "°C",
    "temp": "°C",
    "temperature": "°C",
}

RANGOS_POR_DEFECTO = {
    "humedad": (40.0, 80.0),
    "humidity": (40.0, 80.0),
    "temperatura": (15.0, 32.0),
    "temp": (15.0, 32.0),
    "temperature": (15.0, 32.0),
}

archivos_csv = sorted(glob.glob("*.csv"))

if not archivos_csv:
    st.warning("No se encontraron archivos .csv en el repositorio.")
    st.stop()

st.sidebar.header("Configuración del Sistema")
seleccion = st.sidebar.selectbox("Selecciona el archivo CSV", archivos_csv)

df = pd.read_csv(seleccion, comment="#")

if df.empty:
    st.error("El archivo CSV seleccionado está vacío.")
    st.stop()

# Detectar columna de tiempo
posibles_tiempo = ["time", "_time", "timestamp", "fecha", "date"]
col_tiempo = next((c for c in posibles_tiempo if c in df.columns), None)

if col_tiempo:
    df[col_tiempo] = pd.to_datetime(df[col_tiempo], errors="coerce")

# Normalizar a formato largo si viene en (_time, _field, _value)
if {"_time", "_field", "_value"}.issubset(df.columns):
    df["_value"] = pd.to_numeric(df["_value"], errors="coerce")
    df = df.dropna(subset=["_value"])
    if "_time" in df.columns:
        df["_time"] = pd.to_datetime(df["_time"], errors="coerce")
        df = df.dropna(subset=["_time"]).sort_values("_time")
    variables = sorted(df["_field"].dropna().unique().tolist())
    es_formato_largo = True
else:
    es_formato_largo = False
    cols_num = []
    for c in df.columns:
        if c == col_tiempo:
            continue
        convertida = pd.to_numeric(df[c], errors="coerce")
        if convertida.notna().sum() > 0:
            df[c] = convertida
            cols_num.append(c)
    if col_tiempo:
        df = df.dropna(subset=[col_tiempo]).sort_values(col_tiempo)
    variables = cols_num

if not variables:
    st.error("No se detectaron variables numéricas válidas en el CSV.")
    st.stop()

var_elegida = st.sidebar.selectbox("Variable principal a analizar", variables)

clave_lower = str(var_elegida).strip().lower()
unidad_sugerida = UNIDADES_POR_DEFECTO.get(clave_lower, "unidades")
rango_min_def, rango_max_def = RANGOS_POR_DEFECTO.get(clave_lower, (0.0, 100.0))

unidad = st.sidebar.text_input("Unidad de medida", value=unidad_sugerida)
umbral_min = st.sidebar.number_input(f"Umbral mínimo seguro ({unidad})", value=float(rango_min_def))
umbral_max = st.sidebar.number_input(f"Umbral máximo seguro ({unidad})", value=float(rango_max_def))

if umbral_min > umbral_max:
    st.sidebar.error("El umbral mínimo no puede ser mayor que el umbral máximo.")
    st.stop()

# Extraer serie limpia de la variable elegida
if es_formato_largo:
    serie_df = df[df["_field"] == var_elegida][["_time", "_value"]].rename(
        columns={"_time": "tiempo", "_value": "valor"}
    )
else:
    if col_tiempo:
        serie_df = df[[col_tiempo, var_elegida]].rename(
            columns={col_tiempo: "tiempo", var_elegida: "valor"}
        )
    else:
        serie_df = pd.DataFrame({
            "tiempo": range(len(df)),
            "valor": df[var_elegida],
        })

serie_df = serie_df.dropna(subset=["valor"]).reset_index(drop=True)

if serie_df.empty:
    st.warning(f"No hay datos numéricos válidos para '{var_elegida}'.")
    st.stop()

# Clasificación por umbrales operativos
serie_df["estado"] = "Normal"
serie_df.loc[serie_df["valor"] < umbral_min, "estado"] = "Bajo umbral"
serie_df.loc[serie_df["valor"] > umbral_max, "estado"] = "Sobre umbral"

fuera_de_rango = serie_df[serie_df["estado"] != "Normal"]
pct_fuera = (len(fuera_de_rango) / len(serie_df)) * 100

# 1. Estadísticas clave
st.subheader(f"Estadísticas — {var_elegida.capitalize()} ({unidad})")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Promedio", f"{serie_df['valor'].mean():.2f} {unidad}")
m2.metric("Mínimo", f"{serie_df['valor'].min():.2f} {unidad}")
m3.metric("Máximo", f"{serie_df['valor'].max():.2f} {unidad}")
m4.metric("Último registro", f"{serie_df['valor'].iloc[-1]:.2f} {unidad}")
m5.metric("Fuera de rango", f"{len(fuera_de_rango)} ({pct_fuera:.1f}%)")

# 2. Alertas por umbral
st.subheader("Evaluación de Rangos y Alertas Operativas")
st.info(f"Rango operativo configurado para **{var_elegida}**: **{umbral_min:.2f} {unidad}** a **{umbral_max:.2f} {unidad}**.")

if len(fuera_de_rango) > 0:
    st.warning(
        f"Alerta: se detectaron **{len(fuera_de_rango)}** lecturas fuera del rango seguro "
        f"({(serie_df['estado'] == 'Bajo umbral').sum()} por debajo del mínimo y "
        f"{(serie_df['estado'] == 'Sobre umbral').sum()} por encima del máximo)."
    )
    st.dataframe(fuera_de_rango.tail(30), use_container_width=True)
else:
    st.success("Todas las lecturas registradas se encuentran dentro del rango operativo configurado.")

# 3. Gráfica temporal con referencia de umbrales
st.subheader("Serie Temporal y Referencia de Umbrales")
graf_df = serie_df.set_index("tiempo")[["valor"]].rename(columns={"valor": f"{var_elegida} ({unidad})"})
graf_df[f"Umbral mín ({unidad})"] = umbral_min
graf_df[f"Umbral máx ({unidad})"] = umbral_max
st.line_chart(graf_df)

# 4. Análisis adicional para operación (variación / tendencia y correlación)
st.subheader("Análisis Operativo Adicional")
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Variación / Tendencia del periodo**")
    mitad = max(1, len(serie_df) // 2)
    prom_inicial = serie_df["valor"].iloc[:mitad].mean()
    prom_final = serie_df["valor"].iloc[mitad:].mean()
    delta_prom = prom_final - prom_inicial
    st.write(f"- Promedio primera mitad: **{prom_inicial:.2f} {unidad}**")
    st.write(f"- Promedio segunda mitad: **{prom_final:.2f} {unidad}**")
    st.write(f"- Cambio entre mitades: **{delta_prom:+.2f} {unidad}**")

with col_b:
    st.markdown("**Correlación entre variables numéricas**")
    if not es_formato_largo and len(variables) >= 2:
        corr = df[variables].corr(numeric_only=True)
        st.dataframe(corr.style.format("{:.2f}"), use_container_width=True)
    elif es_formato_largo and len(variables) >= 2:
        pivote = df.pivot_table(index="_time", columns="_field", values="_value", aggfunc="mean")
        if pivote.shape[1] >= 2:
            st.dataframe(pivote.corr().style.format("{:.2f}"), use_container_width=True)
        else:
            st.caption("Se necesitan al menos 2 variables simultáneas para calcular correlación.")
    else:
        st.caption("Este CSV contiene una sola variable numérica; la evaluación se centra en umbrales y variación temporal.")

# 5. Vista previa de datos crudos
with st.expander("Ver vista previa del CSV original"):
    st.dataframe(df.head(50), use_container_width=True)
