/* app.js - Interfaz interactiva que conecta nucleo.js, servicios.js y Leaflet. */
(function () {
  "use strict";

  // Centro de Distribución (CEDIS) de referencia en la ZMM
  const CENTRO = {
    nombre: "CEDIS Mercado Libre (Rectoría UANL ref.)",
    lat: 25.7255,
    lon: -100.3134,
  };

  let ordenes = [];
  let seleccionActual = null;
  let timerSug = null;

  // Elementos del DOM
  const $estado = document.getElementById("estado-sistema");
  const $inputDir = document.getElementById("input-direccion");
  const $listaSug = document.getElementById("lista-sugerencias");
  const $btnAgregar = document.getElementById("btn-agregar");
  const $inputCant = document.getElementById("input-cantidad");
  const $inputSem = document.getElementById("input-semilla");
  const $chkCasas = document.getElementById("chk-casas");
  const $btnGenerar = document.getElementById("btn-generar");
  const $btnLimpiar = document.getElementById("btn-limpiar");
  const $selAlg = document.getElementById("select-algoritmo");
  const $selFuente = document.getElementById("select-fuente");
  const $btnOpt = document.getElementById("btn-optimizar");
  const $contador = document.getElementById("contador-ordenes");
  const $listaOrd = document.getElementById("lista-ordenes");
  const $panelRes = document.getElementById("panel-resultados");
  const $tablaComp = document.getElementById("tabla-comparativa");

  const setEstado = msg => { $estado.textContent = msg; };

  /* ---------------- Mapa Leaflet con mosaicos de Esri ---------------- */
  const mapa = L.map("mapa").setView([CENTRO.lat, CENTRO.lon], 11);
  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Tiles &copy; Esri" }
  ).addTo(mapa);

  const capaMarcadores = L.layerGroup().addTo(mapa);
  const capaRuta = L.layerGroup().addTo(mapa);

  function dibujarBase() {
    capaMarcadores.clearLayers();
    // Marcador del CEDIS
    L.circleMarker([CENTRO.lat, CENTRO.lon], {
      radius: 9, color: "#2d3277", fillColor: "#ffe600", fillOpacity: 1, weight: 3,
    }).bindPopup(`<b>CEDIS (Salida / Regreso)</b><br>${CENTRO.nombre}`).addTo(capaMarcadores);

    ordenes.forEach((o, idx) => {
      L.circleMarker([o.lat, o.lon], {
        radius: 6, color: "#3483fa", fillColor: "#3483fa", fillOpacity: 0.85, weight: 2,
      }).bindPopup(`<b>Orden #${idx + 1}</b><br>${o.direccion}`).addTo(capaMarcadores);
    });
  }

  function renderLista() {
    $contador.textContent = ordenes.length;
    $listaOrd.innerHTML = "";
    ordenes.forEach((o, idx) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span><span class="tag-orden">#${idx + 1}</span> ${o.direccion}</span>
        <button title="Eliminar">&times;</button>
      `;
      li.querySelector("button").onclick = () => {
        ordenes.splice(idx, 1);
        capaRuta.clearLayers();
        $panelRes.classList.add("oculto");
        renderLista();
        dibujarBase();
      };
      $listaOrd.appendChild(li);
    });
  }

  /* ---------------- Autocompletado con Photon ---------------- */
  $inputDir.addEventListener("input", () => {
    seleccionActual = null;
    clearTimeout(timerSug);
    const q = $inputDir.value.trim();
    if (q.length < 3) { $listaSug.classList.add("oculto"); return; }
    timerSug = setTimeout(async () => {
      const sugs = await Serv.sugerencias(q);
      if (!sugs.length) { $listaSug.classList.add("oculto"); return; }
      $listaSug.innerHTML = "";
      sugs.forEach(s => {
        const li = document.createElement("li");
        li.innerHTML = `${s.linea1}<small>${s.linea2}</small>`;
        li.onclick = () => {
          seleccionActual = s;
          $inputDir.value = s.label;
          $listaSug.classList.add("oculto");
        };
        $listaSug.appendChild(li);
      });
      $listaSug.classList.remove("oculto");
    }, 300);
  });

  document.addEventListener("click", e => {
    if (!e.target.closest(".autocomplete-wrap")) $listaSug.classList.add("oculto");
  });

  /* ---------------- Agregar orden manual ---------------- */
  $btnAgregar.addEventListener("click", async () => {
    const texto = $inputDir.value.trim();
    if (!texto) return;
    $btnAgregar.disabled = true;
    try {
      if (seleccionActual) {
        ordenes.push({
          direccion: seleccionActual.label,
          municipio: seleccionActual.municipio,
          lat: seleccionActual.lat,
          lon: seleccionActual.lon,
        });
      } else {
        setEstado("Geocodificando dirección...");
        const q = texto.toLowerCase().includes("nuevo león") ? texto : `${texto}, Monterrey, Nuevo León, México`;
        const res = await Serv.geocodificar(q);
        if (!res) { alert("No se encontró la dirección. Intenta ser más específico."); return; }
        ordenes.push({ direccion: texto, municipio: "ZMM", lat: res.lat, lon: res.lon });
      }
      $inputDir.value = "";
      seleccionActual = null;
      capaRuta.clearLayers();
      renderLista();
      dibujarBase();
      setEstado("Orden agregada");
    } finally {
      $btnAgregar.disabled = false;
    }
  });

  /* ---------------- Clic en el mapa para agregar parada ---------------- */
  mapa.on("click", async e => {
    const { lat, lng } = e.latlng;
    const idx = ordenes.length;
    ordenes.push({ direccion: `Punto en mapa (${lat.toFixed(4)}, ${lng.toFixed(4)})`, municipio: "ZMM", lat, lon: lng });
    renderLista();
    dibujarBase();
    const dir = await Serv.direccionInversa(lat, lng);
    if (dir && ordenes[idx]) {
      ordenes[idx].direccion = dir;
      renderLista();
      dibujarBase();
    }
  });

  /* ---------------- Generar lote aleatorio ---------------- */
  $btnGenerar.addEventListener("click", async () => {
    const n = Math.max(3, Math.min(60, parseInt($inputCant.value, 10) || 20));
    const sem = parseInt($inputSem.value, 10) || 0;
    $btnGenerar.disabled = true;
    capaRuta.clearLayers();
    $panelRes.classList.add("oculto");
    try {
      let casas = null;
      if ($chkCasas.checked) {
        setEstado("Descargando casas reales (Overpass)...");
        const r = await Serv.casasPorZonas(Nucleo.ZONAS, zona => setEstado(`Cargando casas: ${zona}...`));
        casas = r.casas;
      }
      ordenes = Nucleo.generarOrdenes(n, sem, casas);
      renderLista();
      dibujarBase();
      setEstado(`${n} órdenes generadas (semilla ${sem})`);
    } finally {
      $btnGenerar.disabled = false;
    }
  });

  $btnLimpiar.addEventListener("click", () => {
    ordenes = [];
    capaRuta.clearLayers();
    $panelRes.classList.add("oculto");
    renderLista();
    dibujarBase();
    setEstado("Lista limpia");
  });

  /* ---------------- Optimizar ruta ---------------- */
  $btnOpt.addEventListener("click", async () => {
    if (ordenes.length < 2) {
      alert("Agrega al menos 2 órdenes para optimizar una ruta.");
      return;
    }
    $btnOpt.disabled = true;
    capaRuta.clearLayers();

    try {
      const coords = [[CENTRO.lat, CENTRO.lon], ...ordenes.map(o => [o.lat, o.lon])];
      let D, T, fuente = "Haversine";

      if ($selFuente.value === "auto") {
        setEstado("Consultando matriz de calles (OSRM)...");
        try {
          const m = await Serv.matrizOSRM(coords);
          D = m.D; T = m.T; fuente = "OSRM (calles reales)";
        } catch (err) {
          const m = Nucleo.matrizHaversine(coords);
          D = m.D; T = m.T; fuente = "Haversine (respaldo)";
        }
      } else {
        const m = Nucleo.matrizHaversine(coords);
        D = m.D; T = m.T;
      }

      // 1. Asignación por jornada de 8 h
      const { elegidas, sobrantes } = Nucleo.asignarPorJornada(T);
      const elegidasOrd = [...elegidas].sort((a, b) => a - b); // mantiene orden de llegada
      const Ds = elegidasOrd.map(i => elegidasOrd.map(j => D[i][j]));
      const Ts = elegidasOrd.map(i => elegidasOrd.map(j => T[i][j]));

      // 2. Líneas base
      const rutaLlegada = elegidasOrd.map((_, i) => i);
      const kmLlegada = Nucleo.longitudRuta(rutaLlegada, Ds);
      const rutaVecino = Nucleo.rutaNN(Ds);
      const kmVecino = Nucleo.longitudRuta(rutaVecino, Ds);

      // 3. Algoritmos
      setEstado("Ejecutando algoritmos...");
      await Serv.dormir(30); // deja refrescar la UI
      const { comparativa, mejor } = Nucleo.resolver(Ds, $selAlg.value);

      const kmOpt = mejor.costo;
      const ahorroKm = kmLlegada - kmOpt;
      const ahorroPct = kmLlegada > 0 ? (ahorroKm / kmLlegada) * 100 : 0;
      const minJornada = Nucleo.tiempoRuta(mejor.ruta, Ts);

      // 4. Mostrar métricas y tabla
      document.getElementById("res-algoritmo").textContent = mejor.nombre;
      document.getElementById("res-km").textContent = `${kmOpt.toFixed(1)} km`;
      document.getElementById("res-ahorro").textContent = `${ahorroKm.toFixed(1)} km (${ahorroPct.toFixed(1)}%)`;
      document.getElementById("res-tiempo").textContent = `${(minJornada / 60).toFixed(1)} h / 8.0 h`;
      document.getElementById("res-paquetes").textContent = `${elegidasOrd.length - 1} (${sobrantes.length} pendientes)`;

      const filas = [
        { nombre: "Orden de llegada (sin optimizar)", km: kmLlegada, base: true },
        { nombre: "Vecino más cercano (línea base)", km: kmVecino, base: false },
        ...comparativa.map(c => ({ nombre: c.algoritmo, km: c.km, ganador: c.algoritmo === mejor.nombre })),
      ];

      $tablaComp.innerHTML = filas.map(f => {
        const diff = kmLlegada - f.km;
        const pct = kmLlegada > 0 ? (diff / kmLlegada) * 100 : 0;
        const txtAhorro = f.base ? "—" : `${diff.toFixed(1)} km (${pct.toFixed(1)}%)`;
        return `<tr class="${f.ganador ? "ganador" : ""}">
          <td>${f.nombre}</td><td>${f.km.toFixed(2)}</td><td>${txtAhorro}</td>
        </tr>`;
      }).join("");
      $panelRes.classList.remove("oculto");

      // 5. Dibujar ruta en el mapa (por calles con OSRM o línea recta si falla)
      const ptsOrdenados = mejor.ruta.map(idx => coords[elegidasOrd[idx]]);
      ptsOrdenados.push(coords[0]); // regreso al CEDIS

      let trazo = null;
      if ($selFuente.value === "auto") {
        setEstado("Trazando ruta por calles...");
        trazo = await Serv.geometriaRuta(ptsOrdenados);
      }

      L.polyline(trazo || ptsOrdenados, { color: "#2d3277", weight: 4, opacity: 0.85 }).addTo(capaRuta);

      // Numerar paradas en el orden óptimo
      mejor.ruta.forEach((idx, paso) => {
        if (paso === 0) return; // CEDIS
        const idGlobal = elegidasOrd[idx];
        const o = ordenes[idGlobal - 1];
        L.marker([o.lat, o.lon], {
          icon: L.divIcon({
            className: "pin-num",
            html: `<div style="background:#2d3277;color:#ffe600;font-weight:700;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:11px;border:2px solid #fff;">${paso}</div>`,
            iconSize: [22, 22],
          }),
        }).bindPopup(`<b>Parada #${paso}</b><br>${o.direccion}`).addTo(capaRuta);
      });

      mapa.fitBounds(L.latLngBounds(ptsOrdenados), { padding: [30, 30] });
      setEstado(`Listo · Matriz: ${fuente}`);
    } finally {
      $btnOpt.disabled = false;
    }
  });

  dibujarBase();
})();