// Detección de EPP en vivo (HU06 / RF05) y resultado de cumplimiento (HU07 / RF06).
// Toma fotogramas del video, los envía al servicio de detección (TK07) y dibuja
// los recuadros. Los fotogramas solo viajan en memoria: no se guardan (RF05-CA05).
//
// Estabilización (HU07-CA03): el estado de los EPP obligatorios debe mantenerse igual
// durante el tiempo configurado en el laboratorio. Para que un fotograma borroso no
// reinicie la cuenta, cada EPP usa su mejor confianza del último segundo.
(function () {
  const laboratorios = JSON.parse(document.getElementById("datos-laboratorios").textContent);
  const nombresEpp = JSON.parse(document.getElementById("nombres-epp").textContent);

  const $ = (id) => document.getElementById(id);
  const selLaboratorio = $("laboratorio");
  const pasoIdentificacion = $("pasoIdentificacion");
  const pasoDeteccion = $("pasoDeteccion");
  const btnVerificarEpp = $("btnVerificarEpp");
  const btnTerminar = $("btnTerminar");
  const btnReintentar = $("btnReintentar");
  const video = $("video");
  const lienzo = $("lienzo");
  const videoVacio = $("videoVacio");
  const mensaje = $("mensajeDeteccion");
  const listaEpp = $("listaEpp");
  const velocidad = $("velocidad");
  const estudianteDeteccion = $("estudianteDeteccion");
  const progreso = $("progreso");
  const textoProgreso = $("textoProgreso");
  const barraProgreso = $("barraProgreso");
  const resultadoFinal = $("resultadoFinal");

  const ANCHO_ENVIO = 640; // el modelo trabaja a 640 px: enviar más grande solo hace más lento el envío
  const SIN_DETECCION_MS = 1500; // tiempo sin detecciones antes de avisar (HU06-CA03)
  const VENTANA_MS = 1000; // cada EPP usa su mejor confianza del último segundo
  const captura = document.createElement("canvas");

  let estudiante = null;
  let flujo = null;
  let activo = false; // la cámara está encendida
  let pausado = false; // ya hay resultado: no se envían más fotogramas
  let ultimaDeteccion = 0;
  let tiempos = [];

  // Estado de la estabilización
  let historial = []; // [{ t, confianzas: {clase: confianza} }]
  let claveEstable = null;
  let inicioEstable = null;
  let maximos = {};

  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor ?? "—";
    return span.innerHTML;
  }

  function laboratorioActual() {
    return laboratorios.find((l) => String(l.id) === selLaboratorio.value) || { requisitos: [], estabilizacion: 3 };
  }

  function avisar(clase, contenido) {
    mensaje.innerHTML = contenido ? `<div class="aviso ${clase}">${contenido}</div>` : "";
  }

  function pct(valor) {
    return `${Math.round(valor * 100)} %`;
  }

  // ---------- Paso 1 → Paso 2
  document.addEventListener("epp:identificacion", (evento) => {
    const datos = evento.detail;
    estudiante = datos.ok ? datos.estudiante : null;
    btnVerificarEpp.disabled = !estudiante;
  });

  btnVerificarEpp.addEventListener("click", async () => {
    if (!estudiante) return;
    if (!laboratorioActual().requisitos.some((r) => r.obligatorio)) {
      $("resultado").insertAdjacentHTML("beforeend", '<div class="aviso aviso-warn mt-3">El laboratorio seleccionado no tiene EPP obligatorios configurados.</div>');
      return;
    }
    await window.EPP.detenerLector();
    pasoIdentificacion.classList.add("d-none");
    pasoDeteccion.classList.remove("d-none");
    estudianteDeteccion.textContent = `${estudiante.nombre} · ${selLaboratorio.options[selLaboratorio.selectedIndex].text}`;
    selLaboratorio.disabled = true;
    reiniciarEvaluacion();
    iniciar();
  });

  btnTerminar.addEventListener("click", () => {
    detener();
    estudiante = null;
    btnVerificarEpp.disabled = true;
    selLaboratorio.disabled = false;
    pasoDeteccion.classList.add("d-none");
    pasoIdentificacion.classList.remove("d-none");
    $("resultado").textContent = "Esperando la lectura del código QR…";
  });

  // El estudiante corrige sus EPP y se vuelve a evaluar.
  btnReintentar.addEventListener("click", reiniciarEvaluacion);

  function reiniciarEvaluacion() {
    historial = [];
    claveEstable = null;
    inicioEstable = null;
    maximos = {};
    pausado = false;
    resultadoFinal.classList.add("d-none");
    resultadoFinal.innerHTML = "";
    btnReintentar.classList.add("d-none");
    progreso.classList.remove("d-none");
    mostrarProgreso(0, "Esperando una detección estable…");
    pintarLista({});
  }

  // ---------- Cámara
  async function iniciar() {
    avisar("", "");
    videoVacio.textContent = "Iniciando la cámara…";
    videoVacio.classList.remove("d-none");
    try {
      flujo = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    } catch (e) {
      videoVacio.textContent = "No se pudo acceder a la cámara. Revise que el navegador tenga permiso.";
      return;
    }
    video.srcObject = flujo;
    await video.play();
    videoVacio.classList.add("d-none");
    activo = true;
    ultimaDeteccion = performance.now();
    tiempos = [];
    ciclo();
  }

  function detener() {
    activo = false;
    if (flujo) flujo.getTracks().forEach((pista) => pista.stop());
    flujo = null;
    video.srcObject = null;
    lienzo.getContext("2d").clearRect(0, 0, lienzo.width, lienzo.height);
    velocidad.textContent = "";
  }

  function fotograma() {
    const escala = ANCHO_ENVIO / video.videoWidth;
    captura.width = ANCHO_ENVIO;
    captura.height = Math.round(video.videoHeight * escala);
    captura.getContext("2d").drawImage(video, 0, 0, captura.width, captura.height);
    return new Promise((resolver) => captura.toBlob(resolver, "image/jpeg", 0.75));
  }

  const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

  // Un fotograma a la vez: se envía el siguiente cuando llega la respuesta del anterior.
  async function ciclo() {
    while (activo) {
      if (!video.videoWidth || pausado) {
        await esperar(100);
        continue;
      }
      const inicio = performance.now();
      try {
        const datos = new FormData();
        datos.append("fotograma", await fotograma(), "fotograma.jpg");
        const respuesta = await fetch(window.EPP.urlDetectar, {
          method: "POST",
          headers: { "X-CSRFToken": window.EPP.csrf },
          body: datos,
        });
        const resultado = await respuesta.json();
        if (!activo || pausado) continue;
        if (!resultado.ok) {
          // HU06-CA03 / RF05-CA04: servicio no disponible → mensaje, sin resultado ni registro.
          avisar("aviso-error", `<i class="bi bi-x-octagon me-1"></i>${texto(resultado.mensaje)}`);
          dibujar([]);
          reiniciarCuenta();
          await esperar(2000);
          continue;
        }
        procesar(resultado.detecciones);
        medir(performance.now() - inicio);
      } catch (e) {
        if (!activo) break;
        avisar("aviso-error", '<i class="bi bi-x-octagon me-1"></i>No se pudo comunicar con el servicio de detección.');
        reiniciarCuenta();
        await esperar(2000);
      }
    }
  }

  function medir(ms) {
    tiempos.push(ms);
    if (tiempos.length > 20) tiempos.shift();
    const promedio = tiempos.reduce((a, b) => a + b, 0) / tiempos.length;
    velocidad.textContent = `${(1000 / promedio).toFixed(1)} FPS · ${Math.round(promedio)} ms`;
  }

  // ---------- Detecciones de cada fotograma
  function procesar(detecciones) {
    const requisitos = laboratorioActual().requisitos;
    const minimo = Object.fromEntries(requisitos.map((r) => [r.clase, r.confianza_minima]));
    dibujar(detecciones, minimo);

    const ahora = performance.now();
    const delFotograma = {};
    for (const d of detecciones) delFotograma[d.clase] = Math.max(delFotograma[d.clase] || 0, d.confianza);
    historial.push({ t: ahora, confianzas: delFotograma });
    historial = historial.filter((h) => ahora - h.t <= VENTANA_MS);

    // Mejor confianza de cada EPP en el último segundo.
    const suavizadas = {};
    for (const h of historial) {
      for (const [clase, valor] of Object.entries(h.confianzas)) suavizadas[clase] = Math.max(suavizadas[clase] || 0, valor);
    }
    pintarLista(suavizadas);

    if (detecciones.length) ultimaDeteccion = ahora;
    if (ahora - ultimaDeteccion > SIN_DETECCION_MS) {
      // HU06-CA03: el modelo no tiene la clase "persona"; sin detecciones se asume que nadie está en el encuadre.
      avisar("aviso-warn", '<i class="bi bi-person-exclamation me-1"></i>No se detecta a ninguna persona con EPP en el encuadre. Ubíquese frente a la cámara.');
      reiniciarCuenta();
      return;
    }
    avisar("", "");
    estabilizar(requisitos, suavizadas, ahora);
  }

  // ---------- HU07: estabilización y resultado
  function reiniciarCuenta() {
    claveEstable = null;
    inicioEstable = null;
    maximos = {};
    if (!pausado) mostrarProgreso(0, "Esperando una detección estable…");
  }

  function estabilizar(requisitos, suavizadas, ahora) {
    // Clave = qué EPP obligatorios están detectados. Si cambia, la cuenta vuelve a empezar.
    const clave = requisitos
      .filter((r) => r.obligatorio)
      .map((r) => `${r.clase}:${(suavizadas[r.clase] || 0) >= r.confianza_minima ? 1 : 0}`)
      .join("|");
    if (clave !== claveEstable) {
      claveEstable = clave;
      inicioEstable = ahora;
      maximos = {};
    }
    for (const [clase, valor] of Object.entries(suavizadas)) maximos[clase] = Math.max(maximos[clase] || 0, valor);

    const segundos = laboratorioActual().estabilizacion;
    const transcurrido = (ahora - inicioEstable) / 1000;
    const avance = segundos > 0 ? Math.min(1, transcurrido / segundos) : 1;
    mostrarProgreso(avance, `Manténgase quieto: ${Math.min(transcurrido, segundos).toFixed(1)} de ${segundos} s`);
    if (avance >= 1) emitirResultado({ ...maximos });
  }

  function mostrarProgreso(avance, etiqueta) {
    barraProgreso.style.width = `${Math.round(avance * 100)}%`;
    textoProgreso.textContent = etiqueta;
  }

  async function emitirResultado(confianzas) {
    pausado = true;
    mostrarProgreso(1, "Calculando el resultado…");
    try {
      const respuesta = await fetch(window.EPP.urlEvaluar, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.EPP.csrf },
        body: JSON.stringify({ laboratorio: selLaboratorio.value, confianzas }),
      });
      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.mensaje);
      mostrarResultado(datos);
    } catch (e) {
      avisar("aviso-error", `<i class="bi bi-x-octagon me-1"></i>No se pudo calcular el resultado. ${texto(e.message || "")}`);
      reiniciarEvaluacion();
    }
  }

  function mostrarResultado(datos) {
    const cumple = datos.resultado === "conforme";
    let html = `<div class="titulo"><i class="bi ${cumple ? "bi-check-circle-fill" : "bi-x-circle-fill"} me-1"></i>${texto(datos.etiqueta)}</div>`;
    if (!cumple) {
      html += `<div class="mt-2 fw-semibold">Falta: ${datos.faltantes.map(texto).join(", ")}</div>`;
      html += '<div class="small mt-1">Colóquese los EPP faltantes y presione "Verificar de nuevo".</div>';
    }
    resultadoFinal.className = `resultado-final mt-3 ${cumple ? "cumple" : "no-cumple"}`;
    resultadoFinal.innerHTML = html;
    progreso.classList.add("d-none");
    btnReintentar.classList.remove("d-none");
    pintarListaFinal(datos.detalles);
    // HU08 se conectará aquí: registrar el ingreso "Cumple" o el intento "No cumple".
    document.dispatchEvent(new CustomEvent("epp:resultado", { detail: datos }));
  }

  // ---------- Dibujo y lista
  function dibujar(detecciones, minimo = {}) {
    const ancho = video.clientWidth;
    const alto = video.clientHeight;
    const proporcion = window.devicePixelRatio || 1;
    lienzo.width = ancho * proporcion;
    lienzo.height = alto * proporcion;
    const ctx = lienzo.getContext("2d");
    ctx.setTransform(proporcion, 0, 0, proporcion, 0, 0);
    ctx.clearRect(0, 0, ancho, alto);
    ctx.font = "600 14px Inter, system-ui, sans-serif";
    ctx.lineWidth = 3;

    for (const d of detecciones) {
      const [x1, y1, x2, y2] = d.caja;
      const x = x1 * ancho, y = y1 * alto, w = (x2 - x1) * ancho, h = (y2 - y1) * alto;
      // Verde: supera la confianza mínima del laboratorio. Naranja: detectado con poca confianza.
      const cumple = d.clase in minimo && d.confianza >= minimo[d.clase];
      const color = cumple ? "#15803d" : "#fb7e00";
      const etiqueta = `${nombresEpp[d.clase] || d.clase} ${pct(d.confianza)}`;
      ctx.strokeStyle = color;
      ctx.strokeRect(x, y, w, h);
      const anchoTexto = ctx.measureText(etiqueta).width + 10;
      const yTexto = y > 22 ? y - 22 : y;
      ctx.fillStyle = color;
      ctx.fillRect(x - 1.5, yTexto, anchoTexto, 22);
      ctx.fillStyle = "#fff";
      ctx.fillText(etiqueta, x + 4, yTexto + 16);
    }
  }

  function filaEpp(nombre, requerido, confianza, umbral, detectado) {
    const detalle = confianza ? `${pct(confianza)} (mín. ${pct(umbral)})` : `mín. ${pct(umbral)}`;
    return `
      <div class="estado-epp ${detectado ? "detectado" : "pendiente"}">
        <div>
          <div class="fw-semibold">${texto(nombre)}${requerido ? "" : ' <span class="small text-muted-epp">(opcional)</span>'}</div>
          <div class="small text-muted-epp">${detalle}</div>
        </div>
        <span class="marca">${detectado ? '<i class="bi bi-check-circle-fill"></i> Detectado' : '<i class="bi bi-circle"></i> No detectado'}</span>
      </div>`;
  }

  // HU06-CA02: estado de cada EPP requerido, actualizado en vivo.
  function pintarLista(confianzas) {
    listaEpp.innerHTML = laboratorioActual()
      .requisitos.map((r) => {
        const confianza = confianzas[r.clase] || 0;
        return filaEpp(r.epp, r.obligatorio, confianza, r.confianza_minima, confianza >= r.confianza_minima);
      })
      .join("");
  }

  // Con el resultado, la lista muestra lo que calculó el servidor.
  function pintarListaFinal(detalles) {
    listaEpp.innerHTML = detalles.map((d) => filaEpp(d.epp, d.requerido, d.confianza, d.umbral, d.detectado)).join("");
  }

  window.addEventListener("beforeunload", detener);
})();
