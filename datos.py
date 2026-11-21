"""Generación de datos de demo: depósito, flota y clientes alrededor de Pilar."""
import math
from datetime import date
import numpy as np
import pandas as pd

DEPOSITO = {"nombre": "Parque Industrial Pilar", "lat": -34.4600, "lon": -58.9150}
RADIO_KM = 100

# (localidad, lat, lon, peso relativo, dispersión en grados ~ 1° ≈ 111 km)
LOCALIDADES = [
    ("Pilar", -34.458, -58.914, 10, 0.040),
    ("Escobar", -34.349, -58.790, 7, 0.030),
    ("Gral. Rodríguez", -34.609, -58.950, 4, 0.030),
    ("Luján", -34.570, -59.105, 5, 0.030),
    ("San Miguel", -34.543, -58.712, 6, 0.030),
    ("Moreno", -34.634, -58.791, 6, 0.035),
    ("Merlo", -34.665, -58.727, 5, 0.030),
    ("Tigre", -34.426, -58.580, 5, 0.025),
    ("Campana", -34.163, -58.959, 4, 0.020),
    ("Zárate", -34.098, -59.027, 3, 0.015),
    ("Exaltación de la Cruz", -34.330, -59.200, 3, 0.030),
    ("San A. de Giles", -34.449, -59.446, 2, 0.025),
    ("Mercedes", -34.655, -59.430, 2, 0.025),
    ("Cañuelas", -35.052, -58.759, 3, 0.030),
    ("Morón / Ituzaingó", -34.651, -58.619, 5, 0.030),
    ("CABA", -34.604, -58.382, 6, 0.040),
    ("Ezeiza", -34.855, -58.520, 2, 0.030),
    ("Lobos", -35.180, -59.090, 1, 0.020),
]


# Zona de agua aproximada (Río de la Plata + Delta del Paraná), como polígono (lat, lon).
# El borde sigue la costa de Zárate -> Campana -> Escobar -> Tigre -> CABA -> Quilmes y se
# cierra mar adentro. Es una aproximación (error de 1-2 km) pensada para el demo.
AGUA = [
    (-34.07, -59.05), (-34.10, -58.97), (-34.15, -58.93), (-34.20, -58.88),
    (-34.30, -58.76), (-34.37, -58.66), (-34.41, -58.59), (-34.44, -58.53),
    (-34.50, -58.48), (-34.55, -58.42), (-34.60, -58.36), (-34.66, -58.33),
    (-34.80, -58.20), (-34.80, -57.80), (-33.90, -57.80), (-33.90, -59.05),
]


