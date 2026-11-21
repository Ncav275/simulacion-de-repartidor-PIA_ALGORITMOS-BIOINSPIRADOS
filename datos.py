"""
datos.py - Geocodificación y matrices de distancia con servicios gratuitos (OpenStreetMap).

- Geocodificación: Nominatim (1 petición/seg, User-Agent propio, caché en disco).
- Matriz por calles reales: OSRM (servidor demo, solo para pruebas ligeras) o, si falla, Haversine.
"""
import json
import os
import time

import numpy as np
import requests

USER_AGENT = "proyecto-paqueteria-escolar/1.0 (cambia-esto@correo.com)"  # <- pon tu correo
CACHE_ARCHIVO = "cache_geocodificacion.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
OVERPASS = "https://overpass-api.de/api/interpreter"
OSRM = "https://router.project-osrm.org/table/v1/driving/"


# ---------------------------------------------------------------- geocodificación
def _cargar_cache():
    if os.path.exists(CACHE_ARCHIVO):
        with open(CACHE_ARCHIVO, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _guardar_cache(cache):
    with open(CACHE_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def geocodificar(direccion, pais="mx"):
    """Devuelve (lat, lon) o None si no se encuentra. Usa caché para no repetir consultas."""
    cache = _cargar_cache()
    if direccion in cache:
        return tuple(cache[direccion]) if cache[direccion] else None

    r = requests.get(
        NOMINATIM,
        params={"q": direccion, "format": "json", "limit": 1, "countrycodes": pais},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    r.raise_for_status()
    resultado = r.json()
    time.sleep(1.1)  # política de uso de Nominatim: máx. 1 petición por segundo

    cache[direccion] = [float(resultado[0]["lat"]), float(resultado[0]["lon"])] if resultado else None
    _guardar_cache(cache)
    return tuple(cache[direccion]) if cache[direccion] else None


def geocodificar_lista(direcciones):
    """Geocodifica varias direcciones. Devuelve (coordenadas, fallidas)."""
    coords, fallidas = [], []
    for d in direcciones:
        c = geocodificar(d)
        if c is None:
            fallidas.append(d)
        else:
            coords.append(c)
    return coords, fallidas


def _direccion_corta(a):
    """Arma 'Calle 123, Colonia, Municipio' a partir del campo address de Nominatim."""
    calle = a.get("road") or a.get("pedestrian") or a.get("footway") or a.get("residential")
    num = a.get("house_number")
    col = a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or a.get("city_district")
    muni = a.get("city") or a.get("town") or a.get("municipality") or a.get("village") or a.get("county")
    partes = []
    if calle:
        partes.append(f"{calle} {num}" if num else calle)
    if col:
        partes.append(col)
    if muni and muni != col:
        partes.append(muni)
    return ", ".join(partes) if partes else None


def direccion_inversa(lat, lon):
    """(lat, lon) -> dirección corta tipo 'Calle 123, Colonia, Municipio'. Con caché; None si falla."""
    clave = f"rev2:{lat:.5f},{lon:.5f}"
    cache = _cargar_cache()
    if clave in cache:
        return cache[clave]
    try:
        r = requests.get(
            NOMINATIM_REVERSE,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18,
                    "addressdetails": 1, "accept-language": "es"},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        j = r.json()
    except Exception:
        return None
    time.sleep(1.1)  # 1 petición por segundo
    texto = _direccion_corta(j.get("address", {})) or j.get("display_name")
    cache[clave] = texto
    _guardar_cache(cache)
    return texto


PHOTON = "https://photon.komoot.io/api/"
_SUG_CACHE = {}


def sugerencias_direccion(q, limite=6):
    """
    Direcciones parecidas a lo que se va escribiendo (para el autocompletado de la página).
    Usa Photon (gratis, hecho para buscar mientras se escribe; datos de OpenStreetMap).
    Solo devuelve lugares del área metropolitana de Monterrey. Devuelve [] si falla.
    """
    q = (q or "").strip()
    if len(q) < 3:
        return []
    if q.lower() in _SUG_CACHE:
        return _SUG_CACHE[q.lower()]
    try:
        r = requests.get(
            PHOTON,
            params={"q": q, "limit": limite, "lat": 25.68, "lon": -100.31,
                    "bbox": "-100.7,25.4,-99.9,26.0"},
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        r.raise_for_status()
        feats = r.json().get("features", [])
    except Exception as e:
        print(f"[aviso] Sugerencias no disponibles ({e})")
        return []
    salida, vistos = [], set()
    for f in feats:
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"][:2]
        if not (25.4 <= lat <= 26.0 and -100.7 <= lon <= -99.9):
            continue
        calle = p.get("street")
        num = p.get("housenumber")
        if calle:
            l1 = f"{calle} {num}" if num else calle
            if p.get("name") and p["name"] != calle:
                l1 = f"{p['name']} - {l1}"
        else:
            l1 = p.get("name") or ""
        muni = p.get("city") or p.get("county") or p.get("locality") or ""
        l2 = ", ".join(x for x in [p.get("district") or p.get("locality"), muni, p.get("state")] if x)
        if not l1:
            continue
        etiqueta = f"{l1}, {l2}" if l2 else l1
        if etiqueta in vistos:
            continue
        vistos.add(etiqueta)
        salida.append({"label": etiqueta, "linea1": l1, "linea2": l2,
                       "municipio": muni or "-", "lat": float(lat), "lon": float(lon)})
    if len(_SUG_CACHE) > 300:
        _SUG_CACHE.clear()
    _SUG_CACHE[q.lower()] = salida
    return salida


def casas_en_zona(lat, lon, radio_m=3000, maximo=400):
    """
    Lista de (lat, lon) de edificios residenciales (casas) de OpenStreetMap alrededor de un punto.
    Usa Overpass API (gratis) y guarda el resultado en caché. Devuelve [] si falla.
    """
    clave = f"casas:{lat:.4f},{lon:.4f},{radio_m}"
    cache = _cargar_cache()
    if clave in cache:
        return [tuple(c) for c in cache[clave]]
    consulta = (
        "[out:json][timeout:30];"
        f'way["building"~"^(house|residential|detached|semidetached_house|terrace)$"]'
        f"(around:{radio_m},{lat},{lon});"
        f"out center {maximo};"
    )
    try:
        r = requests.post(OVERPASS, data={"data": consulta}, headers={"User-Agent": USER_AGENT}, timeout=60)
        r.raise_for_status()
        elementos = r.json().get("elements", [])
    except Exception as e:
        print(f"[aviso] Overpass falló ({e})")
        return []
    casas = [(el["center"]["lat"], el["center"]["lon"]) for el in elementos if "center" in el]
    cache[clave] = casas
    _guardar_cache(cache)
    time.sleep(1.0)
    return casas


# ---------------------------------------------------------------- matrices
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def matriz_haversine(coords, factor_calle=1.3, vel_kmh=30.0):
    """Respaldo sin internet. factor_calle aproxima que las calles no son línea recta."""
    n = len(coords)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                D[i, j] = haversine_km(*coords[i], *coords[j]) * factor_calle
    T = D / vel_kmh * 60.0  # minutos
    return D, T


def matriz_osrm(coords):
    """
    Matriz real por calles. Devuelve (D en km, T en minutos). Puede ser NO simétrica.
    El servidor demo limita el tamaño de la consulta; para más puntos, usa OSRM propio o ORS.
    """
    lista = ";".join(f"{lon},{lat}" for lat, lon in coords)
    r = requests.get(
        OSRM + lista,
        params={"annotations": "distance,duration"},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    datos = r.json()
    D = np.array(datos["distances"], dtype=float) / 1000.0
    T = np.array(datos["durations"], dtype=float) / 60.0
    return D, T


def geometria_ruta(coords):
    """Trazo por calles (lista de [lat, lon]) que pasa por los puntos en orden. None si falla."""
    try:
        lista = ";".join(f"{lon},{lat}" for lat, lon in coords)
        r = requests.get(
            OSRM.replace("/table/", "/route/") + lista,
            params={"overview": "full", "geometries": "geojson"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        linea = r.json()["routes"][0]["geometry"]["coordinates"]
        return [[lat, lon] for lon, lat in linea]
    except Exception as e:
        print(f"[aviso] No se pudo obtener el trazo por calles ({e}); se dibujan líneas rectas.")
        return None


def obtener_matrices(coords):
    """Intenta OSRM; si falla, cae a Haversine y avisa."""
    try:
        return matriz_osrm(coords), "osrm"
    except Exception as e:  # sin internet, límite, etc.
        print(f"[aviso] OSRM falló ({e}); usando Haversine.")
        return matriz_haversine(coords), "haversine"
