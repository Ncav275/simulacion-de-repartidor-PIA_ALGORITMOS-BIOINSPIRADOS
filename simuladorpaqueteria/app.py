"""
app.py - Página web del centro de distribución (simulación de un repartidor de Mercado Libre).

La página recibe órdenes (dirección de entrega), el programa asigna al repartidor las que caben
en su jornada laboral y optimiza la ruta con ACO, GA o PSO para recorrer la menor distancia.

Uso:
    python app.py                 # con internet: Nominatim + OSRM
    python app.py --offline       # sin internet: solo órdenes aleatorias y distancias Haversine
Luego abre http://127.0.0.1:5000
"""
import argparse
import itertools
import random
import threading

import numpy as np
from flask import Flask, Response, jsonify, request

import algoritmos as alg
import datos
import experimento as exp
import ordenes as ords
from pagina import HTML

app = Flask(__name__)
LOCK = threading.Lock()
ESTADO = {"tarjetas": [], "centro": None, "offline": False, "contador": 0}


def _centro():
    if ESTADO["centro"] is None:
        if ESTADO["offline"]:
            ESTADO["centro"] = exp.CENTRO_COORDS_SIMULADO
        else:
            c = datos.geocodificar(exp.CENTRO)
            if c is None:
                raise RuntimeError(f"No se pudo geocodificar el centro: {exp.CENTRO}")
            ESTADO["centro"] = c
    return ESTADO["centro"]


def _completar(texto):
    bajo = texto.lower()
    if "nuevo le" not in bajo and "n.l" not in bajo:
        texto += ", Nuevo León, México"
    return texto


def _nueva_tarjeta(base):
    ESTADO["contador"] += 1
    base["id"] = f"ML-{ESTADO['contador']:04d}"
    base["llegada"] = ESTADO["contador"]
    base["estado"] = "pendiente"
    return base


@app.get("/")
def inicio():
    return Response(HTML, mimetype="text/html")


@app.get("/api/estado")
def estado():
    try:
        c = _centro()
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(
        centro={"lat": c[0], "lon": c[1], "direccion": exp.CENTRO},
        tarjetas=ESTADO["tarjetas"],
        offline=ESTADO["offline"],
        jornada_h=exp.JORNADA_MIN / 60,
        servicio_min=exp.SERVICIO_MIN,
    )


@app.get("/api/sugerencias")
def sugerencias():
    if ESTADO["offline"]:
        return jsonify(sugerencias=[])
    q = request.args.get("q", "")
    return jsonify(sugerencias=datos.sugerencias_direccion(q))


def _en_zona(lat, lon):
    return 25.4 <= lat <= 26.0 and -100.7 <= lon <= -99.9


@app.post("/api/ordenes")
def agregar_orden():
    cuerpo = request.get_json(silent=True) or {}
    texto = (cuerpo.get("direccion") or "").strip()
    if len(texto) < 8:
        return jsonify(error="Escribe una dirección completa (calle, número, colonia y municipio)."), 400

    lat, lon = cuerpo.get("lat"), cuerpo.get("lon")
    with LOCK:
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            # La persona eligió una sugerencia: ya trae coordenadas
            c = (float(lat), float(lon))
            municipio = cuerpo.get("municipio") or "Ingresada manualmente"
        else:
            if ESTADO["offline"]:
                return jsonify(error="Modo sin internet: usa 'Generar'."), 400
            try:
                c = datos.geocodificar(_completar(texto))
            except Exception as e:
                return jsonify(error=f"Error al geocodificar: {e}"), 502
            if c is None:
                return jsonify(error="No se encontró esa dirección. Elige una de las sugerencias."), 404
            municipio = "Ingresada manualmente"
        if not _en_zona(c[0], c[1]):
            return jsonify(error="La dirección quedó fuera del área metropolitana de Monterrey."), 400
        t = _nueva_tarjeta({"municipio": municipio, "tipo": "manual", "direccion": texto,
                            "lat": float(c[0]), "lon": float(c[1])})
        ESTADO["tarjetas"].append(t)
    return jsonify(t)


@app.post("/api/ordenes/aleatorias")
def aleatorias():
    cuerpo = request.get_json(silent=True) or {}
    n = max(1, min(int(cuerpo.get("n", 20)), 100))
    semilla = cuerpo.get("semilla")
    semilla = int(semilla) if semilla not in (None, "") else random.randrange(10**6)
    real = not ESTADO["offline"]
    with LOCK:
        try:
            nuevas = ords.generar_ordenes(n, semilla=semilla, reverse=real, casas=real)
        except Exception as e:
            return jsonify(error=f"No se pudieron generar las órdenes: {e}"), 502
        for t in nuevas:
            ESTADO["tarjetas"].append(_nueva_tarjeta(t))
    return jsonify(agregadas=len(nuevas), semilla=semilla)


