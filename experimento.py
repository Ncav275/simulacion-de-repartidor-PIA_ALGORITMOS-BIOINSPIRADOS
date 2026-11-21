"""
experimento.py - Asigna órdenes a un repartidor según su jornada y compara GA, PSO y ACO.

Órdenes aleatorias en el área metropolitana de Monterrey:
    python experimento.py                      # sin internet (Haversine)
    python experimento.py --real --n 30        # con Nominatim + OSRM
    python experimento.py --n 50 --semilla 7   # otra tanda de órdenes
"""
import argparse

import numpy as np

import algoritmos as alg

JORNADA_MIN = 8 * 60      # jornada laboral del repartidor
SERVICIO_MIN = 5          # minutos que tarda cada entrega
CORRIDAS = 10             # corridas con semillas distintas (como en tu práctica de ACO)


def asignar_por_jornada(T, jornada_min=JORNADA_MIN, servicio_min=SERVICIO_MIN):
    """
    Elige qué órdenes cubre UN repartidor: vecino más cercano por tiempo, agregando órdenes mientras
    (tiempo de manejo + servicio + regreso al depósito) no rebase la jornada.
    Devuelve la lista de índices (incluye 0 = depósito) de las órdenes asignadas.
    """
    n = len(T)
    elegidas = [0]
    pendientes = set(range(1, n))
    tiempo = 0.0
    while pendientes:
        actual = elegidas[-1]
        sig = min(pendientes, key=lambda j: T[actual, j])
        tiempo_nuevo = tiempo + T[actual, sig] + servicio_min
        if tiempo_nuevo + T[sig, 0] > jornada_min:
            break
        elegidas.append(sig)
        pendientes.remove(sig)
        tiempo = tiempo_nuevo
    return elegidas, sorted(pendientes)


def ruta_nn(D):
    """Línea base: vecino más cercano."""
    n = len(D)
    ruta, vis = [0], {0}
    while len(ruta) < n:
        a = ruta[-1]
        sig = min((j for j in range(n) if j not in vis), key=lambda j: D[a, j])
        ruta.append(sig)
        vis.add(sig)
    return ruta


def tiempo_ruta(ruta, T, servicio_min=SERVICIO_MIN):
    """Minutos de la jornada: manejo (con regreso al centro) + servicio en cada entrega."""
    n = len(ruta)
    manejo = sum(T[ruta[i], ruta[(i + 1) % n]] for i in range(n))
    return manejo + servicio_min * (n - 1)


def comparar(D, T, corridas=CORRIDAS):
    """
    Mismo presupuesto: 2000 evaluaciones por corrida para cada algoritmo.
    Línea base 'orden de llegada': el repartidor visita las direcciones tal como entraron los pedidos
    (D ya viene en ese orden). El ahorro se mide contra esa base.
    """
    n = len(D)
    km_llegada = alg.longitud_ruta(list(range(n)), D)
    km_nn = alg.longitud_ruta(ruta_nn(D), D)
    print(f"Orden de llegada (sin optimizar): {km_llegada:7.1f} km")
    print(f"Vecino más cercano:               {km_nn:7.1f} km")

    configs = {
        "ACO": lambda s: alg.aco(D, hormigas=20, iteraciones=100, semilla=s),
        "GA": lambda s: alg.ga(D, poblacion=50, generaciones=40, semilla=s),
        "PSO": lambda s: alg.pso(D, particulas=20, iteraciones=100, semilla=s),
    }
    resultados = {}
    mejor_global = (np.inf, None, None)
    for nombre, f in configs.items():
        corridas_res = [f(s) for s in range(corridas)]
        costos = [r[1] for r in corridas_res]
        resultados[nombre] = costos
        prom, mejor = np.mean(costos), min(costos)
        ahorro = km_llegada - mejor
        print(f"{nombre:4s} promedio: {prom:7.1f} km | mejor: {mejor:7.1f} | peor: {max(costos):7.1f} | "
              f"desv: {np.std(costos):5.1f} | ahorro vs llegada: {ahorro:6.1f} km ({100 * ahorro / km_llegada:4.1f}%)")
        i = int(np.argmin(costos))
        if costos[i] < mejor_global[0]:
            mejor_global = (costos[i], nombre, corridas_res[i][0])

    costo, nombre, ruta = mejor_global
    print(f"\n--- Resumen del repartidor (mejor ruta: {nombre}) ---")
    print(f"Paquetes entregados: {n - 1}")
    print(f"Distancia total:     {costo:.1f} km (ahorro de {km_llegada - costo:.1f} km vs orden de llegada)")
    print(f"Tiempo de jornada:   {tiempo_ruta(ruta, T) / 60:.1f} h de {JORNADA_MIN / 60:.0f} h")
    return resultados, ruta


# Cambia esto por la dirección del centro de distribución (ejemplo)
CENTRO = "Felipe Tena Ramírez 101, Praderas de Huinalá, Apodaca, Nuevo León, México"
CENTRO_COORDS_SIMULADO = (25.7817, -100.1883)


def main(real, n, semilla):
    import datos
    import ordenes as ords

    tarjetas = ords.generar_ordenes(n, semilla=semilla, reverse=real)
    ords.guardar(tarjetas)

    if real:
        centro = datos.geocodificar(CENTRO)
        if centro is None:
            raise SystemExit(f"No se pudo geocodificar el centro: {CENTRO}")
        coords = [centro] + ords.coords_de(tarjetas)
        (D, T), fuente = datos.obtener_matrices(coords)
    else:
        coords = [CENTRO_COORDS_SIMULADO] + ords.coords_de(tarjetas)
        D, T = datos.matriz_haversine(coords)
        fuente = "haversine (simulado)"

    print(f"{n} órdenes generadas (semilla {semilla}). Primeras tarjetas:")
    for t in tarjetas[:3]:
        ords.imprimir_tarjeta(t)

    print(f"\nMatriz: {fuente}, {len(D)} puntos (centro + {len(D) - 1} órdenes)")
    elegidas, sobrantes = asignar_por_jornada(T)
    print(f"Órdenes asignadas al repartidor: {len(elegidas) - 1} | pendientes: {len(sobrantes)}")

    elegidas = sorted(elegidas)  # el 0 (centro) primero; el resto en orden de llegada
    sub = np.ix_(elegidas, elegidas)
    Ds, Ts = D[sub], T[sub]
    print(f"--- Comparativa ({CORRIDAS} corridas, mismo presupuesto) ---")
    comparar(Ds, Ts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="usar Nominatim + OSRM (necesita internet)")
    ap.add_argument("--n", type=int, default=30, help="número de órdenes a generar")
    ap.add_argument("--semilla", type=int, default=0, help="semilla de las órdenes aleatorias")
    a = ap.parse_args()
    main(a.real, a.n, a.semilla)
