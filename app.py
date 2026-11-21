"""App Streamlit: demo de ruteo de camiones desde el Parque Industrial Pilar.
Ejecutar:  streamlit run app.py
"""
import io
from datetime import date, datetime, time, timedelta
from html import escape

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import datos as _datos

COLORES = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue",
           "darkgreen", "black", "pink", "gray", "lightblue"]

VERSION = "v1.5 (teléfono de contacto + seguimiento de paquetes)"

st.set_page_config(page_title="Reparto de mercadería", layout="wide")

if not (hasattr(_datos, "generar_paquetes") and hasattr(_datos, "en_agua")):
    st.error("⚠️ datos.py es una versión vieja. Reemplazá todos los archivos por los del zip, "
             "reiniciá Streamlit por completo y refrescá el navegador.")
    st.stop()

from datos import DEPOSITO, RADIO_KM, flota_default, generar_clientes, generar_paquetes
from distancias import OSRM_PUBLICO, geometria_osrm
from optimizador import asignar_paquetes, optimizar
from pdf_rutas import generar_pdf
from seguimiento import (ESTADOS, estado_actual, generar_seguimiento, resumen_estados,
                         timeline_html)
st.title("🚚 Organización de reparto de mercadería")
st.caption(f"Depósito: {DEPOSITO['nombre']} · radio de reparto {RADIO_KM} km · datos de demostración")

# ---------------- Parámetros ----------------
with st.sidebar:
    st.header("Parámetros")
    n_clientes = st.slider("Clientes del día", 20, 150, 80, 5)
    n_camiones = st.slider("Camiones", 3, 15, 10)
    c1, c2 = st.columns(2)
    inicio_h = c1.number_input("Inicio (h)", 6, 12, 10)
    fin_h = c2.number_input("Fin (h)", 13, 22, 18)
    d1, d2 = st.slider("Descarga por cliente (min)", 5, 60, (10, 30))
    velocidad = st.slider("Velocidad media (km/h)", 30, 80, 50)
    factor = st.slider("Factor de ruta vs línea recta", 1.0, 1.8, 1.3, 0.05)
    t_lim = st.slider("Tiempo de cálculo (s)", 5, 120, 20)
    seed = st.number_input("Semilla (día)", 0, 99999, 42)
    fecha_rep = st.date_input("Fecha de reparto", date.today(),
                              help="Se usa en el código de cada paquete (PQ-AAMMDD-cliente-paquete).")
    ausencia = st.slider("Clientes ausentes al entregar (%)", 0, 30, 8,
                         help="Porcentaje de clientes que no están: sus paquetes quedan 'No entregado'.")
    st.divider()
    balancear = st.checkbox("Equilibrar jornadas entre camiones", value=True,
                            help="Reparte el trabajo entre más camiones en vez de saturar pocos.")
    usar_osrm = st.checkbox("Rutas reales por calle (OSRM)", value=False,
                            help="Requiere internet o un servidor OSRM propio.")
    osrm_url = st.text_input("URL de OSRM", OSRM_PUBLICO) if usar_osrm else None
    if st.button("🎲 Generar otro día"):
        st.session_state["seed_extra"] = st.session_state.get("seed_extra", 0) + 1
    calcular = st.button("▶️ Optimizar", type="primary")
    st.caption(f"Versión {VERSION}")

seed_efectiva = int(seed) + st.session_state.get("seed_extra", 0)
clientes = generar_clientes(n_clientes, seed_efectiva, d1, d2)
paquetes = generar_paquetes(clientes, fecha_rep, seed_efectiva)

# Autodiagnóstico: avisa si algún cliente cae en el agua
n_agua = sum(_datos.en_agua(a, b, 0) for a, b in zip(clientes["lat"], clientes["lon"]))
if n_agua:
    st.warning(f"{n_agua} cliente(s) caen en el agua. Mandame una captura para ajustar el polígono.")
flota = flota_default(n_camiones)

with st.expander("Flota, clientes y paquetes del día", expanded=False):
    st.caption("Flota (patentes inventadas)")
    st.dataframe(flota, use_container_width=True, hide_index=True)
    st.caption("Clientes (nombres y direcciones ficticios; las coordenadas del mapa son aleatorias)")
    st.dataframe(clientes.drop(columns=["direccion", "cp", "lat", "lon"]),
                 use_container_width=True, hide_index=True)
    st.caption(f"Paquetes ({len(paquetes)}) con su código")
    st.dataframe(paquetes, use_container_width=True, hide_index=True)

