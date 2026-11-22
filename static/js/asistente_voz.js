// Asistente de voz (opción A). Está en la barra superior de todas las pantallas.
// - Escucha con el reconocimiento de voz del navegador (Chrome o Edge; necesita internet) y solo
//   reacciona cuando oye la palabra clave «Asistente». No se guarda ningún audio.
// - Ejecuta las acciones apenas las entiende y tolera errores pequeños («regitrar» → «registrar»).
// - Una orden nueva interrumpe lo que el asistente esté diciendo.
// - Al navegar, cambia de pantalla cuando termina de hablar (la frase no se corta).
// - La navegación respeta el rol: solo abre las secciones del menú del usuario. Por voz no se modifican
//   datos de administración.
(function () {
  const boton = document.getElementById("btnVoz");
  if (!boton) return;
  const burbuja = document.getElementById("burbujaVoz");
  const selector = document.getElementById("selectorVoz");
  const leerJson = (id) => { try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return []; } };
  const SECCIONES = leerJson("voz-secciones");          // [{nombre, url}] permitidas para este rol
  const SECCIONES_ADMIN = leerJson("voz-secciones-admin"); // nombres de las secciones solo para administradores

  const CLAVE_ACTIVO = "epp_voz_activa";
  const CLAVE_VOZ = "epp_voz_nombre";
  const guardar = (clave, valor) => { try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ } };
  const leer = (clave) => { try { return localStorage.getItem(clave); } catch (e) { return null; } };

  // Palabra clave y cómo la suele «oír» el reconocimiento.
  const PALABRA = { texto: "Asistente", variantes: ["asistente", "asistentes", "la asistente", "oye asistente", "sistente", "asistenta"] };

  const Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition;
  const puedeHablar = "speechSynthesis" in window;
  let activo = false;
  let reconocimiento = null;
  let erroresRed = 0;
  let ultimoEjecutado = -1;  // índice de la frase ya ejecutada (llega varias veces: parcial y final)
  let ultimaFraseOida = -1;  // índice de la última frase con palabra clave (se interrumpe al asistente una sola vez)

  // ---------- Utilidades de texto
  const normalizar = (t) => (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9ñ ]/g, " ").replace(/\s+/g, " ").trim();

  function distancia(a, b) {
    const m = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) m[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      for (let j = 1; j <= b.length; j++) {
        m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
    }
    return m[a.length][b.length];
  }
  const parecido = (a, b) => (a === b ? 1 : 1 - distancia(a, b) / Math.max(a.length, b.length, 1));
  // Cómo suena (no cómo se escribe): b/v, g/j, c/s/z, ll/y y la h muda dan igual.
  const sonido = (t) => t.replace(/h/g, "").replace(/v/g, "b").replace(/w/g, "gu").replace(/ll/g, "y")
    .replace(/g([ei])/g, "j$1").replace(/gu([ei])/g, "g$1").replace(/c([ei])/g, "s$1").replace(/z/g, "s")
    .replace(/qu/g, "k").replace(/c/g, "k").replace(/\s+/g, "");
  const suenaParecido = (a, b) => Math.max(parecido(a, b), parecido(sonido(a), sonido(b)));

  // ---------- Voces
  function vocesEspanol() {
    return puedeHablar ? window.speechSynthesis.getVoices().filter((v) => /^es/i.test(v.lang)) : [];
  }
  function puntaje(v) {
    let p = 0;
    if (/natural/i.test(v.name)) p += 100;
    if (/online/i.test(v.name)) p += 40;
    if (/google/i.test(v.name)) p += 30;
    if (/(EC|419|MX|CO|US)$/i.test(v.lang.replace("_", "-"))) p += 10;
    return p;
  }
  function vozElegida() {
    const voces = vocesEspanol();
    return voces.find((v) => v.name === leer(CLAVE_VOZ)) || voces.sort((a, b) => puntaje(b) - puntaje(a))[0] || null;
  }
  function nombreCorto(v) {
    const base = v.name.replace(/Microsoft|Google|Online|\(Natural\)|-.*$/gi, "").replace(/\s+/g, " ").trim() || v.name;
    const region = (v.lang.split(/[-_]/)[1] || "").toUpperCase();
    const paises = { EC: "Ecuador", MX: "México", CO: "Colombia", ES: "España", US: "Estados Unidos", AR: "Argentina", PE: "Perú", CL: "Chile", VE: "Venezuela", BO: "Bolivia", 419: "Latinoamérica" };
    return `${base}${paises[region] ? ` (${paises[region]})` : region ? ` (${region})` : ""}${/natural/i.test(v.name) ? " · Natural" : ""}`;
  }
  function llenarSelector() {
    if (!selector) return;
    const voces = vocesEspanol().sort((a, b) => puntaje(b) - puntaje(a));
    const elegida = vozElegida();
    selector.innerHTML = voces.length
      ? voces.map((v) => `<option value="${v.name.replace(/"/g, "&quot;")}"${elegida && v.name === elegida.name ? " selected" : ""}>${nombreCorto(v)}</option>`).join("")
      : "<option>No hay voces en español en este navegador</option>";
    selector.disabled = !voces.length;
  }
  if (puedeHablar) window.speechSynthesis.onvoiceschanged = llenarSelector;
  llenarSelector();

  // Nunca se pronuncia la palabra clave: así el asistente no se «escucha» a sí mismo.
  // Devuelve una promesa que se cumple cuando termina de hablar (o a los 8 s como máximo).
  function hablar(texto, aunqueApagado) {
    if ((!activo && !aunqueApagado) || !puedeHablar || !texto) return Promise.resolve();
    window.speechSynthesis.cancel();
    return new Promise((terminar) => {
      const frase = new SpeechSynthesisUtterance(texto);
      const voz = vozElegida();
      if (voz) frase.voice = voz;
      frase.lang = voz ? voz.lang : "es-ES";
      frase.volume = 1;
      frase.onend = terminar;
      frase.onerror = terminar;
      setTimeout(terminar, 8000);
      // Chrome y Edge a veces descartan una frase pedida justo después de cancel(): se deja una pausa mínima.
      setTimeout(() => window.speechSynthesis.speak(frase), 80);
    });
  }
  const callar = () => { if (puedeHablar) window.speechSynthesis.cancel(); };

  function cambiarVoz() {
    const voces = vocesEspanol().sort((a, b) => puntaje(b) - puntaje(a));
    if (!voces.length) return false;
    const siguiente = voces[(voces.indexOf(vozElegida()) + 1) % voces.length];
    guardar(CLAVE_VOZ, siguiente.name);
    llenarSelector();
    hablar(`Ahora uso esta voz: ${nombreCorto(siguiente).replace(" · Natural", "")}.`);
    return true;
  }

  if (selector) {
    selector.addEventListener("change", () => { guardar(CLAVE_VOZ, selector.value); probar(); });
    document.getElementById("btnProbarVoz").addEventListener("click", probar);
  }
  function probar() {
    const nombre = (boton.dataset.docente || "").trim().split(" ")[0];
    hablar(`Hola${nombre ? `, ${nombre}` : ""}. Así sonará la voz de su ayudante.`, true);
  }

  // ---------- Burbuja junto al micrófono (sin textos permanentes)
  let ocultar = null;
  function avisar(html, tipo = "", duracion = 1800) {
    clearTimeout(ocultar);
    burbuja.className = `burbuja-voz ${tipo}`;
    burbuja.innerHTML = html;
    if (tipo) ocultar = setTimeout(() => burbuja.classList.add("d-none"), duracion);
  }
  const esconder = () => { clearTimeout(ocultar); burbuja.classList.add("d-none"); };

  // ---------- Acciones de la verificación
  const visible = (el) => el && !el.disabled && el.offsetParent !== null;
  const modal = () => document.getElementById("modalResumen");
  const modalAbierto = () => modal() && modal().classList.contains("show");
  function pulsar(id, respuesta) {
    const el = document.getElementById(id);
    if (!visible(el)) return false;
    el.click();
    if (respuesta) hablar(respuesta);
    return true;
  }
  function camara(accion) {
    const deteccion = document.getElementById("btnCamara");
    if (visible(deteccion)) {
      const encendida = deteccion.textContent.includes("Detener");
      if ((accion === "iniciar" && encendida) || (accion === "detener" && !encendida)) return false;
      deteccion.click();
      hablar(accion === "iniciar" ? "Cámara reanudada." : "Cámara detenida.");
      return true;
    }
    return accion === "iniciar" ? pulsar("btnIniciar", "Cámara iniciada. Acerque el código QR.") : pulsar("btnDetener", "Cámara detenida.");
  }
  // Se cambia de pantalla cuando termina la frase, para que no se corte.
  function irA(destino, frase) {
    hablar(frase).then(() => { window.location.href = destino; });
    return true;
  }

  const ACCIONES = [
    { frases: ["confirmar", "si confirmar", "confirmo", "si"], hacer: () => modalAbierto() && pulsar("btnEmpezarPractica", "Nueva práctica iniciada.") },
    { frases: ["cancelar", "no"], hacer: () => { if (!modalAbierto()) return false; bootstrap.Modal.getInstance(modal()).hide(); hablar("Cancelado."); return true; } },
    { frases: ["iniciar camara", "encender camara", "abrir camara", "activar camara", "prender camara"], hacer: () => camara("iniciar") },
    { frases: ["reanudar", "reanudar camara"], hacer: () => camara("iniciar") },
    { frases: ["detener", "detener camara", "apagar camara", "pausar", "parar camara"], hacer: () => camara("detener") },
    { frases: ["continuar", "verificar epp", "empezar verificacion", "verificar"], hacer: () => pulsar("btnVerificarEpp", "Ubíquese frente a la cámara.") },
    { frases: ["otra vez", "verificar de nuevo", "de nuevo", "repetir", "volver a verificar"], hacer: () => pulsar("btnReintentar", "Verificando de nuevo.") },
    { frases: ["registrar", "registrar intento", "registrar incidencia", "guardar intento"], hacer: () => pulsar("btnNoConforme", "Intento registrado.") },
    { frases: ["siguiente", "siguiente estudiante", "otro estudiante"], hacer: () => pulsar("btnTerminar", "Siguiente estudiante.") },
    { frases: ["nueva practica", "terminar practica", "cerrar practica"], hacer: () => pulsar("btnNuevaPractica", "¿Desea terminar esta práctica? Diga: confirmar, o cancelar.") },
    { frases: ["volver", "atras", "regresar"], hacer: () => { hablar("Volviendo.").then(() => history.back()); return true; } },
    { frases: ["cambiar voz", "otra voz"], hacer: cambiarVoz },
    { frases: ["silencio", "callate", "para", "basta"], hacer: () => { callar(); return true; } },
    { frases: ["ayuda", "comandos", "que puedo decir"], hacer: () => {
      hablar("Puedo iniciar la cámara, continuar, verificar otra vez, registrar, pasar al siguiente, detener la cámara o terminar la práctica. También puedo abrir secciones, por ejemplo: ir a registros. Para detenerme, diga: silencio.");
      return true;
    } },
  ];
  const FRASES = ACCIONES.flatMap((a) => a.frases.map((f) => ({ f, a }))).sort((x, y) => y.f.length - x.f.length);

  // Navegación: «ir a …», «abrir …», «abre …», «llévame a …», o solo el nombre de la sección.
  const VERBOS = /^(ir a la |ir al |ir a |ve a |vamos a |abrir la |abrir |abre |llevame a |mostrar |muestrame |entrar a |pantalla de )/;
  const ALIAS = {
    "inicio": ["dashboard", "pagina principal", "principal", "indicadores"],
    "verificacion en vivo": ["verificacion", "verificar en vivo", "camara en vivo"],
    "registros": ["historial", "validaciones"],
    "carnes pendientes": ["pendientes", "carnes"],
    "incidencias": ["intentos no conformes"],
    "practicas": ["mis practicas", "resumen de practicas"],
    "ayuda": ["manual"],
    "catalogo epp": ["catalogo", "epp", "catalogo de epp"],
    "estudiantes y carnes": ["estudiantes"],
    "usuarios y roles": ["usuarios", "roles", "docentes"],
    "periodos academicos": ["periodos"],
    "parametros generales": ["parametros", "configuracion"],
    "modelo de vision": ["modelos", "modelo"],
  };
  function destinos() {
    const lista = SECCIONES.map((s) => ({ nombres: [normalizar(s.nombre), ...(ALIAS[normalizar(s.nombre)] || [])], url: s.url, nombre: s.nombre }));
    lista.push({ nombres: ["reincidentes", "estudiantes reincidentes"], url: boton.dataset.urlReincidentes, nombre: "Estudiantes reincidentes" });
    lista.push({ nombres: ["mis registros de hoy", "registros de hoy"], url: boton.dataset.urlHoy, nombre: "Mis registros de hoy" });
    return lista;
  }
  function buscarSeccion(texto, estricto) {
    let mejor = null;
    for (const d of destinos()) {
      for (const n of d.nombres) {
        const p = parecido(texto, n);
        if (p >= (estricto ? 0.9 : 0.78) && (!mejor || p > mejor.p)) mejor = { ...d, p };
      }
    }
    return mejor;
  }
  function esSeccionAdmin(texto) {
    return SECCIONES_ADMIN.some((n) => {
      const base = normalizar(n);
      return parecido(texto, base) >= 0.78 || (ALIAS[base] || []).some((a) => parecido(texto, a) >= 0.85);
    });
  }

  // Devuelve {tipo, hacer} o null si no se reconoce la orden.
  function interpretar(orden) {
    const conVerbo = VERBOS.test(orden);
    const resto = orden.replace(VERBOS, "").trim();
    if (!conVerbo) {
      const accion = FRASES.find(({ f }) => orden === f || orden.startsWith(`${f} `))
        || FRASES.map(({ f, a }) => ({ f, a, p: parecido(orden, f) })).filter((x) => x.p >= 0.8).sort((x, y) => y.p - x.p)[0];
      if (accion) return { tipo: "accion", hacer: () => accion.a.hacer() };
    }
    const seccion = buscarSeccion(resto, !conVerbo);
    if (seccion) {
      if (window.location.pathname === seccion.url.split("?")[0] && !seccion.url.includes("?")) {
        return { tipo: "navegar", hacer: () => { hablar(`Ya está en ${seccion.nombre}.`); return true; } };
      }
      return { tipo: "navegar", hacer: () => irA(seccion.url, `Abriendo ${seccion.nombre}.`) };
    }
    if (conVerbo && esSeccionAdmin(resto)) {
      return { tipo: "navegar", hacer: () => { hablar("Esa sección es solo para administradores."); avisar("Solo para administradores", "duda", 2500); return true; } };
    }
    return null;
  }

  // Busca la palabra clave al inicio de la frase (tolerando errores) y devuelve lo que sigue.
  function separarOrden(texto) {
    const palabras = texto.split(" ");
    for (let i = 0; i < Math.min(palabras.length, 4); i++) {
      for (const largo of [3, 2, 1]) {
        const candidato = palabras.slice(i, i + largo).join(" ");
        if (PALABRA.variantes.some((v) => suenaParecido(candidato, v) >= 0.8)) {
          return { hay: true, orden: palabras.slice(i + largo).join(" ").trim() };
        }
      }
    }
    return { hay: false, orden: "" };
  }

  function procesar(transcripcion, indice, final) {
    // Para revisar qué entendió el navegador: F12 → Consola.
    if (final) console.debug("[voz] oí:", transcripcion);
    const { hay, orden } = separarOrden(normalizar(transcripcion));
    if (!hay) { if (final) esconder(); return; }
    // La misma frase sigue llegando (parcial y final) después de ejecutarse: se ignora y NO se calla
    // la respuesta que el asistente acaba de empezar.
    if (indice === ultimoEjecutado) return;
    if (indice !== ultimaFraseOida) { callar(); ultimaFraseOida = indice; } // una orden nueva interrumpe al asistente
    if (!orden) { avisar('<i class="bi bi-ear me-1"></i>Te escucho<span class="puntos"></span>'); return; }
    const pedido = interpretar(orden);
    // La navegación espera a que termine la frase («ir a registros» … «de hoy»); las acciones se ejecutan al instante.
    if (pedido && (final || pedido.tipo === "accion")) {
      ultimoEjecutado = indice;
      if (pedido.hacer()) avisar('<i class="bi bi-check2 me-1"></i>Listo', "ok");
      else avisar("No disponible aquí", "duda");
    } else if (final) {
      avisar("No entendí", "duda");
    } else {
      avisar('<i class="bi bi-ear me-1"></i>Te escucho<span class="puntos"></span>');
    }
  }

  // ---------- Escucha continua
  function crearReconocimiento() {
    const r = new Reconocimiento();
    r.lang = "es-EC";
    r.continuous = true;
    r.interimResults = true;  // permite actuar apenas se entiende la orden
    r.maxAlternatives = 3;    // se prueban otras interpretaciones si la primera no sirve
    r.onresult = (evento) => {
      erroresRed = 0;
      for (let i = evento.resultIndex; i < evento.results.length; i++) {
        const resultado = evento.results[i];
        const alternativas = Array.from(resultado).map((a) => a.transcript);
        const util = alternativas.find((t) => { const s = separarOrden(normalizar(t)); return s.hay && s.orden && interpretar(s.orden); });
        procesar(util || alternativas[0], i, resultado.isFinal);
      }
    };
    r.onerror = (evento) => {
      if (evento.error === "not-allowed" || evento.error === "service-not-allowed") {
        avisar("Permita el micrófono en el navegador", "error", 5000);
        apagar(true);
      } else if (evento.error === "language-not-supported") {
        r.lang = "es-ES";
      } else if (evento.error === "network") {
        // Los cortes cortos del servicio son normales: se reintenta en silencio.
        erroresRed += 1;
        if (!navigator.onLine || erroresRed >= 4) avisar("Sin conexión con el servicio de voz", "error", 4000);
      }
    };
    r.onstart = () => { ultimoEjecutado = -1; ultimaFraseOida = -1; }; // los índices vuelven a 0 en cada sesión
    r.onend = () => {
      if (!activo) return;
      setTimeout(() => { try { r.start(); } catch (e) { /* ya estaba iniciado */ } }, erroresRed ? 1000 : 150);
    };
    return r;
  }

  function encender(saludar) {
    activo = true;
    guardar(CLAVE_ACTIVO, "1");
    boton.classList.add("activo");
    boton.setAttribute("aria-pressed", "true");
    boton.innerHTML = '<i class="bi bi-mic-fill"></i>';
    if (saludar) {
      const nombre = (boton.dataset.docente || "").trim().split(" ")[0];
      hablar(`Hola${nombre ? `, ${nombre}` : ""}. Estoy lista para ayudarle.`);
      avisar(`Diga «${PALABRA.texto}, …»`, "ok", 3500);
    }
    if (!Reconocimiento) { avisar("Use Chrome o Edge para las órdenes de voz", "error", 5000); return; }
    reconocimiento = reconocimiento || crearReconocimiento();
    try { reconocimiento.start(); } catch (e) { /* ya estaba iniciado */ }
  }

  function apagar(porError) {
    activo = false;
    guardar(CLAVE_ACTIVO, "0");
    boton.classList.remove("activo");
    boton.setAttribute("aria-pressed", "false");
    boton.innerHTML = '<i class="bi bi-mic-mute"></i>';
    if (reconocimiento) reconocimiento.stop();
    callar();
    if (!porError) esconder();
  }

  boton.addEventListener("click", () => (activo ? apagar() : encender(true)));
  if (leer(CLAVE_ACTIVO) === "1") encender(false);

  // ---------- Respuestas a lo que pasa en la verificación
  document.addEventListener("epp:identificacion", (evento) => {
    const datos = evento.detail;
    if (datos.ok && datos.estudiante) hablar(`Estudiante identificado: ${String(datos.estudiante.nombre).split(" ")[0]}.`);
    else hablar("No se pudo identificar el carné.");
  });
  document.addEventListener("epp:resultado", (evento) => {
    const datos = evento.detail;
    if (datos.resultado === "conforme") {
      hablar("Cumple. Puede ingresar al laboratorio.");
    } else {
      const faltan = (datos.faltantes || []).map((f) => f.toLowerCase());
      const lista = faltan.length > 1 ? `${faltan.slice(0, -1).join(", ")} y ${faltan[faltan.length - 1]}` : faltan[0] || "";
      hablar(`No cumple.${lista ? ` Falta: ${lista}.` : ""} Colóquese los equipos faltantes.`);
    }
  });

  window.addEventListener("pagehide", () => { if (reconocimiento) reconocimiento.abort(); });
})();
