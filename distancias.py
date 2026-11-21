"""Matrices de distancia (km) y tiempo (min) y geometría de rutas.

Modo simple (sin internet): línea recta * factor / velocidad media.
Modo OSRM: tiempos y distancias reales por calle (servidor propio o público de prueba).
Si OSRM falla, se vuelve automáticamente al modo simple.
"""
import json
import urllib.request
import numpy as np
from datos import haversine_km

OSRM_PUBLICO = "https://router.project-osrm.org"  # solo para pruebas; ver README


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "reparto-demo/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def matrices_simples(coords, factor_ruta=1.3, velocidad_kmh=50.0):
    n = len(coords)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i, j] = haversine_km(*coords[i], *coords[j]) * factor_ruta
    return dist, dist / velocidad_kmh * 60.0


def matrices_osrm(coords, base_url=OSRM_PUBLICO, factor_tiempo=1.2):
    """coords: [(lat, lon)]. Devuelve (km, min). factor_tiempo: los camiones son
    más lentos que los autos que usa OSRM por defecto."""
    pares = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
    url = f"{base_url.rstrip('/')}/table/v1/driving/{pares}?annotations=duration,distance"
    data = _get_json(url, timeout=60)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM: {data.get('code')} {data.get('message', '')}")
    dur = np.array(data["durations"], dtype=float)
    dis = np.array(data["distances"], dtype=float)
    if np.isnan(dur).any() or np.isnan(dis).any():
        raise RuntimeError("OSRM devolvió puntos sin ruta (¿cliente fuera de la red vial?)")
    return dis / 1000.0, dur / 60.0 * factor_tiempo


def matrices(coords, factor_ruta=1.3, velocidad_kmh=50.0, osrm_url=None, factor_tiempo=1.2):
    """Devuelve (km, min, fuente) con fuente 'osrm', 'simple' o 'simple (OSRM falló: ...)'."""
    if osrm_url:
        try:
            d, t = matrices_osrm(coords, osrm_url, factor_tiempo)
            return d, t, "osrm"
        except Exception as e:  # red caída, límite de puntos, etc.
            d, t = matrices_simples(coords, factor_ruta, velocidad_kmh)
            return d, t, f"simple (OSRM falló: {e})"
    d, t = matrices_simples(coords, factor_ruta, velocidad_kmh)
    return d, t, "simple"


def geometria_osrm(puntos, base_url=OSRM_PUBLICO):
    """Trazado real por calles que une `puntos` [(lat, lon)] en orden.
    Devuelve lista [(lat, lon)] o None si falla."""
    try:
        pares = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in puntos)
        url = (f"{base_url.rstrip('/')}/route/v1/driving/{pares}"
               "?overview=full&geometries=geojson")
        data = _get_json(url, timeout=60)
        if data.get("code") != "Ok":
            return None
        return [(lat, lon) for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
    except Exception:
        return None
