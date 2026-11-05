// Detección de EPP en vivo (HU06 / RF05).
// Toma fotogramas del video, los envía al servicio de detección (TK07) y dibuja
// los recuadros. Los fotogramas solo viajan en memoria: no se guardan (RF05-CA05).
(function () {
  const laboratorios = JSON.parse(document.getElementById("datos-laboratorios").textContent);
  const nombresEpp = JSON.parse(document.getElementById("nombres-epp").textContent);

  const selLaboratorio = document.getElementById("laboratorio");
  const pasoIdentificacion = document.getElementById("pasoIdentificacion");
  const pasoDeteccion = document.getElementById("pasoDeteccion");
  const btnVerificarEpp = document.getElementById("btnVerificarEpp");
  const btnTerminar = document.getElementById("btnTerminar");
  const video = document.getElementById("video");
  const lienzo = document.getElementById("lienzo");
  const videoVacio = document.getElementById("videoVacio");
  const mensaje = document.getElementById("mensajeDeteccion");
  const listaEpp = document.getElementById("listaEpp");
  const velocidad = document.getElementById("velocidad");
  const estudianteDeteccion = document.getElementById("estudianteDeteccion");

  const ANCHO_ENVIO = 640; // el modelo trabaja a 640 px: enviar más grande solo hace más lento el envío
  const SIN_DETECCION_MS = 1500; // tiempo sin detecciones antes de avisar (CA03)
  const captura = document.createElement("canvas");

  let estudiante = null;
  let flujo = null;
  let activo = false;
  let ultimaDeteccion = 0;
  let tiempos = [];

  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor ?? "—";
    return span.innerHTML;
  }

  function laboratorioActual() {
    return laboratorios.find((l) => String(l.id) === selLaboratorio.value) || { requisitos: [] };
  }

  function avisar(clase, contenido) {
    mensaje.innerHTML = contenido ? `<div class="aviso ${clase}">${contenido}</div>` : "";
  }

  // ---------- Paso 1 → Paso 2
  document.addEventListener("epp:identificacion", (evento) => {
    const datos = evento.detail;
    estudiante = datos.ok ? datos.estudiante : null;
    btnVerificarEpp.disabled = !estudiante;
  });

  btnVerificarEpp.addEventListener("click", async () => {
    if (!estudiante) return;
    if (!laboratorioActual().requisitos.length) {
      alertaLista("El laboratorio seleccionado no tiene EPP configurados.");
      return;
    }
    await window.EPP.detenerLector();
    pasoIdentificacion.classList.add("d-none");
    pasoDeteccion.classList.remove("d-none");
    estudianteDeteccion.textContent = `${estudiante.nombre} · ${selLaboratorio.options[selLaboratorio.selectedIndex].text}`;
    selLaboratorio.disabled = true;
    pintarLista([]);
    iniciar();
  });

  btnTerminar.addEventListener("click", () => {
    detener();
    estudiante = null;
    btnVerificarEpp.disabled = true;
    selLaboratorio.disabled = false;
    pasoDeteccion.classList.add("d-none");
    pasoIdentificacion.classList.remove("d-none");
    document.getElementById("resultado").textContent = "Esperando la lectura del código QR…";
  });

  function alertaLista(texto_) {
    document.getElementById("resultado").insertAdjacentHTML("beforeend", `<div class="aviso aviso-warn mt-3">${texto(texto_)}</div>`);
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

  // Un fotograma a la vez: se envía el siguiente cuando llega la respuesta del anterior.
  async function ciclo() {
    while (activo) {
      if (!video.videoWidth) {
        await new Promise((r) => setTimeout(r, 100));
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
        if (!activo) break;
        if (!resultado.ok) {
          // CA03 / RF05-CA04: servicio no disponible → mensaje y reintento, sin registrar nada.
          avisar("aviso-error", `<i class="bi bi-x-octagon me-1"></i>${texto(resultado.mensaje)}`);
          dibujar([]);
          pintarLista([]);
          await new Promise((r) => setTimeout(r, 2000));
          continue;
        }
        procesar(resultado.detecciones);
        medir(performance.now() - inicio);
      } catch (e) {
        if (!activo) break;
        avisar("aviso-error", '<i class="bi bi-x-octagon me-1"></i>No se pudo comunicar con el servicio de detección.');
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
  }

  function medir(ms) {
    tiempos.push(ms);
    if (tiempos.length > 20) tiempos.shift();
    const promedio = tiempos.reduce((a, b) => a + b, 0) / tiempos.length;
    velocidad.textContent = `${(1000 / promedio).toFixed(1)} FPS · ${Math.round(promedio)} ms`;
  }

  // ---------- Resultados
  function procesar(detecciones) {
    const requisitos = laboratorioActual().requisitos;
    const minimo = Object.fromEntries(requisitos.map((r) => [r.clase, r.confianza_minima]));
    dibujar(detecciones, minimo);
    pintarLista(detecciones);

    if (detecciones.length) ultimaDeteccion = performance.now();
    if (performance.now() - ultimaDeteccion > SIN_DETECCION_MS) {
      // CA03: el modelo no tiene la clase "persona"; sin ninguna detección se asume que nadie está en el encuadre.
      avisar("aviso-warn", '<i class="bi bi-person-exclamation me-1"></i>No se detecta a ninguna persona con EPP en el encuadre. Ubíquese frente a la cámara.');
    } else {
      avisar("", "");
    }
  }

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
      const etiqueta = `${nombresEpp[d.clase] || d.clase} ${Math.round(d.confianza * 100)} %`;
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

  // CA02: estado de cada EPP requerido, actualizado con cada fotograma.
  function pintarLista(detecciones) {
    const mejor = {};
    for (const d of detecciones) mejor[d.clase] = Math.max(mejor[d.clase] || 0, d.confianza);
    listaEpp.innerHTML = laboratorioActual()
      .requisitos.map((r) => {
        const confianza = mejor[r.clase] || 0;
        const detectado = confianza >= r.confianza_minima;
        const detalle = confianza ? `${Math.round(confianza * 100)} % (mín. ${Math.round(r.confianza_minima * 100)} %)` : `mín. ${Math.round(r.confianza_minima * 100)} %`;
        return `
          <div class="estado-epp ${detectado ? "detectado" : "pendiente"}">
            <div>
              <div class="fw-semibold">${texto(r.epp)}${r.obligatorio ? "" : ' <span class="small text-muted-epp">(opcional)</span>'}</div>
              <div class="small text-muted-epp">${detalle}</div>
            </div>
            <span class="marca">${detectado ? '<i class="bi bi-check-circle-fill"></i> Detectado' : '<i class="bi bi-circle"></i> No detectado'}</span>
          </div>`;
      })
      .join("");
  }

  window.addEventListener("beforeunload", detener);
})();
