// Asistente de voz (prueba, opción A). Está en la barra superior de todas las pantallas.
// - Escucha comandos con el reconocimiento de voz del navegador (Chrome o Edge; necesita internet).
//   Solo reacciona a las frases que empiezan con la palabra clave «Sistema». No se guarda ningún audio.
// - Responde por voz con la síntesis del navegador. Prefiere las voces «naturales» (Edge) o de Google (Chrome).
// - Sigue activo al cambiar de pantalla (se recuerda en este navegador).
// Los comandos solo pulsan botones que ya están visibles; lo que borra o cierra algo pide confirmación.
(function () {
  const boton = document.getElementById("btnVoz");
  if (!boton) return;
  const indicador = document.getElementById("estadoVoz");
  const burbuja = document.getElementById("burbujaVoz");
  const selector = document.getElementById("selectorVoz");
  const PALABRA_CLAVE = "sistema";
  const CLAVE_ACTIVO = "epp_voz_activa";
  const CLAVE_VOZ = "epp_voz_nombre";
  const Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition;
  const puedeHablar = "speechSynthesis" in window;
  const url = (nombre) => boton.dataset[`url${nombre}`];

  const guardar = (clave, valor) => { try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ } };
  const leer = (clave) => { try { return localStorage.getItem(clave); } catch (e) { return null; } };

  let activo = false;
  let reconocimiento = null;
  let hablando = false;

  // ---------- Voces: se eligen las más naturales disponibles en español
  function vocesEspanol() {
    return puedeHablar ? window.speechSynthesis.getVoices().filter((v) => /^es/i.test(v.lang)) : [];
  }
  function puntaje(v) {
    let p = 0;
    if (/natural/i.test(v.name)) p += 100;           // Edge: voces neuronales («Online (Natural)»)
    if (/online/i.test(v.name)) p += 40;
    if (/google/i.test(v.name)) p += 30;              // Chrome: «Google español»
    if (/(EC|419|MX|CO|US)$/i.test(v.lang.replace("_", "-"))) p += 10;  // acento latinoamericano
    return p;
  }
  function vozElegida() {
    const voces = vocesEspanol();
    const guardada = voces.find((v) => v.name === leer(CLAVE_VOZ));
    return guardada || voces.sort((a, b) => puntaje(b) - puntaje(a))[0] || null;
  }
  function cambiarVoz() {
    const voces = vocesEspanol().sort((a, b) => puntaje(b) - puntaje(a));
    if (!voces.length) return false;
    const actual = vozElegida();
    const siguiente = voces[(voces.indexOf(actual) + 1) % voces.length];
    guardar(CLAVE_VOZ, siguiente.name);
    llenarSelector();
    hablar(`Ahora uso esta voz: ${siguiente.name.replace(/Microsoft|Online|\(Natural\)|-.*$/gi, "").trim()}.`);
    return true;
  }

  // ---------- Selector de voz (menú junto al micrófono)
  function nombreCorto(v) {
    const base = v.name.replace(/Microsoft|Google|Online|\(Natural\)|-.*$/gi, "").replace(/\s+/g, " ").trim() || v.name;
    const region = (v.lang.split(/[-_]/)[1] || "").toUpperCase();
    const paises = { EC: "Ecuador", MX: "México", CO: "Colombia", ES: "España", US: "Estados Unidos", AR: "Argentina", PE: "Perú", CL: "Chile", VE: "Venezuela", BO: "Bolivia", "419": "Latinoamérica" };
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
  if (selector) {
    selector.addEventListener("change", () => { guardar(CLAVE_VOZ, selector.value); probar(); });
    document.getElementById("btnProbarVoz").addEventListener("click", probar);
  }
  function probar() {
    const nombre = (boton.dataset.docente || "").trim().split(" ")[0];
    hablar(`Hola${nombre ? `, ${nombre}` : ""}. Así sonará el asistente de voz.`, true);
  }

  function hablar(texto, aunqueApagado) {
    if ((!activo && !aunqueApagado) || !puedeHablar || !texto) return;
    window.speechSynthesis.cancel();
    const frase = new SpeechSynthesisUtterance(texto);
    const voz = vozElegida();
    if (voz) frase.voice = voz;
    frase.lang = voz ? voz.lang : "es-ES";
    frase.rate = 1;
    frase.onstart = () => { hablando = true; };
    frase.onend = () => { hablando = false; };
    frase.onerror = () => { hablando = false; };
    window.speechSynthesis.speak(frase);
  }

  function mostrar(texto, tipo = "text-muted-epp") {
    indicador.className = `estado-voz small text-truncate d-none d-md-inline ${tipo}`;
    indicador.textContent = texto;
  }

  // ---------- Burbuja «Te escucho»
  let ocultarBurbuja = null;
  function burbujaVoz(texto, tipo = "") {
    clearTimeout(ocultarBurbuja);
    burbuja.className = `burbuja-voz ${tipo}`;
    burbuja.innerHTML = texto;
    if (tipo) ocultarBurbuja = setTimeout(() => burbuja.classList.add("d-none"), 1800);
  }

  // ---------- Comandos
  const normalizar = (t) => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9ñ ]/g, " ").replace(/\s+/g, " ").trim();
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
    // Paso 1 (QR): Iniciar cámara / Detener. Paso 2 (detección): Detener cámara / Reanudar cámara.
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
  function ir(nombre, frase) {
    const destino = url(nombre);
    if (!destino) return false;
    hablar(frase);
    setTimeout(() => { window.location.href = destino; }, 900); // deja terminar la frase
    return true;
  }

  const COMANDOS = [
    // Confirmación del resumen de práctica
    { palabras: ["confirmar", "si confirmar", "confirmo"], accion: () => modalAbierto() && pulsar("btnEmpezarPractica", "Nueva práctica iniciada.") },
    { palabras: ["cancelar"], accion: () => { if (!modalAbierto()) return false; bootstrap.Modal.getInstance(modal()).hide(); hablar("Cancelado."); return true; } },
    // Verificación
    { palabras: ["iniciar camara", "encender camara", "abrir camara", "activar camara"], accion: () => camara("iniciar") },
    { palabras: ["reanudar", "reanudar camara"], accion: () => camara("iniciar") },
    { palabras: ["detener", "detener camara", "apagar camara", "pausar"], accion: () => camara("detener") },
    { palabras: ["continuar", "verificar", "verificar epp", "empezar"], accion: () => pulsar("btnVerificarEpp", "Ubíquese frente a la cámara.") },
    { palabras: ["otra vez", "verificar de nuevo", "de nuevo", "repetir"], accion: () => pulsar("btnReintentar", "Verificando de nuevo.") },
    { palabras: ["registrar", "registrar intento", "registrar incidencia"], accion: () => pulsar("btnNoConforme", "Intento registrado.") },
    { palabras: ["siguiente", "siguiente estudiante"], accion: () => pulsar("btnTerminar", "Siguiente estudiante.") },
    { palabras: ["nueva practica", "terminar practica"], accion: () => { const ok = pulsar("btnNuevaPractica"); if (ok) hablar("¿Desea terminar esta práctica? Diga: sistema, confirmar; o: sistema, cancelar."); return ok; } },
    // Navegación
    { palabras: ["ir a inicio", "ir al inicio", "inicio", "dashboard"], accion: () => ir("Inicio", "Abriendo el inicio.") },
    { palabras: ["ir a verificacion", "verificacion en vivo", "ir a verificar"], accion: () => ir("Verificacion", "Abriendo la verificación en vivo.") },
    { palabras: ["mis registros de hoy", "registros de hoy"], accion: () => ir("Hoy", "Abriendo sus registros de hoy.") },
    { palabras: ["ir a registros", "registros"], accion: () => ir("Registros", "Abriendo registros.") },
    { palabras: ["ir a reincidentes", "reincidentes", "estudiantes reincidentes"], accion: () => ir("Reincidentes", "Abriendo los estudiantes reincidentes.") },
    { palabras: ["ir a incidencias", "incidencias"], accion: () => ir("Incidencias", "Abriendo incidencias.") },
    { palabras: ["ir a practicas", "practicas", "mis practicas"], accion: () => ir("Practicas", "Abriendo prácticas.") },
    { palabras: ["ir a ayuda", "abrir ayuda"], accion: () => ir("Ayuda", "Abriendo la ayuda.") },
    { palabras: ["volver", "atras", "regresar"], accion: () => { hablar("Volviendo."); setTimeout(() => history.back(), 700); return true; } },
    // Asistente
    { palabras: ["cambiar voz", "otra voz"], accion: cambiarVoz },
    { palabras: ["ayuda", "comandos", "que puedo decir"], accion: () => {
      hablar("Diga sistema, seguido de la orden. En la verificación: iniciar cámara, continuar, otra vez, registrar, siguiente, detener o nueva práctica. Para moverse: ir a registros, incidencias, prácticas o inicio. Para cambiar mi voz: cambiar voz.");
      return true;
    } },
  ];
  const CANDIDATOS = COMANDOS.flatMap((c) => c.palabras.map((p) => ({ p, c }))).sort((a, b) => b.p.length - a.p.length);

  function ejecutar(frase) {
    const texto = normalizar(frase);
    const posicion = texto.indexOf(PALABRA_CLAVE);
    if (posicion === -1) { burbuja.classList.add("d-none"); return; } // sin palabra clave: se ignora
    const orden = texto.slice(posicion + PALABRA_CLAVE.length).trim();
    if (!orden) { burbujaVoz("No entendí", "duda"); return; }
    // Los comandos de más palabras van primero, para que «verificar de nuevo» no se confunda con «verificar».
    const elegido = CANDIDATOS.find(({ p }) => orden === p || orden.startsWith(`${p} `));
    if (elegido && elegido.c.accion()) {
      mostrar(`✓ «${orden}»`, "text-success");
      burbujaVoz('<i class="bi bi-check2 me-1"></i>Listo', "ok");
    } else {
      mostrar(`No disponible aquí: «${orden}»`);
      burbujaVoz(elegido ? "No disponible aquí" : "No entendí", "duda");
    }
  }

  // ---------- Escucha continua
  function crearReconocimiento() {
    const r = new Reconocimiento();
    r.lang = "es-EC";
    r.continuous = true;
    r.interimResults = true; // permite mostrar «Te escucho» apenas se dice la palabra clave
    r.onresult = (evento) => {
      if (hablando) return; // no escucharse a sí mismo
      for (let i = evento.resultIndex; i < evento.results.length; i++) {
        const resultado = evento.results[i];
        const texto = resultado[0].transcript;
        if (resultado.isFinal) ejecutar(texto);
        else if (normalizar(texto).includes(PALABRA_CLAVE)) burbujaVoz('<i class="bi bi-ear me-1"></i>Te escucho<span class="puntos"></span>');
      }
    };
    r.onerror = (evento) => {
      if (evento.error === "not-allowed" || evento.error === "service-not-allowed") {
        mostrar("Permita el micrófono en el navegador.", "text-danger");
        apagar(true);
      } else if (evento.error === "network") {
        mostrar("Sin internet: los comandos de voz no están disponibles.", "text-danger");
      }
    };
    r.onend = () => { if (activo) { try { r.start(); } catch (e) { /* ya estaba iniciado */ } } }; // Chrome corta tras un silencio
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
      hablar(`Hola${nombre ? `, ${nombre}` : ""}. Asistente de voz activado. Para darme una orden, diga primero: sistema.`);
    }
    if (!Reconocimiento) {
      mostrar("Use Chrome o Edge para los comandos de voz.");
      return;
    }
    reconocimiento = reconocimiento || crearReconocimiento();
    try { reconocimiento.start(); } catch (e) { /* ya estaba iniciado */ }
    mostrar("Escuchando… «Sistema, …»");
  }

  function apagar(porError) {
    activo = false;
    guardar(CLAVE_ACTIVO, "0");
    boton.classList.remove("activo");
    boton.setAttribute("aria-pressed", "false");
    boton.innerHTML = '<i class="bi bi-mic-mute"></i>';
    if (reconocimiento) reconocimiento.stop();
    if (puedeHablar) window.speechSynthesis.cancel();
    if (!porError) mostrar("");
    burbuja.classList.add("d-none");
  }

  boton.addEventListener("click", () => (activo ? apagar() : encender(true)));
  if (leer(CLAVE_ACTIVO) === "1") encender(false); // sigue activo al cambiar de pantalla

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
