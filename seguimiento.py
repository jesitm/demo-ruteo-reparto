"""Seguimiento simulado de paquetes: eventos, estado según la hora y línea de tiempo en HTML.

Estados: Pedido recibido -> En depósito -> En camino -> Cerca de destino -> Entregado / No entregado.
Los horarios salen de la hoja de ruta que calculó el optimizador, así que el seguimiento es
coherente con las rutas. Todo es simulado (demo): en producción cada evento lo registra el
chofer con su celular o el sistema de la flota.
"""
from datetime import date, datetime, time, timedelta
from html import escape

import numpy as np
import pandas as pd

ESTADOS = ["Pedido recibido", "En depósito", "En camino", "Cerca de destino", "Entregado", "No entregado"]
ICONOS = {"Pedido recibido": "📋", "En depósito": "🏭", "En camino": "🚚",
          "Cerca de destino": "📍", "Entregado": "✅", "No entregado": "❌"}
COLOR_ESTADO = {"Entregado": "#2E9E5B", "No entregado": "#D64545"}
NARANJA = "#F28C00"
PENDIENTE = {"En depósito": "Se está preparando tu pedido.",
             "En camino": "Saldrá del depósito en el horario previsto.",
             "Cerca de destino": "Te avisaremos por SMS cuando el camión esté cerca.",
             "Entregado": "Entrega estimada."}


def _dia_habil_anterior(fecha):
    d = fecha - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _hm(fecha, hhmm, seg=0):
    return datetime.combine(fecha, time(int(hhmm[:2]), int(hhmm[3:5]), seg))


def generar_seguimiento(paquetes, paradas, rutas, clientes, fecha, seed=0, tasa_ausente=0.07):
    """DataFrame de eventos: codigo, id_cliente, cliente, orden_evento, estado, fecha_hora, detalle.

    - El camión se carga en orden inverso a las paradas (el último en entregarse, primero en subir).
    - 'Cerca de destino': 15 min antes de la llegada estimada (se avisa por SMS al cliente).
    - Un % de clientes no está (tasa_ausente): sus paquetes quedan 'No entregado'.
    - Los paquetes de clientes sin ruta quedan 'En depósito' (se reprograman).
    """
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    par = paradas.set_index("id_cliente")
    rut = rutas.set_index("camion")
    tel = clientes.set_index("id_cliente")["telefono"]
    prev = _dia_habil_anterior(fecha)

    pq = paquetes.copy()
    pq["camion"] = pq["id_cliente"].map(par["camion"])
    pq["orden"] = pq["id_cliente"].map(par["orden"])

    carga = {}  # codigo -> (posición de carga, total del camión)
    for _, g in pq.dropna(subset=["camion"]).groupby("camion"):
        g = g.sort_values(["orden", "codigo"], ascending=[False, True])
        for k, cod in enumerate(g["codigo"], start=1):
            carga[cod] = (k, len(g))

    filas = []

    def add(p, i, estado, ts, detalle, eta=""):
        filas.append({"codigo": p["codigo"], "id_cliente": p["id_cliente"], "cliente": p["cliente"],
                      "orden_evento": i, "estado": estado, "fecha_hora": ts, "detalle": detalle,
                      "llegada_estimada": eta})

    for _, p in pq.iterrows():
        num = int(p["id_cliente"][1:])
        rng = np.random.default_rng([int(seed), num, int(p["paquete_n"]), 7])
        seg = lambda: int(rng.integers(0, 60))
        telefono = tel.get(p["id_cliente"], "")

        add(p, 0, "Pedido recibido",
            datetime.combine(prev, time(int(rng.integers(9, 18)), int(rng.integers(0, 60)), seg())),
            "Hemos recibido tu pedido.")

        if pd.isna(p["camion"]):  # sin ruta hoy
            add(p, 1, "En depósito", datetime.combine(fecha, time(9, int(rng.integers(0, 50)), seg())),
                "Paquete preparado. Hoy no entró en ninguna ruta: se reprograma para el próximo día hábil.")
            continue

        r, s = rut.loc[p["camion"]], par.loc[p["id_cliente"]]
        dep = _hm(fecha, r["salida_deposito"], seg())
        k, n = carga[p["codigo"]]
        t_carga = dep - timedelta(minutes=90) + timedelta(minutes=int(k * 80 / (n + 1)), seconds=seg())
        add(p, 1, "En depósito", t_carga,
            f"Paquete preparado y cargado en {p['camion']} ({s['patente']}).", s["llegada"])
        add(p, 2, "En camino", dep,
            f"El camión {p['camion']} ({s['patente']}) salió del depósito. "
            f"Tu entrega es la parada {int(s['orden'])} de {int(r['paradas'])}.", s["llegada"])

        llegada = _hm(fecha, s["llegada"], seg())
        salida = max(_hm(fecha, s["salida"], seg()), llegada + timedelta(seconds=60))
        cerca = max(dep + timedelta(minutes=1), llegada - timedelta(minutes=15))
        if cerca >= llegada:
            cerca = llegada - timedelta(seconds=30)
        add(p, 3, "Cerca de destino", cerca,
            f"El camión está a pocos minutos de {s['direccion']}. Llegada estimada {s['llegada']}. "
            f"Aviso enviado por SMS al {telefono}.", s["llegada"])

        ausente = np.random.default_rng([int(seed), num, 99]).random() < tasa_ausente
        if ausente:
            add(p, 4, "No entregado", llegada + timedelta(minutes=6),
                f"Cliente ausente en {s['direccion']}. Se intentó contactar al {telefono}. "
                "Se reprogramará la entrega para el próximo día hábil.", s["llegada"])
        else:
            add(p, 4, "Entregado", salida, f"Entregado en {s['direccion']}.", s["llegada"])
    return pd.DataFrame(filas)