# ---------------- Cálculo ----------------
if calcular:
    with st.spinner("Optimizando rutas..."):
        try:
            st.session_state["res"] = optimizar(
                clientes, flota, inicio_h, fin_h, factor, velocidad, t_lim,
                balanceo=1000 if balancear else 0, osrm_url=osrm_url, paquetes=paquetes)
            st.session_state["osrm_url_res"] = osrm_url
            st.session_state["clientes_res"] = clientes
            st.session_state["paquetes_res"] = paquetes
            st.session_state["fecha_res"] = fecha_rep
            st.session_state["seed_res"] = seed_efectiva
            st.session_state["ausencia_res"] = ausencia
        except Exception as e:
            st.error(str(e))

res = st.session_state.get("res")
if res is None:
    st.info("Ajustá los parámetros y presioná **Optimizar**.")
    st.stop()

rutas, paradas, sin_asignar = res
cli = st.session_state["clientes_res"]
paq = st.session_state["paquetes_res"]
fecha_res = st.session_state["fecha_res"]
osrm_res = st.session_state.get("osrm_url_res")
fuente = rutas.attrs.get("fuente_distancias", "simple")
if osrm_res and fuente != "osrm":
    st.warning(f"No se pudo usar OSRM, se usó el modelo simple. Detalle: {fuente}")
else:
    st.caption(f"Distancias y tiempos: {'OSRM (por calle)' if fuente == 'osrm' else 'modelo simple (línea recta x factor)'}")

# ---------------- Indicadores ----------------
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Km totales", f"{rutas['km'].sum():,.0f}")
k2.metric("Camiones usados", f"{len(rutas)} / {len(flota)}")
k3.metric("Entregas", f"{len(paradas)} / {len(cli)}")
k6.metric("Paquetes", f"{int(paradas['paquetes'].sum())} / {len(paq)}")
k4.metric("Uso de capacidad", f"{rutas['carga_kg'].sum() / rutas['capacidad_kg'].sum() * 100:.0f}%")
k5.metric("Sin asignar", len(sin_asignar))

# ---------------- Mapa ----------------
@st.cache_data(show_spinner=False)
def _trazado(puntos, url):
    return geometria_osrm(list(puntos), url)

m = folium.Map(location=[DEPOSITO["lat"], DEPOSITO["lon"]], zoom_start=9, tiles=None)
folium.TileLayer("OpenStreetMap", referrer_policy="strict-origin-when-cross-origin").add_to(m)
folium.Circle([DEPOSITO["lat"], DEPOSITO["lon"]], radius=RADIO_KM * 1000,
              color="#888", fill=False, dash_array="6").add_to(m)
folium.Marker([DEPOSITO["lat"], DEPOSITO["lon"]], tooltip=DEPOSITO["nombre"],
              icon=folium.Icon(color="black", icon="home")).add_to(m)

for i, (camion, g) in enumerate(paradas.groupby("camion")):
    color = COLORES[i % len(COLORES)]
    g = g.sort_values("orden")
    puntos = [(DEPOSITO["lat"], DEPOSITO["lon"])] + list(zip(g["lat"], g["lon"])) + \
             [(DEPOSITO["lat"], DEPOSITO["lon"])]
    trazado = _trazado(tuple(puntos), osrm_res) if fuente == "osrm" else None
    folium.PolyLine(trazado or puntos, color=color, weight=3, opacity=0.8, tooltip=f"{camion} · {g['patente'].iloc[0]}").add_to(m)
    for _, p in g.iterrows():
        folium.CircleMarker(
            [p["lat"], p["lon"]], radius=6, color=color, fill=True, fill_opacity=0.9,
            tooltip=f"{camion} · #{p['orden']} {p['cliente']} ({p['llegada']})",
            popup=folium.Popup(
                f"<b>{escape(p['cliente'])}</b><br>{escape(p['direccion'])}<br>"
                f"{camion} ({escape(p['patente'])}) · parada #{p['orden']}<br>"
                f"Tel. {escape(p['telefono'])}<br>"
                f"Llegada {p['llegada']} · descarga {p['descarga_min']} min<br>"
                f"{p['paquetes']} paquete(s) · {p['demanda_kg']} kg<br>"
                f"<small>{escape(p['codigos'])}</small>", max_width=320),
        ).add_to(m)
