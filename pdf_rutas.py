"""PDF de hojas de ruta: una página de resumen del día + una hoja por camión/chofer."""
import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

AZUL = colors.HexColor("#1F3A5F")
GRIS = colors.HexColor("#F1F3F6")


def _tabla(datos, anchos, cabecera=True, alinear_der=()):
    t = Table(datos, colWidths=anchos, repeatRows=1 if cabecera else 0)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8CDD5")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if cabecera:
        estilo += [("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                   ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS])]
    for c in alinear_der:
        estilo.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(estilo))
    return t


def _pie(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(15 * mm, 8 * mm, "Hoja de ruta - documento generado automáticamente")
    canvas.drawRightString(landscape(A4)[0] - 15 * mm, 8 * mm, f"Página {doc.page}")
    canvas.restoreState()


def generar_pdf(rutas, paradas, deposito_nombre="Depósito", fecha=None, sin_asignar=None):
    """Devuelve bytes del PDF. `rutas` y `paradas` son los DataFrames del optimizador."""
    fecha = fecha or date.today().strftime("%d/%m/%Y")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=18,
                        textColor=AZUL, alignment=0, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=10, textColor=colors.HexColor("#555555"))
    norm = ParagraphStyle("n", parent=ss["Normal"], fontSize=9)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="Hojas de ruta", author="Sistema de reparto")
    ancho = landscape(A4)[0] - 30 * mm
    el = []

    # ---- Resumen del día ----
    el += [Paragraph("Resumen del día de reparto", h1),
           Paragraph(f"{deposito_nombre} · {fecha}", sub), Spacer(1, 6 * mm)]
    ind = [["Camiones usados", "Entregas", "Km totales", "Carga total (kg)", "Sin asignar"],
           [str(len(rutas)), str(len(paradas)), f"{rutas['km'].sum():,.0f}",
            f"{rutas['carga_kg'].sum():,.0f}", str(0 if sin_asignar is None else len(sin_asignar))]]
    t = _tabla(ind, [ancho / 5] * 5)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 1), (-1, 1), 14),
                           ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold")]))
    el += [t, Spacer(1, 6 * mm)]
    filas = [["Camión", "Patente", "Tipo", "Paradas", "Paquetes", "Carga (kg)", "Uso", "Km", "Salida", "Regreso"]]
    for _, r in rutas.iterrows():
        n_paq = int(paradas.loc[paradas["camion"] == r["camion"], "paquetes"].sum())
        filas.append([r["camion"], r["patente"], r["tipo"], r["paradas"], n_paq, f"{r['carga_kg']:,}",
                      f"{r['uso_capacidad_%']:.0f}%", f"{r['km']:.1f}",
                      r["salida_deposito"], r["regreso_deposito"]])
    el.append(_tabla(filas, [ancho * x for x in (.12, .12, .10, .08, .09, .11, .08, .09, .10, .11)],
                     alinear_der=(3, 4, 5, 6, 7)))

    # ---- Una hoja por camión ----
    chico = ParagraphStyle("c", parent=norm, fontSize=8, leading=10)
    for _, r in rutas.iterrows():
        el.append(PageBreak())
        el += [Paragraph(f"{r['camion']} · {r['tipo']} · Patente {escape(r['patente'])}", h1),
               Paragraph(f"{escape(deposito_nombre)} · {fecha}", sub), Spacer(1, 4 * mm)]
        g = paradas[paradas["camion"] == r["camion"]].sort_values("orden")
        datos_c = [["Salida", "Regreso est.", "Paradas", "Paquetes", "Km est.", "Carga", "Capacidad"],
                   [r["salida_deposito"], r["regreso_deposito"], str(r["paradas"]),
                    str(int(g["paquetes"].sum())), f"{r['km']:.1f}", f"{r['carga_kg']:,} kg",
                    f"{r['capacidad_kg']:,} kg ({r['uso_capacidad_%']:.0f}%)"]]
        el += [_tabla(datos_c, [ancho / 7] * 7), Spacer(1, 5 * mm)]

        filas = [["#", "Llegada", "Cliente", "Dirección", "Paquetes (códigos)", "Kg", "Descarga", "Recibió / Firma"]]
        for _, p in g.iterrows():
            cods = "<br/>".join(escape(c) for c in str(p["codigos"]).split(" · ") if c)
            filas.append([p["orden"], p["llegada"],
                          Paragraph(f"<b>{escape(p['cliente'])}</b><br/>{escape(p['id_cliente'])}<br/>Tel. {escape(p['telefono'])}", chico),
                          Paragraph(escape(p["direccion"]), chico),
                          Paragraph(cods, chico),
                          f"{p['demanda_kg']:,}", f"{p['descarga_min']} min", ""])
        filas.append(["", "", "", "Total", f"{int(g['paquetes'].sum())} paquetes",
                      f"{int(g['demanda_kg'].sum()):,}", "", ""])
        t = _tabla(filas, [ancho * x for x in (.04, .07, .19, .21, .19, .06, .08, .16)], alinear_der=(5,))
        t.setStyle(TableStyle([("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                               ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DDE3EC")),
                               ("TOPPADDING", (0, 1), (-1, -2), 5), ("BOTTOMPADDING", (0, 1), (-1, -2), 5)]))
        el += [t, Spacer(1, 6 * mm),
               Paragraph("Horarios estimados. Conductor: ______________________   Firma: ______________________", norm)]

    doc.build(el, onFirstPage=_pie, onLaterPages=_pie)
    return buf.getvalue()
