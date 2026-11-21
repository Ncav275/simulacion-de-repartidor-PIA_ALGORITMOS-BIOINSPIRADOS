"""
ordenes.py - Genera órdenes aleatorias de entrega en el área metropolitana de Monterrey
y crea una "tarjeta" por orden (una ficha con sus datos).

Cómo funciona:
1. Se eligen puntos al azar alrededor de los centros de varios municipios (con peso según tamaño).
2. Con reverse=True se obtiene una dirección real para cada punto (Nominatim inverso, con caché).
   Con reverse=False (sin internet) se usa un texto genérico.
3. Cada orden recibe un número de llegada: ese es el "orden de llegada" de los pedidos.
"""
import json

import numpy as np

# Centros aproximados (lat, lon), peso relativo y municipio
ZONAS = [
    ("Monterrey", 25.6866, -100.3161, 0.28),
    ("San Nicolás de los Garza", 25.7417, -100.3022, 0.17),
    ("Guadalupe", 25.6769, -100.2563, 0.17),
    ("Apodaca", 25.7817, -100.1883, 0.12),
    ("General Escobedo", 25.7970, -100.3167, 0.10),
    ("San Pedro Garza García", 25.6572, -100.4021, 0.08),
    ("Santa Catarina", 25.6733, -100.4586, 0.08),
]
DISPERSION_GRADOS = 0.02  # ~2 km de desviación alrededor de cada centro


def generar_ordenes(n, semilla=0, reverse=False, casas=False):
    """
    Devuelve una lista de n tarjetas (diccionarios). Misma semilla = mismas órdenes.
    casas=True: los puntos se eligen al azar entre casas reales de OpenStreetMap (Overpass),
                para que sean domicilios y no escuelas, comercios, parques, etc.
    casas=False: puntos aleatorios alrededor de los centros de municipio (sin internet).
    """
    rng = np.random.default_rng(semilla)
    pesos = np.array([z[3] for z in ZONAS])
    pesos = pesos / pesos.sum()

    disponibles = {}
    if casas:
        import datos
        for z in ZONAS:
            lista = datos.casas_en_zona(z[1], z[2])
            idx = rng.permutation(len(lista))  # orden aleatorio, sin repetir casas
            disponibles[z[0]] = [lista[i] for i in idx]
        if not any(disponibles.values()):
            print("[aviso] No se obtuvieron casas de OpenStreetMap; uso puntos aleatorios.")

    tarjetas = []
    for i in range(n):
        z = ZONAS[rng.choice(len(ZONAS), p=pesos)]
        if casas and disponibles.get(z[0]):
            lat, lon = disponibles[z[0]].pop()
            tipo = "casa"
        else:
            lat = float(z[1] + rng.normal(0, DISPERSION_GRADOS))
            lon = float(z[2] + rng.normal(0, DISPERSION_GRADOS))
            tipo = "punto aleatorio"
        direccion = f"Domicilio aprox. en {z[0]} ({lat:.4f}, {lon:.4f})"
        if reverse:
            import datos
            real = datos.direccion_inversa(lat, lon)
            if real:
                direccion = real
        tarjetas.append({
            "id": f"ML-{i + 1:04d}",
            "llegada": i + 1,  # orden en que entró el pedido
            "municipio": z[0],
            "tipo": tipo,
            "direccion": direccion,
            "lat": float(lat),
            "lon": float(lon),
            "estado": "pendiente",
        })
    return tarjetas


def imprimir_tarjeta(t):
    print("+" + "-" * 62 + "+")
    print(f"| Orden {t['id']}  (llegada #{t['llegada']})  Estado: {t['estado']}".ljust(63) + "|")
    print(f"| Municipio: {t['municipio']}".ljust(63) + "|")
    print(f"| Dirección: {t['direccion'][:48]}".ljust(63) + "|")
    print(f"| Coord.: {t['lat']:.5f}, {t['lon']:.5f}".ljust(63) + "|")
    print("+" + "-" * 62 + "+")


def guardar(tarjetas, archivo="ordenes.json"):
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(tarjetas, f, ensure_ascii=False, indent=1)


def cargar(archivo="ordenes.json"):
    with open(archivo, encoding="utf-8") as f:
        return json.load(f)


def coords_de(tarjetas):
    return [(t["lat"], t["lon"]) for t in tarjetas]
