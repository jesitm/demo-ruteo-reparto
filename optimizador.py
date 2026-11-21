"""Optimización de rutas con Google OR-Tools (VRP con capacidad y jornada)."""
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from datos import DEPOSITO
from distancias import matrices


def _hhmm(minutos, inicio_h):
    t = int(round(minutos)) + inicio_h * 60
    return f"{t // 60:02d}:{t % 60:02d}"


def optimizar(clientes, flota, inicio_h=10, fin_h=18, factor_ruta=1.3,
              velocidad_kmh=50.0, tiempo_limite_s=20, penalidad_km=300,
              costo_fijo_camion_km=15, balanceo=1000, osrm_url=None, paquetes=None):
    """Devuelve (rutas_df, paradas_df, sin_asignar_df).

    - Todos los camiones salen del depósito a `inicio_h` y deben volver antes de `fin_h`.
    - Tiempo en nodo = descarga del cliente. Pedidos que no entran quedan sin asignar
      con penalidad `penalidad_km` (equivalente en km).
    - balanceo: peso (en metros por minuto) de la jornada más larga; >0 reparte mejor el
      trabajo entre camiones (usa más camiones). 0 = solo minimizar km.
    - osrm_url: si se indica, usa distancias/tiempos reales por calle.
    - paquetes: DataFrame de generar_paquetes(); si se pasa, cada parada lista los
      códigos de los paquetes a entregar.
    """
    horizonte = int((fin_h - inicio_h) * 60)
    coords = [(DEPOSITO["lat"], DEPOSITO["lon"])] + list(zip(clientes["lat"], clientes["lon"]))
    dist_km, t_min, fuente = matrices(coords, factor_ruta, velocidad_kmh, osrm_url)

    dist_m = (dist_km * 1000).round().astype(int)            # costo en metros
    viaje = t_min.round().astype(int)                         # minutos
    servicio = [0] + [int(x) for x in clientes["descarga_min"]]
    demanda = [0] + [int(x) for x in clientes["demanda_kg"]]
    capacidades = [int(x) for x in flota["capacidad_kg"]]

    codigos = {}
    if paquetes is not None:
        for idc, g in paquetes.groupby("id_cliente"):
            codigos[idc] = " · ".join(g.sort_values("paquete_n")["codigo"])

    n_nodos = len(coords)
    n_veh = len(flota)
    manager = pywrapcp.RoutingIndexManager(n_nodos, n_veh, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Costo: distancia
    def costo_cb(i, j):
        return int(dist_m[manager.IndexToNode(i)][manager.IndexToNode(j)])
    costo_idx = routing.RegisterTransitCallback(costo_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(costo_idx)
    routing.SetFixedCostOfAllVehicles(int(costo_fijo_camion_km * 1000))

    # Capacidad
    def dem_cb(i):
        return demanda[manager.IndexToNode(i)]
    dem_idx = routing.RegisterUnaryTransitCallback(dem_cb)
    routing.AddDimensionWithVehicleCapacity(dem_idx, 0, capacidades, True, "Carga")

    # Tiempo: viaje + descarga en el nodo de origen del arco
    def tiempo_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(viaje[a][b] + servicio[a])
    t_idx = routing.RegisterTransitCallback(tiempo_cb)
    routing.AddDimension(t_idx, 0, horizonte, True, "Tiempo")
    time_dim = routing.GetDimensionOrDie("Tiempo")
    if balanceo > 0:
        time_dim.SetGlobalSpanCostCoefficient(int(balanceo))

    # Pedidos opcionales (se pueden dejar sin asignar con penalidad)
    for nodo in range(1, n_nodos):
        routing.AddDisjunction([manager.NodeToIndex(nodo)], int(penalidad_km * 1000))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = int(tiempo_limite_s)

    sol = routing.SolveWithParameters(params)
    if sol is None:
        raise RuntimeError("No se encontró solución. Probá con más camiones o menos clientes.")

    paradas, rutas, atendidos = [], [], set()
    for v in range(n_veh):
        idx = routing.Start(v)
        orden, km, carga = 0, 0.0, 0
        salida_dep = sol.Min(time_dim.CumulVar(idx))
        prev_nodo = 0
        while True:
            idx = sol.Value(routing.NextVar(idx))
            nodo = manager.IndexToNode(idx)
            if routing.IsEnd(idx):
                km += dist_km[prev_nodo][0]
                regreso = sol.Min(time_dim.CumulVar(idx))
                break
            orden += 1
            km += dist_km[prev_nodo][nodo]
            llegada = sol.Min(time_dim.CumulVar(idx))
            carga += demanda[nodo]
            c = clientes.iloc[nodo - 1]
            atendidos.add(nodo)
            paradas.append({
                "camion": flota.iloc[v]["camion"], "patente": flota.iloc[v]["patente"],
                "orden": orden, "id_cliente": c["id_cliente"], "cliente": c["cliente"],
                "direccion": c["direccion_completa"], "telefono": c["telefono"],
                "localidad": c["localidad"],
                "lat": c["lat"], "lon": c["lon"],
                "llegada": _hhmm(llegada, inicio_h),
                "salida": _hhmm(llegada + servicio[nodo], inicio_h),
                "descarga_min": servicio[nodo], "paquetes": int(c["paquetes"]),
                "demanda_kg": demanda[nodo], "codigos": codigos.get(c["id_cliente"], ""),
            })
            prev_nodo = nodo
        if orden > 0:
            cap = capacidades[v]
            rutas.append({
                "camion": flota.iloc[v]["camion"], "patente": flota.iloc[v]["patente"],
                "tipo": flota.iloc[v]["tipo"], "capacidad_kg": cap, "paradas": orden, "carga_kg": carga,
                "uso_capacidad_%": round(100 * carga / cap, 1),
                "km": round(km, 1),
                "salida_deposito": _hhmm(salida_dep, inicio_h),
                "regreso_deposito": _hhmm(regreso, inicio_h),
                "minutos_jornada": int(regreso - salida_dep),
            })

    sin_asignar = clientes.iloc[[n - 1 for n in range(1, n_nodos) if n not in atendidos]].copy()
    rutas_df = pd.DataFrame(rutas)
    rutas_df.attrs["fuente_distancias"] = fuente
    return rutas_df, pd.DataFrame(paradas), sin_asignar


def asignar_paquetes(paquetes, paradas, clientes):
    """Cada paquete con su camión, orden de parada y hora estimada (o SIN ASIGNAR)."""
    ruta = paradas[["id_cliente", "camion", "patente", "orden", "llegada"]]
    dirs = clientes[["id_cliente", "direccion_completa", "telefono"]].rename(columns={"direccion_completa": "direccion"})
    df = paquetes.merge(dirs, on="id_cliente", how="left").merge(ruta, on="id_cliente", how="left")
    df["camion"] = df["camion"].fillna("SIN ASIGNAR")
    df["patente"] = df["patente"].fillna("")
    df["llegada"] = df["llegada"].fillna("")
    df["orden"] = df["orden"].apply(lambda x: "" if pd.isna(x) else int(x))
    cols = ["codigo", "camion", "patente", "orden", "llegada", "id_cliente", "cliente", "direccion", "telefono", "peso_kg"]
    return df[cols].sort_values(["camion", "codigo"]).reset_index(drop=True)
