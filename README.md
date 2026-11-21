# Demo: ruteo de reparto desde el Parque Industrial Pilar

## Instalación
```
pip install -r requirements.txt
streamlit run app.py
```

## Archivos
- `datos.py`: depósito, flota (con patente), clientes (nombre o razón social, dirección, CP) y paquetes con código.
- `distancias.py`: matrices de km/min (línea recta × factor, velocidad media). Reemplazable por OSRM.
- `optimizador.py`: VRP con OR-Tools (capacidad por camión, jornada 10-18, descarga 10-30 min, pedidos sin asignar con penalidad).
- `seguimiento.py`: eventos y estados de cada paquete, y la línea de tiempo (HTML) que ve el cliente.
- `pdf_rutas.py`: PDF con resumen del día y una hoja por camión/chofer (con columna de firma).
- `app.py`: interfaz Streamlit (mapa, indicadores, hoja de ruta, Excel, PDF).

## Modelo
- Todos los camiones salen a las 10:00 y deben volver antes de las 18:00.
- Costo = km + costo fijo por camión usado (favorece usar menos camiones).
- Si un pedido no entra por capacidad u horas, queda sin asignar (penalidad 300 km).

## Opciones nuevas
- **Equilibrar jornadas**: penaliza la jornada más larga para repartir el trabajo entre más camiones.
- **OSRM**: tildar "Rutas reales por calle". El servidor público (`router.project-osrm.org`) es solo
  para pruebas (límite de uso y de ~100 puntos por consulta). Para vender el sistema, levantar un
  OSRM propio con el mapa de Argentina (Docker) y poner su URL en la app. Si OSRM falla, la app
  vuelve sola al modelo simple y avisa.

## Datos ficticios
- Clientes: personas (nombre y apellido) y razones sociales, con calle, número y CP aproximado por localidad.
- Las direcciones **no están geocodificadas**: las coordenadas del mapa son aleatorias y no corresponden a la calle
  indicada. En producción, geocodificar la dirección (Nominatim, OpenCage, Google) para obtener lat/lon.
- Patentes inventadas con formato argentino actual (AB 123 CD).
- Paquetes: código `PQ-AAMMDD-NNN-PP` (fecha de reparto, N° de cliente, N° de paquete). El Excel trae una hoja
  "Paquetes" con camión, orden de parada y hora estimada de cada código, y la app permite buscarlos.

## Seguimiento de paquetes (simulado)
Estados: Pedido recibido -> En depósito -> En camino -> Cerca de destino -> Entregado / No entregado.
- Los horarios salen de la hoja de ruta del optimizador (salida del depósito, llegada y fin de descarga).
- "Cerca de destino" se dispara 15 min antes de la llegada estimada y simula un SMS al teléfono del cliente.
- El camión se carga en orden inverso a las paradas.
- Un porcentaje configurable de clientes está ausente: sus paquetes quedan "No entregado" (se reprograman).
- Los paquetes sin ruta quedan "En depósito" y se reprograman.
- En la app se mueve la "Hora simulada" y se elige un paquete para ver su línea de tiempo. El Excel trae la hoja "Seguimiento".
- En producción, cada evento lo registraría el chofer desde el celular (o el sistema de la flota).
