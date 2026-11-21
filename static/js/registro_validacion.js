// Registro de la validación (HU08 / RF07).
// - "Cumple": se guarda automáticamente, una sola vez (CA01).
// - "No cumple": el docente decide con el botón "Registrar intento no conforme" (CA02).
// - Si falla el guardado, se conserva la evaluación y se puede reintentar sin duplicar (CA04).
(function () {
  const panel = document.getElementById("registroValidacion");
  const btnReintentar = document.getElementById("btnReintentar");
  const btnTerminar = document.getElementById("btnTerminar");

  let carnetId = null;
  let pendiente = null; // evaluación esperando ser guardada
  let guardando = false;

  function nuevaClave() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor ?? "";
    return span.innerHTML;
  }

  document.addEventListener("epp:identificacion", (evento) => {
    const datos = evento.detail;
    carnetId = datos.ok && datos.carnet ? datos.carnet.id : null;
  });

  document.addEventListener("epp:resultado", (evento) => {
    const datos = evento.detail;
    pendiente = {
      clave: nuevaClave(), // la misma clave en los reintentos: así el servidor no duplica
      carnet: carnetId,
      laboratorio: datos.laboratorio,
      confianzas: datos.confianzas,
      confirmar_no_conforme: false,
    };
    if (datos.resultado === "conforme") {
      btnReintentar.classList.add("d-none"); // el ingreso ya quedó resuelto: sigue el siguiente estudiante
      registrar();
    } else {
      panel.innerHTML = `
        <button type="button" id="btnNoConforme" class="btn btn-outline-danger w-100">
          <i class="bi bi-journal-x me-1"></i>Registrar intento no conforme
        </button>
        <div class="small text-muted-epp mt-1">Regístrelo si el estudiante no va a corregir sus EPP ahora.</div>`;
      document.getElementById("btnNoConforme").addEventListener("click", () => {
        pendiente.confirmar_no_conforme = true;
        registrar();
      });
    }
  });

  // Acceso rápido al detalle (tutoría): se abre en otra pestaña para no interrumpir la verificación.
  function enlaceDetalle(id) {
    const url = window.EPP.urlDetalle.replace(/0\/?$/, `${Number(id)}/`);
    return `${url}?volver=${encodeURIComponent("/historial/registros/")}`;
  }

  function limpiar() {
    pendiente = null;
    panel.innerHTML = "";
  }
  btnReintentar.addEventListener("click", limpiar);
  btnTerminar.addEventListener("click", limpiar);

  async function registrar() {
    if (!pendiente || guardando) return;
    guardando = true;
    panel.innerHTML = '<div class="small text-muted-epp"><span class="spinner-border spinner-border-sm me-1"></span>Guardando el registro…</div>';
    try {
      const respuesta = await fetch(window.EPP.urlRegistrar, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.EPP.csrf },
        body: JSON.stringify(pendiente),
      });
      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.mensaje || "No se pudo guardar.");
      const conforme = datos.resultado === "conforme";
      panel.innerHTML = `<div class="aviso ${conforme ? "aviso-ok" : "aviso-warn"}">
        <i class="bi ${conforme ? "bi-check2-circle" : "bi-journal-x"} me-1"></i>${texto(datos.mensaje)} <span class="small">(registro #${datos.id})</span>
        </div>
        <a href="${enlaceDetalle(datos.id)}" target="_blank" rel="noopener" class="btn btn-epp-outline btn-sm w-100 mt-2">
          <i class="bi bi-pencil-square me-1"></i>Ver o corregir este registro</a>`;
      pendiente = null;
      // La campana se actualiza al instante (por si este registro completa el umbral de incidencias).
      document.dispatchEvent(new CustomEvent("epp:validacion-registrada", { detail: datos }));
    } catch (e) {
      // CA04: la evaluación se conserva; el reintento usa la misma clave.
      panel.innerHTML = `<div class="aviso aviso-error">
        <i class="bi bi-exclamation-octagon me-1"></i>No se pudo guardar el registro. ${texto(e.message)}
        <button type="button" id="btnReintentarGuardado" class="btn btn-sm btn-epp mt-2 w-100">Reintentar guardado</button></div>`;
      document.getElementById("btnReintentarGuardado").addEventListener("click", registrar);
    } finally {
      guardando = false;
    }
  }
})();