@app.post("/api/limpiar")
def limpiar():
    with LOCK:
        ESTADO["tarjetas"].clear()
        ESTADO["contador"] = 0
    return jsonify(ok=True)


def _mejor_ruta_pocas(D):
    """Con 3 o menos puntos se prueban todas las permutaciones."""
    n = len(D)
    mejor = min(itertools.permutations(range(1, n)),
                key=lambda p: alg.longitud_ruta([0] + list(p), D))
    ruta = [0] + list(mejor)
    return ruta, alg.longitud_ruta(ruta, D)


@app.post("/api/optimizar")
def optimizar():
    algoritmo = ((request.get_json(silent=True) or {}).get("algoritmo") or "TODOS").upper()
    tarjetas = ESTADO["tarjetas"]
    if not tarjetas:
        return jsonify(error="Aún no hay órdenes."), 400

    with LOCK:
        try:
            centro = _centro()
            coords = [centro] + [(t["lat"], t["lon"]) for t in tarjetas]
            if ESTADO["offline"]:
                D, T = datos.matriz_haversine(coords)
                fuente = "Haversine (aproximado)"
            else:
                (D, T), fuente = datos.obtener_matrices(coords)
        except Exception as e:
            return jsonify(error=str(e)), 502

        elegidas, sobrantes = exp.asignar_por_jornada(T)
        elegidas = sorted(elegidas)  # centro primero; resto en orden de llegada
        if len(elegidas) < 2:
            return jsonify(error="Ninguna orden cabe en la jornada."), 400
        Ds, Ts = D[np.ix_(elegidas, elegidas)], T[np.ix_(elegidas, elegidas)]
        n = len(Ds)

        km_llegada = alg.longitud_ruta(list(range(n)), Ds)
        comparativa, mejor = [], (np.inf, None, None)

        if n <= 3:
            ruta, costo = _mejor_ruta_pocas(Ds)
            comparativa.append({"algoritmo": "Pocas órdenes (todas las rutas)", "km": round(costo, 2)})
            mejor = (costo, "Pocas órdenes", ruta)
        else:
            configs = {
                "ACO": lambda: alg.aco(Ds, hormigas=20, iteraciones=100, semilla=0),
                "GA": lambda: alg.ga(Ds, poblacion=50, generaciones=40, semilla=0),
                "PSO": lambda: alg.pso(Ds, particulas=20, iteraciones=100, semilla=0),
            }
            if algoritmo not in ("ACO", "GA", "PSO"):
                algoritmo = "TODOS"
            elegir = list(configs) if algoritmo == "TODOS" else [algoritmo]
            for nombre in elegir:
                ruta, costo, _ = configs[nombre]()
                comparativa.append({"algoritmo": nombre, "km": round(float(costo), 2)})
                if costo < mejor[0]:
                    mejor = (float(costo), nombre, ruta)

        costo, nombre, ruta = mejor
        paradas = [{"orden": 0, "id": "CENTRO", "direccion": exp.CENTRO,
                    "lat": centro[0], "lon": centro[1]}]
        for k, i in enumerate(ruta[1:], start=1):
            t = tarjetas[elegidas[i] - 1]
            paradas.append({"orden": k, "id": t["id"], "direccion": t["direccion"],
                            "lat": t["lat"], "lon": t["lon"]})
        puntos = [(p["lat"], p["lon"]) for p in paradas] + [(centro[0], centro[1])]
        geometria = None if ESTADO["offline"] else datos.geometria_ruta(puntos)

        for t in tarjetas:
            t["estado"] = "pendiente"
        for p in paradas[1:]:
            for t in tarjetas:
                if t["id"] == p["id"]:
                    t["estado"] = f"asignada (parada {p['orden']})"

    return jsonify(
        paradas=paradas,
        geometria=geometria,
        puntos_rectos=[[a, b] for a, b in puntos],
        metricas={
            "algoritmo": nombre,
            "fuente_distancias": fuente,
            "km": round(float(costo), 2),
            "km_llegada": round(float(km_llegada), 2),
            "ahorro_km": round(float(km_llegada - costo), 2),
            "ahorro_pct": round(float(100 * (km_llegada - costo) / km_llegada), 1) if km_llegada else 0,
            "horas": round(exp.tiempo_ruta(ruta, Ts) / 60, 2),
            "jornada_h": exp.JORNADA_MIN / 60,
            "entregados": n - 1,
            "pendientes": [tarjetas[i - 1]["id"] for i in sobrantes],
        },
        comparativa=comparativa,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="sin internet: órdenes aleatorias y Haversine")
    ap.add_argument("--puerto", type=int, default=5000)
    a = ap.parse_args()
    ESTADO["offline"] = a.offline
    app.run(host="127.0.0.1", port=a.puerto, debug=False)