def estado_actual(eventos, ahora):
    """Último estado de cada paquete a la hora simulada `ahora` (datetime)."""
    e = eventos[eventos["fecha_hora"] <= ahora].sort_values(["fecha_hora", "orden_evento"])
    out = e.groupby("codigo").tail(1)[["codigo", "estado", "fecha_hora"]]
    return out.rename(columns={"fecha_hora": "desde"}).reset_index(drop=True)


def resumen_estados(actual):
    """Cantidad de paquetes por estado, en el orden del recorrido."""
    return actual["estado"].value_counts().reindex(ESTADOS, fill_value=0)


def timeline_html(codigo, eventos, ahora, info):
    """Línea de tiempo de un paquete. info: cliente, direccion, telefono, camion, patente.
    Los pasos futuros se ven en gris con la hora estimada; el resultado final no se anticipa."""
    ev = eventos[eventos["codigo"] == codigo].sort_values("orden_evento")
    hechos = ev[ev["fecha_hora"] <= ahora]
    actual = hechos.iloc[-1]["estado"] if len(hechos) else "Pedido recibido"
    final = actual in ("Entregado", "No entregado")
    color = COLOR_ESTADO.get(actual, NARANJA)

    if final:
        sub = f"{actual} el {hechos.iloc[-1]['fecha_hora']:%d/%m/%Y a las %H:%M}"
    else:
        etas = ev.loc[ev["llegada_estimada"] != "", "llegada_estimada"]
        eta = etas.iloc[0] if len(etas) else ""
        if eta:
            sub = f"Llegada estimada: {eta}"
        else:
            sub = "Sin ruta asignada hoy: se reprograma para el próximo día hábil"

    pasos = []
    for _, e in ev.iterrows():
        hecho = e["fecha_hora"] <= ahora
        estado, detalle = e["estado"], e["detalle"]
        if not hecho and estado == "No entregado":  # no anticipar que el cliente no estará
            estado = "Entregado"
        if hecho:
            fecha_txt = f"{e['fecha_hora']:%d/%m/%Y - %H:%M:%S}"
        else:
            fecha_txt = f"Estimado {e['fecha_hora']:%H:%M}" if estado != "Pedido recibido" else ""
        clase = "hecho" if hecho else "pend"
        col = COLOR_ESTADO.get(estado, NARANJA) if hecho else "#B8BDC6"
        det = escape(detalle) if hecho else escape(PENDIENTE.get(estado, ""))
        pasos.append(
            f'<div class="it {clase}"><div class="ico" style="border-color:{col}">{ICONOS[estado]}</div>'
            f'<div class="tx"><b style="color:{col}">{escape(estado)}</b>'
            f'<small>{escape(fecha_txt)}</small><p>{det}</p></div></div>')

    css = f"""
    body{{font-family:Segoe UI,Roboto,Arial,sans-serif;margin:0;color:#222;background:#fff}}
    .card{{background:#F6F7F9;border:1px solid #E3E6EA;border-radius:10px;padding:14px 16px;margin-bottom:14px}}
    .badge{{display:inline-block;background:{color};color:#fff;font-weight:600;border-radius:6px;padding:4px 12px}}
    .card p{{margin:8px 0 0;font-size:14px}} .card .cod{{font-size:12px;color:#666;margin-top:6px}}
    .it{{display:flex;position:relative;padding-bottom:18px}}
    .it:not(:last-child)::before{{content:"";position:absolute;left:19px;top:40px;bottom:0;width:3px;background:#B8BDC6}}
    .it.hecho:not(:last-child)::before{{background:{NARANJA}}}
    .ico{{flex:0 0 40px;height:40px;border:3px solid;border-radius:50%;display:flex;align-items:center;
          justify-content:center;font-size:18px;background:#fff;margin-right:14px}}
    .it.pend .ico{{opacity:.55}} .it.pend .tx{{opacity:.75}}
    .tx b{{font-size:17px;display:block}} .tx small{{color:#666;font-size:12.5px;display:block;margin:2px 0}}
    .tx p{{margin:2px 0 0;font-size:14px}}"""
    cab = (f'<div class="card"><span class="badge">{escape(actual)}</span>'
           f'<p><b>{escape(sub)}</b></p>'
           f'<p>{escape(info["cliente"])} · {escape(info["direccion"])}<br>Tel. {escape(info["telefono"])}'
           + (f' · {escape(str(info["camion"]))} ({escape(str(info["patente"]))})' if info.get("camion") else "")
           + f'</p><div class="cod">Código de seguimiento: {escape(codigo)}</div></div>')
    html = f"<style>{css}</style>{cab}{''.join(pasos)}"
    return html, 250 + 92 * len(pasos)
