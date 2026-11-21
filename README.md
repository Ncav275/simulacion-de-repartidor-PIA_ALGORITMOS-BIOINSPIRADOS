# Simulación de Repartidor de Paquetería (ACO, GA y PSO)

**Demo en vivo (GitHub Pages):**  
https://ncav275.github.io/simulacion-de-repartidor-PIA_ALGORITMOS-BIOINSPIRADOS/

---

## Datos académicos
- **Institución:** Universidad Autónoma de Nuevo León (UANL) — Escuela Industrial y Preparatoria Técnica "Álvaro Obregón" (EIAO)
- **Materia:** Algoritmos Bioinspirados (PIA)
- **Especialidad:** Inteligencia Artificial
- **Alumno:** Noah Demian Cavazos López (2251426)
- **Grupo / Aula:** 5V1 · Aula 144

---

## Descripción del proyecto
Simulación de la operación diaria de un repartidor de Mercado Libre en el área metropolitana de Monterrey, saliendo y regresando a un centro de distribución en Apodaca. El proyecto compara tres algoritmos bioinspirados —**Colonia de Hormigas (ACO)**, **Algoritmo Genético (GA)** y **Enjambre de Partículas (PSO)**— para minimizar la distancia total recorrida respetando una jornada laboral de 8 horas (manejo + 5 minutos de servicio por entrega).

La interfaz web permite:
1. Capturar órdenes manualmente con autocompletado de direcciones.
2. Generar lotes de órdenes aleatorias usando domicilios reales de OpenStreetMap (con semilla reproducible).
3. Asignar automáticamente los paquetes que caben en la jornada de 8 horas y optimizar el orden de visita, mostrando la ruta por calles reales, el ahorro contra el orden de llegada y una comparativa entre algoritmos.

---

## Resumen de resultados (10 corridas por escenario)
Se evaluaron escenarios de 10, 30 y 50 órdenes con el mismo presupuesto de evaluaciones ($100 \times n$) y prueba estadística de Mann-Whitney U ($p < 0.05$).

| Órdenes | Orden de llegada (sin optimizar) | Vecino más cercano | ACO (prom.) | GA (prom.) | PSO (prom.) | Ahorro ACO vs. llegada |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 166.7 km | 96.7 km | **86.9 km** | 88.8 km | 96.0 km | **47.9%** |
| **30** | 367.7 km | 163.2 km | **130.8 km** | 181.2 km | 213.4 km | **64.4%** |
| **50** | 667.0 km | 213.5 km | **171.0 km** | 322.9 km | 356.1 km | **74.4%** |

**Conclusión principal:** ACO obtuvo las rutas más cortas y estables en los tres escenarios (con ahorros de 48% a 74% frente al orden de llegada), seguido por GA y PSO.

---

## Estructura del repositorio

### Versión Web (GitHub Pages — JavaScript)
Para que la demo funcione directamente en el navegador sin servidor, la lógica de los algoritmos y los servicios de mapas se portó a JavaScript con los mismos parámetros:
- `index.html` — Interfaz interactiva con mapa Leaflet, modo claro/oscuro, tarjetas de órdenes y métricas.
- `nucleo.js` — Implementación en JS de ACO, GA, PSO, asignación por jornada, generador de órdenes y respaldo Haversine.
- `servicios.js` — Consultas desde el navegador a Nominatim, Photon, Overpass y OSRM (con caché en `localStorage`).

### Versión de escritorio y experimentos (Python)
- `algoritmos.py` — Implementación de ACO, GA, PSO y función de costo asimétrica.
- `datos.py` — Geocodificación (Nominatim), sugerencias (Photon), casas reales (Overpass), matrices y trazo (OSRM / Haversine).
- `ordenes.py` — Generación de órdenes aleatorias y tarjetas de paquetes.
- `experimento.py` — Asignación por jornada, líneas base y comparativa rápida en consola.
- `app.py` y `pagina.py` — Servidor local en Flask con la interfaz web.

---

## Cómo ejecutar la versión en Python localmente

```bash
pip install numpy requests flask