for _, p in sin_asignar.iterrows():
    folium.CircleMarker([p["lat"], p["lon"]], radius=6, color="red", fill=False,
                        tooltip=f"SIN ASIGNAR: {p['cliente']} · {p['direccion_completa']}").add_to(m)

components.html(m._repr_html_(), height=560)
st.caption("Con el modelo simple las líneas unen las paradas en orden (no siguen calles). Círculos rojos vacíos = pedidos sin asignar.")

# ---------------- Detalle ----------------
st.subheader("Resumen por camión")
st.dataframe(rutas, use_container_width=True, hide_index=True)

st.subheader("Hoja de ruta")
sel = st.selectbox("Camión", ["Todos"] + list(rutas["camion"]))
det = paradas if sel == "Todos" else paradas[paradas["camion"] == sel]
st.dataframe(det.drop(columns=["lat", "lon"]), use_container_width=True, hide_index=True)

# ---------------- Seguimiento de paquetes ----------------
paq_asig = asignar_paquetes(paq, paradas, cli)
eventos = generar_seguimiento(paq, paradas, rutas, cli, fecha_res,
                              seed=st.session_state.get("seed_res", 0),
                              tasa_ausente=st.session_state.get("ausencia_res", 8) / 100)

st.subheader("Seguimiento de paquetes")
st.caption("Simulación: movés la hora del día y cada paquete cambia de estado según el horario "
           "que calculó el optimizador. En producción lo registraría el chofer desde su celular.")
hora = st.slider("Hora simulada del día", time(8, 0), time(19, 0), time(11, 0),
                 step=timedelta(minutes=5), format="HH:mm")
ahora = datetime.combine(fecha_res, hora)
actual = estado_actual(eventos, ahora)
conteo = resumen_estados(actual)
for col, est in zip(st.columns(len(ESTADOS)), ESTADOS):
    col.metric(est, int(conteo[est]))

paq_est = paq_asig.merge(actual[["codigo", "estado"]], on="codigo", how="left")
paq_est = paq_est[["codigo", "estado", "camion", "patente", "orden", "llegada",
                   "cliente", "telefono", "direccion", "peso_kg"]]
codigo_sel = st.selectbox("Ver el seguimiento de un paquete (escribí para buscar)",
                          list(paq_est["codigo"]), index=None, placeholder="PQ-AAMMDD-000-00")
if codigo_sel:
    fila = paq_est[paq_est["codigo"] == codigo_sel].iloc[0]
    info = {"cliente": fila["cliente"], "direccion": fila["direccion"], "telefono": fila["telefono"],
            "camion": fila["camion"] if fila["camion"] != "SIN ASIGNAR" else "",
            "patente": fila["patente"]}
    html_tl, alto = timeline_html(codigo_sel, eventos, ahora, info)
    components.html(html_tl, height=min(alto, 900), scrolling=True)
with st.expander("Ver todos los paquetes con su estado a la hora simulada"):
    st.dataframe(paq_est, use_container_width=True, hide_index=True)

if len(sin_asignar):
    st.subheader("Pedidos sin asignar")
    st.dataframe(sin_asignar, use_container_width=True, hide_index=True)

# ---------------- Exportación ----------------
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    rutas.to_excel(xw, "Resumen", index=False)
    paradas.to_excel(xw, "Hoja de ruta", index=False)
    paq_asig.to_excel(xw, "Paquetes", index=False)
    eventos.drop(columns=["orden_evento"]).to_excel(xw, "Seguimiento", index=False)
    sin_asignar.to_excel(xw, "Sin asignar", index=False)
pdf_bytes = generar_pdf(rutas, paradas, DEPOSITO["nombre"], fecha=fecha_res.strftime("%d/%m/%Y"),
                       sin_asignar=sin_asignar)
c1, c2 = st.columns(2)
c1.download_button("📄 Hojas de ruta en PDF (una por chofer)", pdf_bytes, "hojas_de_ruta.pdf", "application/pdf")
c2.download_button("📥 Exportar a Excel", buf.getvalue(), "hoja_de_ruta.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
