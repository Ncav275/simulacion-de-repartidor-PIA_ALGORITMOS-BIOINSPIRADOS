/* servicios.js - Servicios gratuitos de OpenStreetMap, llamados directamente desde el navegador.
 *  - Nominatim: geocodificación directa e inversa (1 consulta por segundo, con caché)
 *  - Photon: sugerencias de dirección mientras se escribe
 *  - Overpass: casas reales para generar órdenes aleatorias (o docs/casas.json ya descargado)
 *  - OSRM (servidor demo): matrices de distancia/tiempo y trazo por calles
 * Si un servicio falla, la página usa un respaldo (distancias Haversine o puntos aleatorios). */
(function (raiz) {
  "use strict";

  const BBOX = { latMin: 25.4, latMax: 26.0, lonMin: -100.7, lonMax: -99.9 };
  const enZona = (lat, lon) => lat >= BBOX.latMin && lat <= BBOX.latMax && lon >= BBOX.lonMin && lon <= BBOX.lonMax;
  const dormir = ms => new Promise(r => setTimeout(r, ms));

  /* ---------- caché en el navegador ---------- */
  const CLAVE = "cache_paqueteria_v1";
  let cache = {};
  try { cache = JSON.parse(localStorage.getItem(CLAVE) || "{}"); } catch (e) { cache = {}; }
  function guardarCache() { try { localStorage.setItem(CLAVE, JSON.stringify(cache)); } catch (e) { /* lleno o bloqueado */ } }

  async function fetchJSON(url, opciones = {}, timeoutMs = 20000) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), timeoutMs);
    try {
      const r = await fetch(url, { ...opciones, signal: ctl.signal });
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  /* ---------- Nominatim: una consulta por segundo ---------- */
  let cola = Promise.resolve();
  function nominatim(url) {
    const tarea = cola.then(async () => {
      try { return await fetchJSON(url); } finally { await dormir(1100); }
    });
    cola = tarea.catch(() => {});
    return tarea;
  }

  async function geocodificar(texto) {
    const k = "geo:" + texto;
    if (k in cache) return cache[k];
    const j = await nominatim("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=mx&q=" + encodeURIComponent(texto));
    const res = j.length ? { lat: parseFloat(j[0].lat), lon: parseFloat(j[0].lon) } : null;
    cache[k] = res; guardarCache();
    return res;
  }

  function direccionCorta(a) {
    const calle = a.road || a.pedestrian || a.footway || a.residential;
    const col = a.suburb || a.neighbourhood || a.quarter || a.city_district;
    const muni = a.city || a.town || a.municipality || a.village || a.county;
    const partes = [];
    if (calle) partes.push(a.house_number ? calle + " " + a.house_number : calle);
    if (col) partes.push(col);
    if (muni && muni !== col) partes.push(muni);
    return partes.length ? partes.join(", ") : null;
  }

  async function direccionInversa(lat, lon) {
    const k = "rev2:" + lat.toFixed(5) + "," + lon.toFixed(5);
    if (k in cache) return cache[k];
    try {
      const j = await nominatim("https://nominatim.openstreetmap.org/reverse?format=json&zoom=18&addressdetails=1&accept-language=es&lat=" + lat + "&lon=" + lon);
      const texto = direccionCorta(j.address || {}) || j.display_name || null;
      cache[k] = texto; guardarCache();
      return texto;
    } catch (e) { return null; }
  }

  /* ---------- Photon: sugerencias ---------- */
  const sugCache = {};
  async function sugerencias(q, limite = 6) {
    q = (q || "").trim();
    if (q.length < 3) return [];
    const k = q.toLowerCase();
    if (k in sugCache) return sugCache[k];
    let feats = [];
    try {
      const j = await fetchJSON("https://photon.komoot.io/api/?limit=" + limite + "&lat=25.68&lon=-100.31&bbox=-100.7,25.4,-99.9,26.0&q=" + encodeURIComponent(q), {}, 8000);
      feats = j.features || [];
    } catch (e) { return []; }
    const salida = [], vistos = new Set();
    for (const f of feats) {
      const p = f.properties || {}, [lon, lat] = f.geometry.coordinates;
      if (!enZona(lat, lon)) continue;
      let l1;
      if (p.street) {
        l1 = p.housenumber ? p.street + " " + p.housenumber : p.street;
        if (p.name && p.name !== p.street) l1 = p.name + " - " + l1;
      } else l1 = p.name || "";
      if (!l1) continue;
      const muni = p.city || p.county || p.locality || "";
      const l2 = [p.district || p.locality, muni, p.state].filter(Boolean).join(", ");
      const label = l2 ? l1 + ", " + l2 : l1;
      if (vistos.has(label)) continue;
      vistos.add(label);
      salida.push({ label, linea1: l1, linea2: l2, municipio: muni || "-", lat, lon });
    }
    sugCache[k] = salida;
    return salida;
  }

  /* ---------- Casas reales: casas.json (ya descargado) o Overpass ---------- */
  let precalculadas = null;
  async function cargarPrecalculadas() {
    if (precalculadas !== null) return precalculadas;
    try { precalculadas = await fetchJSON("casas.json", {}, 8000); } catch (e) { precalculadas = {}; }
    return precalculadas;
  }
  async function casasOverpass(z, radio = 3000, maximo = 400) {
    const k = "casas:" + z.lat.toFixed(4) + "," + z.lon.toFixed(4) + "," + radio;
    if (k in cache) return cache[k];
    const consulta = '[out:json][timeout:30];way["building"~"^(house|residential|detached|semidetached_house|terrace)$"]' +
      "(around:" + radio + "," + z.lat + "," + z.lon + ");out center " + maximo + ";";
    const j = await fetchJSON("https://overpass-api.de/api/interpreter",
      { method: "POST", body: new URLSearchParams({ data: consulta }) }, 60000);
    const casas = (j.elements || []).filter(e => e.center).map(e => [e.center.lat, e.center.lon]);
    cache[k] = casas; guardarCache();
    await dormir(800);
    return casas;
  }
  /** Devuelve {zona: [[lat, lon], ...]} para las zonas pedidas (las que fallen quedan vacías). */
  async function casasPorZonas(zonas, alAvance) {
    const pre = await cargarPrecalculadas();
    const salida = {};
    let fallos = 0;
    for (const z of zonas) {
      if (pre[z.nombre] && pre[z.nombre].length) { salida[z.nombre] = pre[z.nombre]; continue; }
      if (alAvance) alAvance(z.nombre);
      try { salida[z.nombre] = await casasOverpass(z); } catch (e) { salida[z.nombre] = []; fallos++; }
    }
    return { casas: salida, fallos };
  }

  /* ---------- OSRM: matrices y trazo por calles ---------- */
  const OSRM = "https://router.project-osrm.org/";
  const lista = coords => coords.map(c => c[1] + "," + c[0]).join(";");

  async function matrizOSRM(coords) {
    const j = await fetchJSON(OSRM + "table/v1/driving/" + lista(coords) + "?annotations=distance,duration", {}, 30000);
    if (!j.distances || !j.durations) throw new Error("respuesta sin matrices");
    const malo = m => m.some(f => f.some(v => v === null || v === undefined));
    if (malo(j.distances) || malo(j.durations)) throw new Error("hay puntos sin ruta");
    return { D: j.distances.map(f => f.map(v => v / 1000)), T: j.durations.map(f => f.map(v => v / 60)) };
  }
  async function geometriaRuta(coords) {
    try {
      const j = await fetchJSON(OSRM + "route/v1/driving/" + lista(coords) + "?overview=full&geometries=geojson", {}, 30000);
      return j.routes[0].geometry.coordinates.map(([lon, lat]) => [lat, lon]);
    } catch (e) { return null; }
  }

  raiz.Serv = { enZona, geocodificar, direccionInversa, sugerencias, casasPorZonas, matrizOSRM, geometriaRuta, dormir };
})(typeof window !== "undefined" ? window : globalThis);