def _en_poligono(lat, lon, poligono):
    """Ray casting: True si (lat, lon) está dentro del polígono."""
    dentro = False
    n = len(poligono)
    for i in range(n):
        y1, x1 = poligono[i]
        y2, x2 = poligono[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cruce = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_cruce:
                dentro = not dentro
    return dentro


def en_agua(lat, lon, margen=0.006):
    """True si el punto cae en el agua o a menos de ~0,7 km de la costa (hacia el agua)."""
    return _en_poligono(lat, lon, AGUA) or _en_poligono(lat + margen, lon + margen, AGUA)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Datos ficticios para personalizar el demo (nombres, direcciones, patentes)
# ---------------------------------------------------------------------------
NOMBRES = ["Juan", "María", "Carlos", "Laura", "Pedro", "Marcela", "Diego", "Silvia", "Martín",
           "Claudia", "Alejandro", "Patricia", "Fernando", "Gabriela", "Ricardo", "Norma",
           "Sergio", "Mónica", "Javier", "Susana", "Héctor", "Andrea", "Raúl", "Verónica",
           "Gustavo", "Natalia", "Pablo", "Liliana", "Daniel", "Carolina", "Hugo", "Romina"]
APELLIDOS = ["González", "Rodríguez", "Gómez", "Fernández", "López", "Díaz", "Martínez", "Pérez",
             "Romero", "Sánchez", "García", "Sosa", "Álvarez", "Torres", "Ruiz", "Ramírez",
             "Acosta", "Benítez", "Medina", "Herrera", "Suárez", "Aguirre", "Giménez", "Gutiérrez",
             "Molina", "Silva", "Castro", "Rojas", "Ortiz", "Núñez", "Luna", "Cabrera", "Ríos",
             "Domínguez", "Vega", "Morales", "Ponce", "Peralta", "Quiroga", "Bustos"]
RUBROS = ["Ferretería", "Corralón", "Supermercado", "Distribuidora", "Panadería", "Almacén",
          "Autoservicio", "Pinturería", "Bazar", "Mercado", "Librería", "Agroveterinaria",
          "Electricidad", "Materiales de Construcción", "Forrajería", "Despensa"]
FANTASIA = ["El Progreso", "La Esquina", "Los Andes", "Don Pedro", "San Cayetano", "El Trébol",
            "La Unión", "Las Palmas", "Del Centro", "El Faro", "La Estrella", "Pampa",
            "El Sol", "La Cascada", "Los Pinos", "San José", "Central", "El Molino"]
CALLES = ["San Martín", "Belgrano", "Mitre", "Sarmiento", "Moreno", "Independencia", "Alsina",
          "Lavalle", "Colón", "Roca", "Güemes", "Italia", "Libertad", "25 de Mayo", "Urquiza",
          "Tucumán", "Entre Ríos", "Pellegrini", "Rivadavia", "9 de Julio", "Maipú", "Córdoba",
          "Corrientes", "Santa Fe", "Salta", "Balcarce", "Brown", "Las Heras", "Alvear", "Perú"]
AVENIDAS = ["Av. Hipólito Yrigoyen", "Av. Presidente Perón", "Av. Rivadavia", "Av. San Martín",
            "Av. Libertador", "Av. Mitre", "Av. del Trabajo", "Av. Constitución"]
URBANAS = {"CABA", "Morón / Ituzaingó", "San Miguel", "Moreno", "Merlo", "Tigre"}
# Códigos postales argentinos aproximados por localidad (demo)
CP = {"Pilar": "B1629", "Escobar": "B1625", "Gral. Rodríguez": "B1748", "Luján": "B6700",
      "San Miguel": "B1663", "Moreno": "B1744", "Merlo": "B1722", "Tigre": "B1648",
      "Campana": "B2804", "Zárate": "B2800", "Exaltación de la Cruz": "B2812",
      "San A. de Giles": "B6720", "Mercedes": "B6600", "Cañuelas": "B1814",
      "Morón / Ituzaingó": "B1708", "CABA": "C1000", "Ezeiza": "B1804", "Lobos": "B7240"}
LETRAS_PATENTE = "ABCDEFGHJKLMNPRSTUVWXYZ"  # sin I, O, Q, Ñ
# Característica telefónica por localidad (el resto del AMBA usa 11)
AREA = {"Luján": "2323", "Mercedes": "2324", "Campana": "3489", "Zárate": "3487",
        "Cañuelas": "2226", "Lobos": "2227", "San A. de Giles": "2325",
        "Exaltación de la Cruz": "3232"}


def _pick(rng, opciones):
    return opciones[int(rng.integers(len(opciones)))]


def _telefono(rng, localidad):
    """Celular inventado en formato internacional argentino (+54 9 ...)."""
    area = AREA.get(localidad, "11")
    if area == "11":
        return f"+54 9 11 {int(rng.integers(2000, 8000))}-{int(rng.integers(0, 10000)):04d}"
    return f"+54 9 {area} {int(rng.integers(40, 70))}-{int(rng.integers(0, 10000)):04d}"


def _nombre_cliente(rng, usados):
    """Persona (nombre y apellido) o razón social. Evita repetidos en el mismo día."""
    for _ in range(60):
        if rng.random() < 0.4:
            nom = f"{_pick(rng, NOMBRES)} {_pick(rng, APELLIDOS)}"
        elif rng.random() < 0.55:
            nom = f"{_pick(rng, RUBROS)} {_pick(rng, FANTASIA)} {_pick(rng, ['S.R.L.', 'S.A.', 'S.A.S.', ''])}"
        else:
            nom = f"{_pick(rng, RUBROS)} {_pick(rng, APELLIDOS)} {_pick(rng, ['S.R.L.', 'S.A.', 'e Hijos', 'Hnos.'])}"
        nom = nom.strip()
        if nom not in usados:
            usados.add(nom)
            return nom
    nom = f"{nom} ({len(usados) + 1})"
    usados.add(nom)
    return nom


def _direccion(rng, localidad):
    """Calle y número, con piso/dto. o local en zonas urbanas (ficticia)."""
    calle = _pick(rng, AVENIDAS) if rng.random() < 0.2 else _pick(rng, CALLES)
    d = f"{calle} {int(rng.integers(1, 49)) * 100 + int(rng.integers(0, 100))}"
    r = rng.random()
    if localidad in URBANAS and r < 0.15:
        d += f", Piso {int(rng.integers(1, 9))} Dto. {_pick(rng, 'ABCD')}"
    elif r > 0.90:
        d += f", Local {int(rng.integers(1, 15))}"
    return d


def generar_clientes(n=80, seed=42, descarga_min=10, descarga_max=30,
                     demanda_min=40, demanda_max=450):
    """Clientes sobre localidades reales con algo de dispersión (evita caer al río).

    Cada cliente tiene: id, nombre o razón social, dirección (calle y número), CP, teléfono,
    coordenadas, cantidad de paquetes, demanda total (kg) y tiempo de descarga.
    Las coordenadas son aleatorias: la dirección es ficticia y NO está geocodificada.
    """
    rng = np.random.default_rng(seed)
    rng_txt = np.random.default_rng(seed + 7919)  # aparte, para no alterar las coordenadas
    rng_tel = np.random.default_rng(seed + 104729)  # aparte, para no alterar nombres ni direcciones
    pesos = np.array([l[3] for l in LOCALIDADES], dtype=float)
    pesos /= pesos.sum()
    filas, usados = [], set()
    intentos = 0
    while len(filas) < n and intentos < n * 50:
        intentos += 1
        localidad, lat, lon, _, sd = LOCALIDADES[rng.choice(len(LOCALIDADES), p=pesos)]
        la = lat + rng.normal(0, sd)
        lo = lon + rng.normal(0, sd)
        if haversine_km(DEPOSITO["lat"], DEPOSITO["lon"], la, lo) > RADIO_KM:
            continue
        if en_agua(la, lo):
            continue
        demanda = int(rng.integers(demanda_min, demanda_max + 1))
        descarga = int(rng.integers(descarga_min, descarga_max + 1))
        direccion = _direccion(rng_txt, localidad)
        cp = CP.get(localidad, "")
        filas.append({
            "id_cliente": f"C{len(filas) + 1:03d}",
            "cliente": _nombre_cliente(rng_txt, usados),
            "direccion": direccion,
            "localidad": localidad,
            "cp": cp,
            "direccion_completa": f"{direccion}, {localidad} ({cp})",
            "telefono": _telefono(rng_tel, localidad),
            "lat": round(la, 5),
            "lon": round(lo, 5),
            "paquetes": int(rng_txt.integers(1, 5)),
            "demanda_kg": demanda,
            "descarga_min": descarga,
        })
    return pd.DataFrame(filas)


def generar_paquetes(clientes, fecha=None, seed=0):
    """Un registro por paquete, con código único. La suma de pesos por cliente = demanda_kg.

    Código: PQ-AAMMDD-NNN-PP  (fecha de reparto, N° de cliente, N° de paquete del cliente).
    """
    fecha = fecha or date.today()
    filas = []
    for _, c in clientes.iterrows():
        k, total = int(c["paquetes"]), int(c["demanda_kg"])
        num = int(c["id_cliente"][1:])
        rng = np.random.default_rng([int(seed), num])
        w = 0.5 / k + 0.5 * rng.dirichlet(np.ones(k))
        pesos = np.floor(total * w).astype(int)
        pesos[0] += total - pesos.sum()
        for j, kg in enumerate(pesos, start=1):
            filas.append({
                "codigo": f"PQ-{fecha:%y%m%d}-{num:03d}-{j:02d}",
                "id_cliente": c["id_cliente"],
                "cliente": c["cliente"],
                "paquete_n": j,
                "peso_kg": int(kg),
            })
    return pd.DataFrame(filas)


def _patentes(n):
    """Patentes inventadas con formato argentino actual (AB 123 CD), estables por camión."""
    rng = np.random.default_rng(20260)
    out = []
    while len(out) < n:
        p = ("A" + _pick(rng, "ABCDEFGH") + f" {int(rng.integers(0, 1000)):03d} "
             + _pick(rng, LETRAS_PATENTE) + _pick(rng, LETRAS_PATENTE))
        if p not in out:
            out.append(p)
    return out


def flota_default(n_camiones=10):
    """Flota mixta: 30% chicos, 40% medianos, 30% grandes, con patente inventada."""
    n_ch = round(n_camiones * 0.3)
    n_gr = round(n_camiones * 0.3)
    n_md = n_camiones - n_ch - n_gr
    tipos = [("Chico", 1500)] * n_ch + [("Mediano", 3000)] * n_md + [("Grande", 5000)] * n_gr
    pat = _patentes(n_camiones)
    return pd.DataFrame([
        {"camion": f"Camión {i + 1:02d}", "patente": pat[i], "tipo": t, "capacidad_kg": c}
        for i, (t, c) in enumerate(tipos)
    ])
