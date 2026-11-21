/* nucleo.js - Algoritmos (ACO, GA, PSO), asignación por jornada y generación de órdenes.
 * Es la versión en JavaScript de algoritmos.py, experimento.py y ordenes.py, con los mismos
 * parámetros y la misma lógica. Corre en el navegador (GitHub Pages) y en Node.js. */
(function (raiz) {
  "use strict";

  const JORNADA_MIN = 8 * 60;   // jornada laboral del repartidor
  const SERVICIO_MIN = 5;       // minutos por entrega

  /* ---------------- números aleatorios con semilla (mulberry32) ---------------- */
  function crearRng(semilla) {
    let a = (semilla >>> 0);
    const random = () => {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const entero = n => Math.floor(random() * n);
    return {
      random, entero,
      uniforme: (lo, hi) => lo + (hi - lo) * random(),
      normal: (mu, sd) => {
        const u1 = random() || 1e-12, u2 = random();
        return mu + sd * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      },
      shuffle: arr => { for (let i = arr.length - 1; i > 0; i--) { const j = entero(i + 1); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; },
      sample: (n, k) => { const idx = Array.from({ length: n }, (_, i) => i); for (let i = 0; i < k; i++) { const j = i + entero(n - i); [idx[i], idx[j]] = [idx[j], idx[i]]; } return idx.slice(0, k); },
      indicePesos: (pesos, suma) => {
        let r = random() * suma;
        for (let i = 0; i < pesos.length; i++) { r -= pesos[i]; if (r <= 0) return i; }
        return pesos.length - 1;
      },
    };
  }

  /* ---------------- función de costo ---------------- */
  function longitudRuta(ruta, D) {
    const n = ruta.length;
    let s = 0;
    for (let i = 0; i < n; i++) s += D[ruta[i]][ruta[(i + 1) % n]];
    return s;
  }
  function tiempoRuta(ruta, T, servicio = SERVICIO_MIN) {
    return longitudRuta(ruta, T) + servicio * (ruta.length - 1);
  }
  const argsort = x => Array.from(x.keys()).sort((i, j) => x[i] - x[j]);

  /* ---------------- ACO ---------------- */
  function aco(D, o = {}) {
    const { hormigas = 20, iteraciones = 100, alpha = 1, beta = 2, rho = 0.3, q = 1, semilla = 0 } = o;
    const rng = crearRng(semilla), N = D.length;
    const ETA = D.map(f => f.map(v => (v > 0 ? 1 / v : 0)));
    const tau = Array.from({ length: N }, () => new Array(N).fill(1));
    let mejorRuta = null, mejorCosto = Infinity;
    const historial = [];
    for (let it = 0; it < iteraciones; it++) {
      const rutas = [], costos = [];
      for (let h = 0; h < hormigas; h++) {
        const ruta = [0], visit = new Array(N).fill(false);
        visit[0] = true;
        while (ruta.length < N) {
          const actual = ruta[ruta.length - 1];
          const cand = [], peso = [];
          let suma = 0;
          for (let j = 0; j < N; j++) {
            if (visit[j]) continue;
            const w = Math.pow(tau[actual][j], alpha) * Math.pow(ETA[actual][j], beta);
            cand.push(j); peso.push(w); suma += w;
          }
          const sig = (suma === 0 || !isFinite(suma)) ? cand[rng.entero(cand.length)] : cand[rng.indicePesos(peso, suma)];
          ruta.push(sig); visit[sig] = true;
        }
        const c = longitudRuta(ruta, D);
        rutas.push(ruta); costos.push(c);
        if (c < mejorCosto) { mejorCosto = c; mejorRuta = ruta.slice(); }
      }
      for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) tau[i][j] *= (1 - rho);   // evaporación
      rutas.forEach((ruta, k) => {                                                      // depósito (a -> b)
        for (let i = 0; i < N; i++) tau[ruta[i]][ruta[(i + 1) % N]] += q / costos[k];
      });
      historial.push(mejorCosto);
    }
    return { ruta: mejorRuta, costo: mejorCosto, historial };
  }

  /* ---------------- GA ---------------- */
  function cruzaOX(p1, p2, rng) {
    const n = p1.length - 1;
    const [a, b] = rng.sample(n, 2).sort((x, y) => x - y);
    const g1 = p1.slice(1), g2 = p2.slice(1);
    const hijo = new Array(n).fill(null);
    const usados = new Set();
    for (let i = a; i <= b; i++) { hijo[i] = g1[i]; usados.add(g1[i]); }
    const resto = g2.filter(g => !usados.has(g));
    let k = 0;
    for (let i = 0; i < n; i++) if (hijo[i] === null) hijo[i] = resto[k++];
    return [0, ...hijo];
  }
  function ga(D, o = {}) {
    const { poblacion = 50, generaciones = 40, pCruza = 0.9, pMut = 0.2, elite = 2, torneo = 3, semilla = 0 } = o;
    const rng = crearRng(semilla), N = D.length;
    const base = Array.from({ length: N - 1 }, (_, i) => i + 1);
    let pob = Array.from({ length: poblacion }, () => [0, ...rng.shuffle(base.slice())]);
    let costos = pob.map(r => longitudRuta(r, D));
    let i0 = costos.indexOf(Math.min(...costos));
    let mejorRuta = pob[i0].slice(), mejorCosto = costos[i0];
    const historial = [mejorCosto];
    const seleccion = () => {
      const idx = rng.sample(poblacion, torneo);
      let mejor = idx[0];
      for (const i of idx) if (costos[i] < costos[mejor]) mejor = i;
      return pob[mejor];
    };
    for (let g = 0; g < generaciones - 1; g++) {
      const orden = argsort(costos);
      const nueva = orden.slice(0, elite).map(i => pob[i].slice());
      while (nueva.length < poblacion) {
        const p1 = seleccion(), p2 = seleccion();
        const hijo = rng.random() < pCruza ? cruzaOX(p1, p2, rng) : p1.slice();
        if (rng.random() < pMut && N > 2) {          // mutación por intercambio
          const [i, j] = rng.sample(N - 1, 2).map(x => x + 1);
          [hijo[i], hijo[j]] = [hijo[j], hijo[i]];
        }
        nueva.push(hijo);
      }
      pob = nueva;
      costos = pob.map(r => longitudRuta(r, D));
      i0 = costos.indexOf(Math.min(...costos));
      if (costos[i0] < mejorCosto) { mejorCosto = costos[i0]; mejorRuta = pob[i0].slice(); }
      historial.push(mejorCosto);
    }
    return { ruta: mejorRuta, costo: mejorCosto, historial };
  }

  /* ---------------- PSO (random keys) ---------------- */
  function pso(D, o = {}) {
    const { particulas = 20, iteraciones = 100, w = 0.7, c1 = 1.5, c2 = 1.5, semilla = 0 } = o;
    const rng = crearRng(semilla), N = D.length, dim = N - 1;
    const decodificar = x => [0, ...argsort(x).map(i => i + 1)];
    const pos = Array.from({ length: particulas }, () => Array.from({ length: dim }, () => rng.random()));
    const vel = Array.from({ length: particulas }, () => Array.from({ length: dim }, () => rng.uniforme(-0.1, 0.1)));
    let costos = pos.map(p => longitudRuta(decodificar(p), D));
    const pbest = pos.map(p => p.slice()), pbestC = costos.slice();
    let g = pbestC.indexOf(Math.min(...pbestC));
    let gbest = pos[g].slice(), gbestC = costos[g];
    const historial = [gbestC];
    for (let it = 0; it < iteraciones - 1; it++) {
      for (let k = 0; k < particulas; k++) {
        for (let d = 0; d < dim; d++) {
          vel[k][d] = w * vel[k][d] + c1 * rng.random() * (pbest[k][d] - pos[k][d]) + c2 * rng.random() * (gbest[d] - pos[k][d]);
          pos[k][d] += vel[k][d];
        }
      }
      costos = pos.map(p => longitudRuta(decodificar(p), D));
      for (let k = 0; k < particulas; k++) if (costos[k] < pbestC[k]) { pbestC[k] = costos[k]; pbest[k] = pos[k].slice(); }
      g = pbestC.indexOf(Math.min(...pbestC));
      if (pbestC[g] < gbestC) { gbestC = pbestC[g]; gbest = pbest[g].slice(); }
      historial.push(gbestC);
    }
    return { ruta: decodificar(gbest), costo: gbestC, historial };
  }

  /* ---------------- líneas base, jornada y selección de algoritmo ---------------- */
  function rutaNN(D) {
    const n = D.length, ruta = [0], vis = new Set([0]);
    while (ruta.length < n) {
      const a = ruta[ruta.length - 1];
      let mejor = -1;
      for (let j = 0; j < n; j++) if (!vis.has(j) && (mejor < 0 || D[a][j] < D[a][mejor])) mejor = j;
      ruta.push(mejor); vis.add(mejor);
    }
    return ruta;
  }

  /** Órdenes que caben en la jornada (vecino más cercano por tiempo). Índice 0 = centro. */
  function asignarPorJornada(T, jornada = JORNADA_MIN, servicio = SERVICIO_MIN) {
    const n = T.length, elegidas = [0], pendientes = new Set(Array.from({ length: n - 1 }, (_, i) => i + 1));
    let tiempo = 0;
    while (pendientes.size) {
      const actual = elegidas[elegidas.length - 1];
      let sig = -1;
      for (const j of pendientes) if (sig < 0 || T[actual][j] < T[actual][sig]) sig = j;
      const nuevo = tiempo + T[actual][sig] + servicio;
      if (nuevo + T[sig][0] > jornada) break;
      elegidas.push(sig); pendientes.delete(sig); tiempo = nuevo;
    }
    return { elegidas, sobrantes: Array.from(pendientes).sort((a, b) => a - b) };
  }

  function mejorPocas(D) {   // con 3 o menos puntos se prueban todas las permutaciones
    const n = D.length;
    const perms = n === 2 ? [[1]] : [[1, 2], [2, 1]];
    let mejor = null, mejorC = Infinity;
    for (const p of perms) { const r = [0, ...p], c = longitudRuta(r, D); if (c < mejorC) { mejorC = c; mejor = r; } }
    return { ruta: mejor, costo: mejorC };
  }

  /** Corre el algoritmo elegido ("ACO", "GA", "PSO" o "TODOS") con el mismo presupuesto de 2000 evaluaciones. */
  function resolver(Ds, algoritmo) {
    const n = Ds.length;
    if (n <= 3) {
      const r = mejorPocas(Ds);
      return { comparativa: [{ algoritmo: "Pocas órdenes (todas las rutas)", km: +r.costo.toFixed(2) }],
               mejor: { costo: r.costo, nombre: "Pocas órdenes", ruta: r.ruta } };
    }
    const configs = {
      ACO: () => aco(Ds, { hormigas: 20, iteraciones: 100, semilla: 0 }),
      GA: () => ga(Ds, { poblacion: 50, generaciones: 40, semilla: 0 }),
      PSO: () => pso(Ds, { particulas: 20, iteraciones: 100, semilla: 0 }),
    };
    const elegir = configs[algoritmo] ? [algoritmo] : Object.keys(configs);
    const comparativa = [];
    let mejor = { costo: Infinity };
    for (const nombre of elegir) {
      const r = configs[nombre]();
      comparativa.push({ algoritmo: nombre, km: +r.costo.toFixed(2) });
      if (r.costo < mejor.costo) mejor = { costo: r.costo, nombre, ruta: r.ruta };
    }
    return { comparativa, mejor };
  }

  /* ---------------- distancias aproximadas (respaldo sin internet) ---------------- */
  function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371, rad = x => x * Math.PI / 180;
    const dphi = rad(lat2 - lat1), dl = rad(lon2 - lon1);
    const a = Math.sin(dphi / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }
  function matrizHaversine(coords, factorCalle = 1.3, velKmh = 30) {
    const n = coords.length;
    const D = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) =>
      i === j ? 0 : haversineKm(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) * factorCalle));
    const T = D.map(f => f.map(v => v / velKmh * 60));
    return { D, T };
  }

  /* ---------------- órdenes aleatorias ---------------- */
  const ZONAS = [
    { nombre: "Monterrey", lat: 25.6866, lon: -100.3161, peso: 0.28 },
    { nombre: "San Nicolás de los Garza", lat: 25.7417, lon: -100.3022, peso: 0.17 },
    { nombre: "Guadalupe", lat: 25.6769, lon: -100.2563, peso: 0.17 },
    { nombre: "Apodaca", lat: 25.7817, lon: -100.1883, peso: 0.12 },
    { nombre: "General Escobedo", lat: 25.7970, lon: -100.3167, peso: 0.10 },
    { nombre: "San Pedro Garza García", lat: 25.6572, lon: -100.4021, peso: 0.08 },
    { nombre: "Santa Catarina", lat: 25.6733, lon: -100.4586, peso: 0.08 },
  ];
  const DISPERSION_GRADOS = 0.02;

  /** casasPorZona: {nombreZona: [[lat, lon], ...]} o null. Misma semilla = mismas órdenes. */
  function generarOrdenes(n, semilla, casasPorZona) {
    const rng = crearRng(semilla);
    const suma = ZONAS.reduce((s, z) => s + z.peso, 0);
    const disponibles = {};
    for (const z of ZONAS) {
      const lista = (casasPorZona && casasPorZona[z.nombre]) || [];
      const idx = rng.shuffle(Array.from({ length: lista.length }, (_, i) => i));
      disponibles[z.nombre] = idx.map(i => lista[i]);
    }
    const tarjetas = [];
    for (let i = 0; i < n; i++) {
      const z = ZONAS[rng.indicePesos(ZONAS.map(x => x.peso), suma)];
      let lat, lon, tipo;
      if (disponibles[z.nombre].length) {
        [lat, lon] = disponibles[z.nombre].pop(); tipo = "casa";
      } else {
        lat = z.lat + rng.normal(0, DISPERSION_GRADOS); lon = z.lon + rng.normal(0, DISPERSION_GRADOS); tipo = "punto aleatorio";
      }
      tarjetas.push({ municipio: z.nombre, tipo, lat, lon,
        direccion: `Domicilio aprox. en ${z.nombre} (${lat.toFixed(4)}, ${lon.toFixed(4)})` });
    }
    return tarjetas;
  }

  const API = { JORNADA_MIN, SERVICIO_MIN, crearRng, longitudRuta, tiempoRuta, aco, ga, pso, rutaNN,
                asignarPorJornada, resolver, haversineKm, matrizHaversine, ZONAS, generarOrdenes };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else raiz.Nucleo = API;
})(typeof window !== "undefined" ? window : globalThis);
