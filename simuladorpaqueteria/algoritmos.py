"""
algoritmos.py - ACO, GA y PSO para la ruta de un repartidor.

Convenciones:
- D es la matriz de distancias (n x n), puede ser asimétrica. El índice 0 es el centro de distribución.
- Una ruta es una permutación de [0..n-1] que empieza en 0. El regreso al depósito se suma en el costo.
- Todos los algoritmos devuelven (mejor_ruta, mejor_costo, historial) donde historial[i] es el
  mejor costo global después de la evaluación (o bloque de evaluaciones) i.
- Presupuesto justo: ACO = hormigas x iteraciones, GA = poblacion x generaciones,
  PSO = particulas x iteraciones. Usa valores que den el mismo total de evaluaciones.
"""
import numpy as np


def longitud_ruta(ruta, D):
    n = len(ruta)
    return sum(D[ruta[i], ruta[(i + 1) % n]] for i in range(n))


# ====================================================================== ACO
def aco(D, hormigas=20, iteraciones=100, alpha=1.0, beta=2.0, rho=0.3, q=1.0, semilla=0):
    rng = np.random.default_rng(semilla)
    N = len(D)
    ETA = np.zeros_like(D)
    ETA[D > 0] = 1.0 / D[D > 0]
    tau = np.ones((N, N))

    mejor_ruta, mejor_costo = None, np.inf
    historial = []

    for _ in range(iteraciones):
        rutas, costos = [], []
        for _h in range(hormigas):
            ruta = [0]
            visitadas = {0}
            while len(ruta) < N:
                actual = ruta[-1]
                cand = [j for j in range(N) if j not in visitadas]
                peso = np.array([(tau[actual, j] ** alpha) * (ETA[actual, j] ** beta) for j in cand])
                if peso.sum() == 0:
                    prob = np.ones(len(cand)) / len(cand)
                else:
                    prob = peso / peso.sum()
                sig = rng.choice(cand, p=prob)
                ruta.append(int(sig))
                visitadas.add(int(sig))
            c = longitud_ruta(ruta, D)
            rutas.append(ruta)
            costos.append(c)
            if c < mejor_costo:
                mejor_costo, mejor_ruta = c, ruta[:]

        tau *= (1 - rho)  # evaporación
        for ruta, c in zip(rutas, costos):
            for i in range(N):
                a, b = ruta[i], ruta[(i + 1) % N]
                tau[a, b] += q / c  # solo a->b: la matriz real puede ser asimétrica
        historial.append(mejor_costo)

    return mejor_ruta, mejor_costo, historial


# ====================================================================== GA
def _cruza_ox(p1, p2, rng):
    """Order crossover sobre las posiciones 1..n-1 (el depósito 0 queda fijo)."""
    n = len(p1) - 1
    a, b = sorted(rng.choice(n, size=2, replace=False))
    g1, g2 = p1[1:], p2[1:]
    hijo = [None] * n
    hijo[a:b + 1] = g1[a:b + 1]
    usados = set(hijo[a:b + 1])
    resto = [g for g in g2 if g not in usados]
    k = 0
    for i in range(n):
        if hijo[i] is None:
            hijo[i] = resto[k]
            k += 1
    return [0] + hijo


def ga(D, poblacion=50, generaciones=40, p_cruza=0.9, p_mut=0.2, elite=2, torneo=3, semilla=0):
    rng = np.random.default_rng(semilla)
    N = len(D)
    base = list(range(1, N))

    def nueva():
        perm = base[:]
        rng.shuffle(perm)
        return [0] + perm

    pob = [nueva() for _ in range(poblacion)]
    costos = [longitud_ruta(r, D) for r in pob]
    i0 = int(np.argmin(costos))
    mejor_ruta, mejor_costo = pob[i0][:], costos[i0]
    historial = [mejor_costo]

    def seleccion():
        idx = rng.choice(poblacion, size=torneo, replace=False)
        return pob[idx[np.argmin([costos[i] for i in idx])]]

    for _ in range(generaciones - 1):
        orden = np.argsort(costos)
        nueva_pob = [pob[i][:] for i in orden[:elite]]
        while len(nueva_pob) < poblacion:
            p1, p2 = seleccion(), seleccion()
            hijo = _cruza_ox(p1, p2, rng) if rng.random() < p_cruza else p1[:]
            if rng.random() < p_mut and N > 2:  # mutación por intercambio
                i, j = rng.choice(np.arange(1, N), size=2, replace=False)
                hijo[i], hijo[j] = hijo[j], hijo[i]
            nueva_pob.append(hijo)
        pob = nueva_pob
        costos = [longitud_ruta(r, D) for r in pob]
        i0 = int(np.argmin(costos))
        if costos[i0] < mejor_costo:
            mejor_costo, mejor_ruta = costos[i0], pob[i0][:]
        historial.append(mejor_costo)

    return mejor_ruta, mejor_costo, historial


# ====================================================================== PSO
def pso(D, particulas=20, iteraciones=100, w=0.7, c1=1.5, c2=1.5, semilla=0):
    """PSO con random keys: cada partícula es un vector continuo; argsort da el orden de visita."""
    rng = np.random.default_rng(semilla)
    N = len(D)
    dim = N - 1  # el depósito no se codifica

    def decodificar(x):
        return [0] + [int(i) + 1 for i in np.argsort(x)]

    pos = rng.random((particulas, dim))
    vel = rng.uniform(-0.1, 0.1, (particulas, dim))
    costos = np.array([longitud_ruta(decodificar(p), D) for p in pos])
    pbest, pbest_c = pos.copy(), costos.copy()
    g = int(np.argmin(costos))
    gbest, gbest_c = pos[g].copy(), costos[g]
    historial = [gbest_c]

    for _ in range(iteraciones - 1):
        r1, r2 = rng.random((particulas, dim)), rng.random((particulas, dim))
        vel = w * vel + c1 * r1 * (pbest - pos) + c2 * r2 * (gbest - pos)
        pos = pos + vel
        costos = np.array([longitud_ruta(decodificar(p), D) for p in pos])
        mejora = costos < pbest_c
        pbest[mejora], pbest_c[mejora] = pos[mejora], costos[mejora]
        g = int(np.argmin(pbest_c))
        if pbest_c[g] < gbest_c:
            gbest, gbest_c = pbest[g].copy(), pbest_c[g]
        historial.append(gbest_c)

    return decodificar(gbest), float(gbest_c), historial
