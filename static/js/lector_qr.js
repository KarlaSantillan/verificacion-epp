// Lectura del QR del carné con la cámara (HU02) y por código escrito a mano (HU03).
(function () {
  const resultado = document.getElementById("resultado");
  const btnIniciar = document.getElementById("btnIniciar");
  const btnDetener = document.getElementById("btnDetener");
  const lector = new Html5Qrcode("lector");
  let ultimoTexto = "";
  let ultimoMomento = 0;
  let procesando = false;

  const ESTILOS = {
    registrado: "aviso aviso-info",
    nuevo: "aviso aviso-info",
    pendiente: "aviso aviso-warn",
    inactivo: "aviso aviso-error",
    vencido: "aviso aviso-error",
    no_valido_sga: "aviso aviso-error",
    qr_no_valido: "aviso aviso-error",
    codigo_no_valido: "aviso aviso-error",
    error: "aviso aviso-error",
  };

  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor ?? "—";
    return span.innerHTML;
  }

  function mostrar(datos, milisegundos) {
    const clase = ESTILOS[datos.estado] || "aviso aviso-info";
    let html = `<div class="${clase} mb-3">${texto(datos.mensaje)}</div>`;
    if (datos.estudiante) {
      html += `
        <dl class="row mb-0 small">
          <dt class="col-5">Nombre</dt><dd class="col-7">${texto(datos.estudiante.nombre)}</dd>
          <dt class="col-5">Cédula</dt><dd class="col-7">${texto(datos.estudiante.cedula)}</dd>
          <dt class="col-5">Carrera</dt><dd class="col-7">${texto(datos.estudiante.carrera)}</dd>
          <dt class="col-5">Código del carné</dt><dd class="col-7">${texto(datos.carnet.codigo)}</dd>
          <dt class="col-5">Estado del carné</dt><dd class="col-7">${texto(datos.carnet.estado_registro)}</dd>
        </dl>`;
    }
    // Tiempo de respuesta del servidor, útil para medir el RNF04 (CP55).
    html += `<p class="small text-muted-epp mt-3 mb-0">Identificado en ${milisegundos} ms</p>`;
    resultado.innerHTML = html;
  }

  // datos: { qr: "..." } cuando lee la cámara, o { codigo: "..." } cuando se escribe a mano.
  async function enviar(datosEnvio) {
    const inicio = performance.now();
    procesando = true;
    try {
      const respuesta = await fetch(window.EPP.urlIdentificar, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.EPP.csrf },
        body: JSON.stringify(datosEnvio),
      });
      const datos = await respuesta.json();
      mostrar(datos, Math.round(performance.now() - inicio));
    } catch (e) {
      mostrar({ estado: "error", mensaje: "No se pudo comunicar con el servidor." }, Math.round(performance.now() - inicio));
    } finally {
      procesando = false;
    }
  }

  function alLeer(textoQR) {
    // Evita procesar el mismo QR varias veces seguidas (la cámara lo lee muchas veces por segundo).
    const ahora = Date.now();
    if (procesando || (textoQR === ultimoTexto && ahora - ultimoMomento < 4000)) return;
    ultimoTexto = textoQR;
    ultimoMomento = ahora;
    enviar({ qr: textoQR });
  }

  // HU03: ingreso manual del código impreso en el carné.
  const formCodigo = document.getElementById("formCodigo");
  const codigoManual = document.getElementById("codigoManual");
  formCodigo.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (procesando) return;
    await enviar({ codigo: codigoManual.value });
    codigoManual.select();
  });

  btnIniciar.addEventListener("click", async () => {
    try {
      await lector.start({ facingMode: "user" }, { fps: 10, qrbox: { width: 250, height: 250 } }, alLeer, () => {});
      btnIniciar.disabled = true;
      btnDetener.disabled = false;
    } catch (e) {
      resultado.innerHTML = `<div class="aviso aviso-error">No se pudo acceder a la cámara. Revise que el navegador tenga permiso.</div>`;
    }
  });

  btnDetener.addEventListener("click", async () => {
    await lector.stop();
    btnIniciar.disabled = false;
    btnDetener.disabled = true;
  });
})();
